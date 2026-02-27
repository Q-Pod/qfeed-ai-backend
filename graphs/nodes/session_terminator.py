# graphs/nodes/session_terminator.py

"""세션 종료 노드"""

from langfuse import observe

from schemas.question import GeneratedQuestion
from graphs.question.state import QuestionState
from core.logging import get_logger

logger = get_logger(__name__)


@observe(name="session_terminator", as_type="tool")
async def session_terminator(state: QuestionState) -> dict:
    """세션 종료 노드"""
    
    user_id = state.get("user_id")
    session_id = state.get("session_id")
    current_topic_id = state.get("current_topic_id", 1)
    current_topic_count = state.get("current_topic_count", 0)
    interview_history = state.get("interview_history", [])
    
    # 종료 사유 결정
    end_reason = _determine_end_reason(state)
    
    # 세션 통계
    total_questions = len(interview_history)
    
    # 마지막 turn_type
    last_turn_type = "new_topic"
    if interview_history:
        last_turn = interview_history[-1]
        last_turn_type = last_turn.turn_type
        last_category = last_turn.category
    
    generated_question = GeneratedQuestion(
        user_id = user_id,
        session_id = session_id,
        question_text="수고하셨습니다. 준비된 모든 면접 질문이 종료되었습니다.",
        category=last_category,  # 마지막 토픽의 카테고리
        topic_id=current_topic_id,
        turn_type=last_turn_type,
        is_session_ended=True,
        end_reason=end_reason,
        is_bad_case=False,
        bad_case_feedback=None,
    )
    
    logger.info(
        "세션 종료",
        extra={
            "user_id": user_id,
            "session_id": session_id,
            "end_reason": end_reason,
            "total_topics": current_topic_count,
            "total_questions": total_questions,
        }
    )
    
    return {
        "generated_question": generated_question,
    }


def _determine_end_reason(state: QuestionState) -> str:
    """종료 사유 결정"""
    
    current_topic_count = state.get("current_topic_count", 0)
    max_topics = state.get("max_topics", 3)
    current_follow_up_count = state.get("current_follow_up_count", 0)
    max_follow_ups = state.get("max_follow_ups_per_topic", 3)
    route_reasoning = state.get("route_reasoning", "")
    
    if route_reasoning:
        return route_reasoning
    
    if current_topic_count >= max_topics and current_follow_up_count >= max_follow_ups:
        return f"모든 토픽({max_topics}개)과 꼬리질문을 완료하여 면접 종료"
    
    if current_topic_count >= max_topics:
        return f"최대 토픽 수({max_topics}개)에 도달하여 면접 종료"
    
    return "면접 세션 완료"
