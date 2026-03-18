# graphs/nodes/PF/question_router.py

"""포트폴리오 질문 라우터 노드

포트폴리오 실전모드에서 지원자의 답변을 분석하고,
다음 질문의 방향(follow_up / new_topic / end_session)을 결정한다.

포트폴리오 특성:
    - 완성도/근거/트레이드오프/문제해결 네 축으로 답변을 분석한다.
    - 꼬리질문 방향은 depth/why/tradeoff/problem/scale/connect 여섯 가지.
    - follow_up 시 direction + detail을 제시하여 generator의 부담을 줄인다.
    - topic_summaries를 참조하여 이전 토픽과의 연결 질문(connect_probe)도 가능.
    - 질문 풀이 존재하므로 new_topic 시 풀에서 선택할 근거를 제공한다.
"""

from langfuse import observe

from graphs.question.state import QuestionState
from schemas.question import (
    RouteDecision,
    PortfolioRouterOutput,
    FollowUpRouterResult,
    NewTopicRouterResult,
    EndSessionRouterResult,
)
from prompts.PF.router import (
    PF_ROUTER_SYSTEM_PROMPT,
    build_pf_router_prompt,
)
from core.dependencies import get_llm_provider
from core.logging import get_logger
from core.tracing import update_observation

logger = get_logger(__name__)


# ============================================================
# 메인 노드 함수
# ============================================================

@observe(name="pf_question_router")
async def pf_question_router(state: QuestionState) -> dict:
    """포트폴리오 답변 분석 + 라우팅 결정 노드

    1. 빠른 경로: 룰 기반으로 즉시 결정 가능한 경우 LLM 호출 생략
    2. LLM 경로: PortfolioRouterOutput(Union) 스키마로 답변 분석 + 방향 판단
    3. Fallback: LLM 실패 시 룰 기반 안전 분기

    Returns:
        dict: route_decision, route_reasoning,
              follow_up_direction (follow_up인 경우),
              direction_detail (follow_up인 경우),
              router_analysis (분석 결과 dict),
              topic_transition_reason (new_topic인 경우)
    """

    session_id = state.get("session_id")
    current_topic_count = state.get("current_topic_count", 0)
    max_topics = state.get("max_topics", 3)
    current_follow_up_count = state.get("current_follow_up_count", 0)
    max_follow_ups = state.get("max_follow_ups_per_topic", 3)

    # ── 빠른 경로 1: 꼬리질문 최대치 + 최대 토픽 도달 → 종료 ──
    if (
        current_follow_up_count >= max_follow_ups
        and current_topic_count >= max_topics
    ):
        logger.info(
            f"session_id={session_id} | "
            f"Max topics({max_topics}) and follow-ups({max_follow_ups}) reached → END_SESSION"
        )
        return {
            "route_decision": RouteDecision.END_SESSION,
            "route_reasoning": (
                f"최대 토픽 수({max_topics})와 꼬리질문 최대치({max_follow_ups}) 도달로 면접 종료"
            ),
        }

    # ── 빠른 경로 2: 꼬리질문 최대치 도달 → 새 토픽 ────────────
    if current_follow_up_count >= max_follow_ups:
        logger.info(
            f"session_id={session_id} | "
            f"Max follow-ups reached ({current_follow_up_count}/{max_follow_ups}) → NEW_TOPIC"
        )
        return {
            "route_decision": RouteDecision.NEW_TOPIC,
            "route_reasoning": (
                f"현재 토픽 꼬리질문 최대치({max_follow_ups})에 도달하여 새 토픽으로 전환"
            ),
            "topic_transition_reason": "꼬리질문 최대 횟수 도달",
        }

    # ── LLM 호출: 답변 분석 + 라우팅 결정 ─────────────────────
    try:
        router_result = await _invoke_pf_router_llm(state)
        return _parse_router_result(router_result, state)

    except Exception as e:
        logger.error(
            f"session_id={session_id} | "
            f"PF router LLM failed | {type(e).__name__}: {e}"
        )
        return _fallback_decision(state)


# ============================================================
# LLM 호출
# ============================================================

async def _invoke_pf_router_llm(state: QuestionState) -> PortfolioRouterOutput:
    """Gemini Flash를 호출하여 포트폴리오 답변 분석 + 라우팅 결정

    PortfolioRouterOutput = Union[
        FollowUpRouterResult,
        NewTopicRouterResult,
        EndSessionRouterResult
    ]
    """

    interview_history = state.get("interview_history", [])
    last_turn = interview_history[-1]

    user_prompt = build_pf_router_prompt(
        portfolio_summary=state.get("portfolio_summary", "포트폴리오 정보 없음"),
        topic_summaries=state.get("topic_summaries", []),
        interview_history=interview_history,
        current_topic_id=state.get("current_topic_id", 1),
        current_topic_count=state.get("current_topic_count", 1),
        max_topics=state.get("max_topics", 3),
        current_follow_up_count=state.get("current_follow_up_count", 0),
        max_follow_ups_per_topic=state.get("max_follow_ups_per_topic", 3),
        last_question=last_turn.question,
        last_answer=last_turn.answer_text,
    )

    llm_provider = get_llm_provider("gemini")

    router_output = await llm_provider.generate_structured(
        prompt=user_prompt,
        system_prompt=PF_ROUTER_SYSTEM_PROMPT,
        response_model=PortfolioRouterOutput,
        temperature=0.2,
    )

    update_observation(
        output={
            "decision": router_output.decision
            if hasattr(router_output, "decision")
            else str(router_output),
        }
    )

    return router_output


# ============================================================
# 결과 파싱
# ============================================================

def _parse_router_result(result: PortfolioRouterOutput, state: QuestionState) -> dict:
    """LLM 출력(Union 타입)을 state 업데이트 dict로 변환

    PortfolioRouterOutput = Union[
        FollowUpRouterResult,
        NewTopicRouterResult,
        EndSessionRouterResult
    ]

    LangGraph 노드는 반드시 dict를 반환해야 한다.
    """

    session_id = state.get("session_id")
    current_topic_count = state.get("current_topic_count", 0)
    max_topics = state.get("max_topics", 3)

    # ── follow_up ──────────────────────────────────────────────
    if isinstance(result, FollowUpRouterResult):
        logger.info(
            f"session_id={session_id} | "
            f"Router decision: follow_up | "
            f"direction: {result.follow_up_direction}"
        )
        return {
            "route_decision": RouteDecision.FOLLOW_UP,
            "route_reasoning": result.reasoning,
            "follow_up_direction": result.follow_up_direction.value,
            "direction_detail": result.direction_detail,
            "router_analysis": result.analysis.model_dump(),
        }

    # ── new_topic ──────────────────────────────────────────────
    elif isinstance(result, NewTopicRouterResult):
        if current_topic_count >= max_topics:
            logger.info(
                f"session_id={session_id} | "
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
            f"session_id={session_id} | "
            f"Router decision: new_topic | "
            f"reason: {result.topic_transition_reason}"
        )
        return {
            "route_decision": RouteDecision.NEW_TOPIC,
            "route_reasoning": result.reasoning,
            "router_analysis": result.analysis.model_dump(),
            "topic_transition_reason": result.topic_transition_reason,
        }

    # ── end_session ────────────────────────────────────────────
    elif isinstance(result, EndSessionRouterResult):
        logger.info(
            f"session_id={session_id} | "
            f"Router decision: end_session"
        )
        return {
            "route_decision": RouteDecision.END_SESSION,
            "router_analysis": result.analysis.model_dump(),
            "route_reasoning": result.reasoning,
        }

    # ── unexpected ─────────────────────────────────────────────
    else:
        logger.warning(
            f"session_id={session_id} | "
            f"Unexpected router result type: {type(result).__name__}, "
            f"falling back"
        )
        return _fallback_decision(state)


# ============================================================
# Fallback
# ============================================================

def _fallback_decision(state: QuestionState) -> dict:
    """LLM 호출 실패 시 안전한 fallback 분기

    - 꼬리질문 여유가 있으면 follow_up (depth_probe 방향)
    - 없으면 new_topic
    """
    current_follow_up_count = state.get("current_follow_up_count", 0)
    max_follow_ups = state.get("max_follow_ups_per_topic", 3)

    if current_follow_up_count < max_follow_ups:
        return {
            "route_decision": RouteDecision.FOLLOW_UP,
            "route_reasoning": "Fallback: LLM 호출 실패, 기본적으로 꼬리질문 시도",
            "follow_up_direction": "depth_probe",
            "direction_detail": "이전 답변에서 언급한 내용을 더 구체적으로 확인",
        }
    else:
        return {
            "route_decision": RouteDecision.NEW_TOPIC,
            "route_reasoning": "Fallback: LLM 호출 실패, 새 토픽으로 전환",
            "topic_transition_reason": "LLM 호출 실패로 인한 자동 토픽 전환",
        }


# ============================================================
# 조건부 엣지 함수
# ============================================================

def get_pf_route_decision(state: QuestionState) -> str:
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
