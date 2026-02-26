# graphs/nodes/question_router.py

"""라우터 노드 - 분기 결정 (follow_up / new_topic / end_session)"""
from langfuse import observe

from schemas.question import RouteDecision, RouterOutput
from prompts.question_router import get_router_system_prompt, build_router_prompt
from graphs.question.state import QuestionState
from core.dependencies import get_llm_provider
from core.logging import get_logger

logger = get_logger(__name__)


@observe(name="question_router")
async def question_router(state: QuestionState) -> dict:
    """분기 결정 노드
    
    면접 히스토리와 설정을 분석하여 다음 행동을 결정합니다.
    """

    # 세션 시작 시 (히스토리 없음) → 바로 new_topic
    if not state.get("interview_history"):
        logger.info(f"Empty interview history - routing to NEW_TOPIC | session_id: {state.get("session_id")}")
        return {
            "route_decision": RouteDecision.NEW_TOPIC,
            "route_reasoning": "세션 시작 - 첫 질문 생성 필요"
        }
        
    
    current_topic_count = state.get("current_topic_count", 0)
    current_follow_up_count = state.get("current_follow_up_count", 0)
    max_topics = state.get("max_topics", 3)
    max_follow_ups = state.get("max_follow_ups_per_topic", 2)
    
    # 종료 조건: 최대 토픽 수 + 꼬리질문 최대치 도달
    if current_topic_count >= max_topics and current_follow_up_count >= max_follow_ups:
        logger.info(
            f"Session complete - topics: {current_topic_count}/{max_topics} | "
            f"follow-ups: {current_follow_up_count}/{max_follow_ups } | ",
            f"session_id : {state.get("session_id")}",
        )
        return {
            "route_decision": RouteDecision.END_SESSION,
            "route_reasoning": f"최대 토픽 수({max_topics})와 꼬리질문을 모두 완료하여 면접 종료"
        }
    
    # 현재 토픽 꼬리질문 최대치 도달 → new_topic 전환
    if current_follow_up_count >= max_follow_ups:
        if current_topic_count >= max_topics:
            return {
            "route_decision": RouteDecision.END_SESSION,
            "route_reasoning": f"최대 토픽 수({max_topics}) 도달로 면접 종료"
        }
        
        logger.info(
            "Max follow-ups reached - routing to NEW_TOPIC",
            f"session_id : {state.get("session_id")}"
            f"current_follow_up_count : {current_follow_up_count}"
        )
        return {
            "route_decision": RouteDecision.NEW_TOPIC,
            "route_reasoning": f"현재 토픽 꼬리질문 최대치({max_follow_ups}) 도달로 새 토픽 전환",
        }
    
    # LLM에게 분기 결정 요청
    try:
        router_output = await _invoke_router_llm(state)
        
        logger.info(
            f"session_id : {state.get("session_id")} | "
            f"Router decision: {router_output.decision.value}"
        )
        
        return {
            "route_decision": router_output.decision,
            "route_reasoning": router_output.reasoning,
        }
        
    except Exception as e:
        logger.error(f"session_id : {state.get("session_id")} | Router LLM call failed: {e}")
        return _fallback_decision(state)


@observe(name="router_llm")
async def _invoke_router_llm(state: QuestionState) -> RouterOutput:
    """LLM을 호출하여 분기 결정"""

    llm = get_llm_provider()
    
    system_prompt = get_router_system_prompt(llm.provider_name)
    user_prompt = build_router_prompt(
        question_type=state.get("question_type", "CS"),
        category=state.get("category"),
        max_topics=state.get("max_topics", 3),
        max_follow_ups_per_topic=state.get("max_follow_ups_per_topic", 2),
        current_topic_count=state.get("current_topic_count", 0),
        current_follow_up_count=state.get("current_follow_up_count", 0),
        interview_history=state.get("interview_history", []),
    )
    
    router_output = await llm.generate_structured(
        prompt=user_prompt,
        response_model=RouterOutput,
        system_prompt=system_prompt,
        temperature=0.0,
    )
        
    return router_output


def _fallback_decision(state: QuestionState) -> dict:
    """LLM 호출 실패 시 fallback"""
    current_follow_up_count = state.get("current_follow_up_count", 0)
    max_follow_ups = state.get("max_follow_ups_per_topic", 2)
    
    if current_follow_up_count >= max_follow_ups:
        return {
            "route_decision": RouteDecision.NEW_TOPIC,
            "route_reasoning": "Fallback: 꼬리질문 최대치 도달로 새 토픽 전환",
        }
    return {
        "route_decision": RouteDecision.FOLLOW_UP,
        "route_reasoning": "Fallback: 기본적으로 꼬리질문 시도",
    }


def get_route_decision(state: QuestionState) -> str:
    """조건부 엣지용 - route_decision 값 반환"""
    decision = state.get("route_decision")
    
    if decision is None:
        logger.warning("route_decision not found, defaulting to new_topic")
        return RouteDecision.NEW_TOPIC.value
    
    return decision.value