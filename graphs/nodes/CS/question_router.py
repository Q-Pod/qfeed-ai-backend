# graphs/nodes/cs_question_router.py

"""CS 기초 질문 라우터 노드

CS 실전모드에서 지원자의 답변을 분석하고,
다음 질문의 방향(follow_up / new_topic / end_session)을 결정한다.

CS 특성:
    - 정확성/완성도/깊이 세 축으로 답변을 분석한다.
    - 꼬리질문 방향은 depth/reasoning/correction/lateral 네 가지.
    - Java 백엔드가 첫 질문을 포함하여 전달하므로 interview_history가 항상 존재한다.
"""

from langfuse import observe

from graphs.question.state import QuestionState
from schemas.question import (
    RouteDecision,
    CSRouterOutput,
    CSFollowUpResult,
    CSNewTopicResult,
    EndSessionRouterResult,
)
from prompts.CS.router import (
    CS_ROUTER_SYSTEM_PROMPT,
    build_cs_router_prompt,
)
from core.dependencies import get_llm_provider
from core.logging import get_logger
from core.tracing import update_observation

logger = get_logger(__name__)


@observe(name="cs_question_router")
async def cs_question_router(state: QuestionState) -> dict:
    """CS 답변 분석 + 라우팅 결정 노드

    1. 빠른 경로: 룰 기반으로 즉시 결정 가능한 경우 LLM 호출 생략
    2. LLM 경로: CSRouterOutput 스키마로 답변 분석 + 방향 판단
    3. Fallback: LLM 실패 시 룰 기반 안전 분기

    Returns:
        dict: route_decision, route_reasoning,
              follow_up_direction (follow_up인 경우),
              direction_detail (follow_up인 경우),
              router_analysis (분석 결과)
    """

    session_id = state.get("session_id")
    current_topic_count = state.get("current_topic_count", 0)
    max_topics = state.get("max_topics", 3)
    current_follow_up_count = state.get("current_follow_up_count", 0)
    max_follow_ups = state.get("max_follow_ups_per_topic", 2)

    # ── 빠른 경로 1: 꼬리질문 최대치 도달 + 최대 토픽 도달 → 종료 ──
    if (
        current_follow_up_count >= max_follow_ups
        and current_topic_count >= max_topics
    ):
        logger.info(
            f"session_id : {session_id} | "
            f"Max topics and follow-ups reached → END_SESSION"
        )
        return {
            "route_decision": RouteDecision.END_SESSION,
            "route_reasoning": (
                f"최대 토픽 수({max_topics})와 꼬리질문 최대치 도달로 면접 종료"
            ),
        }

    # ── 빠른 경로 2: 꼬리질문 최대치 도달 → 새 토픽 ────────────
    if current_follow_up_count >= max_follow_ups:
        logger.info(
            f"session_id : {session_id} | "
            f"Max follow-ups reached ({current_follow_up_count}/{max_follow_ups}) → NEW_TOPIC"
        )
        return {
            "route_decision": RouteDecision.NEW_TOPIC,
            "route_reasoning": (
                f"현재 토픽 꼬리질문 최대치({max_follow_ups})에 도달하여 새 토픽으로 전환"
            ),
        }

    # ── LLM 호출: 답변 분석 + 라우팅 결정 ─────────────────────
    try:
        router_result = await _invoke_cs_router_llm(state)
        return _parse_router_result(router_result, state)

    except Exception as e:
        logger.error(
            f"session_id : {session_id} | "
            f"CS router LLM failed | {type(e).__name__}: {e}"
        )
        return _fallback_decision(state)


async def _invoke_cs_router_llm(state: QuestionState) -> CSRouterOutput:
    """LLM을 호출하여 CS 답변 분석 + 라우팅 결정"""

    interview_history = state.get("interview_history", [])
    last_turn = interview_history[-1]

    user_prompt = build_cs_router_prompt(
        interview_history=interview_history,
        current_topic_id=state.get("current_topic_id", 1),
        current_topic_count=state.get("current_topic_count", 1),
        max_topics=state.get("max_topics", 3),
        current_follow_up_count=state.get("current_follow_up_count", 0),
        max_follow_ups_per_topic=state.get("max_follow_ups_per_topic", 2),
        last_question=last_turn.question,
        last_answer=last_turn.answer_text,
    )

    llm_provider = get_llm_provider("gemini")

    router_output = await llm_provider.generate_structured(
        prompt=user_prompt,
        system_prompt=CS_ROUTER_SYSTEM_PROMPT,
        response_model=CSRouterOutput,
        temperature=0.0,
    )

    update_observation(
        output={
            "decision": router_output.decision if hasattr(router_output, "decision") else str(router_output),
        }
    )

    return router_output


def _parse_router_result(result: CSRouterOutput, state: QuestionState) -> dict:
    """LLM 출력(Union 타입)을 state 업데이트 dict로 변환

    CSRouterOutput = Union[CSFollowUpResult, CSNewTopicResult, EndSessionRouterResult]
    """

    session_id = state.get("session_id")
    current_topic_count = state.get("current_topic_count", 0)
    max_topics = state.get("max_topics", 3)

    if isinstance(result, CSFollowUpResult):
        logger.info(
            f"session_id : {session_id} | "
            f"Router decision: follow_up | "
            f"direction: {result.follow_up_direction}"
        )
        return {
            "route_decision": RouteDecision.FOLLOW_UP,
            "route_reasoning": result.reasoning,
            "follow_up_direction": result.follow_up_direction,
            "direction_detail": result.direction_detail,
            "router_analysis": result.analysis.model_dump(),
        }

    elif isinstance(result, CSNewTopicResult):
        if current_topic_count >= max_topics:
            logger.info(
                f"session_id : {session_id} | "
                f"Router requested new_topic at topic cap ({current_topic_count}/{max_topics}) → END_SESSION"
            )
            return {
                "route_decision": RouteDecision.END_SESSION,
                "route_reasoning": (
                    f"최대 토픽 수({max_topics})에 도달한 상태이므로 새 토픽 대신 면접 종료"
                ),
                "router_analysis": result.analysis.model_dump(),
            }

        logger.info(
            f"session_id : {session_id} | "
            f"Router decision: new_topic | "
            f"reason: {result.topic_transition_reason}"
        )
        return {
            "route_decision": RouteDecision.NEW_TOPIC,
            "route_reasoning": result.reasoning,
            "router_analysis": result.analysis.model_dump(),
            "topic_transition_reason": result.topic_transition_reason,
        }

    elif isinstance(result, EndSessionRouterResult):
        logger.info(
            f"session_id : {session_id} | "
            f"Router decision: end_session"
        )
        return {
            "route_decision": RouteDecision.END_SESSION,
            "router_analysis": result.analysis.model_dump(),
            "route_reasoning": result.reasoning,
        }

    else:
        logger.warning(
            f"session_id : {session_id} | "
            f"Unexpected router result type: {type(result).__name__}, "
            f"falling back"
        )
        return _fallback_decision(state)


def _fallback_decision(state: QuestionState) -> dict:
    """LLM 호출 실패 시 안전한 fallback 분기

    - 꼬리질문 여유가 있으면 follow_up (depth 방향)
    - 없으면 new_topic
    """
    current_follow_up_count = state.get("current_follow_up_count", 0)
    max_follow_ups = state.get("max_follow_ups_per_topic", 2)

    if current_follow_up_count < max_follow_ups:
        return {
            "route_decision": RouteDecision.FOLLOW_UP,
            "route_reasoning": "Fallback: LLM 호출 실패, 기본적으로 꼬리질문 시도",
            "follow_up_direction": "depth",
            "direction_detail": "이전 답변에서 부족했던 부분을 더 구체적으로 확인",
        }
    else:
        return {
            "route_decision": RouteDecision.NEW_TOPIC,
            "route_reasoning": "Fallback: LLM 호출 실패, 새 토픽으로 전환",
        }


def get_cs_route_decision(state: QuestionState) -> str:
    """조건부 엣지용 - route_decision 값 반환

    LangGraph의 add_conditional_edges에서 사용한다.
    route_decision이 RouteDecision enum이면 .value로,
    이미 문자열이면 그대로 반환한다.
    """
    decision = state.get("route_decision")

    if decision is None:
        logger.warning("route_decision not found in state, defaulting to new_topic")
        return RouteDecision.NEW_TOPIC.value

    if isinstance(decision, RouteDecision):
        return decision.value

    return str(decision)
