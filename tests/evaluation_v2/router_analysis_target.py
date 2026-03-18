"""Evaluation target - question_router 실행 후 evaluator용 결과 반환."""

from typing import Any

from graphs.nodes.CS.question_router import cs_question_router
from graphs.nodes.PF.question_router import pf_question_router
from graphs.question.state import create_initial_state
from schemas.feedback import QATurn, QuestionType


def _enum_value(value: Any) -> Any:
    if hasattr(value, "value"):
        return value.value
    return value


def _build_history(turns: list[dict]) -> list[QATurn]:
    return [QATurn(**turn) for turn in turns]


async def router_analysis_eval_task(*, item, **kwargs) -> dict:
    """Langfuse experiment task: Router 실행 후 evaluator용 공통 dict 반환."""
    input_data = item.input if hasattr(item, "input") else item["input"]
    question_type = QuestionType(input_data["question_type"])
    interview_history = _build_history(input_data.get("interview_history", []))

    state = create_initial_state(
        user_id=input_data["user_id"],
        session_id=input_data["session_id"],
        question_type=question_type,
        interview_history=interview_history,
        portfolio_summary=input_data.get("portfolio_summary"),
        question_pool=input_data.get("question_pool"),
        max_topics=input_data.get("max_topics", 3),
        max_follow_ups_per_topic=input_data.get("max_follow_ups_per_topic", 3),
    )
    state["topic_summaries"] = input_data.get("topic_summaries", [])

    if question_type == QuestionType.PORTFOLIO:
        result = await pf_question_router(state)
        analysis_key = "router_analysis"
    else:
        result = await cs_question_router(state)
        analysis_key = "router_analysis"

    route_decision = _enum_value(result.get("route_decision"))
    follow_up_direction = _enum_value(result.get("follow_up_direction"))

    return {
        "question_type": question_type.value,
        "analysis_key": analysis_key,
        "route_decision": route_decision,
        "route_reasoning": result.get("route_reasoning"),
        "follow_up_direction": follow_up_direction,
        "direction_detail": result.get("direction_detail"),
        "analysis": result.get(analysis_key),
        "topic_transition_reason": result.get("topic_transition_reason"),
        "input_snapshot": {
            "session_id": input_data["session_id"],
            "question_type": question_type.value,
            "portfolio_summary": input_data.get("portfolio_summary"),
            "topic_summaries": input_data.get("topic_summaries", []),
            "interview_history": input_data.get("interview_history", []),
            "max_topics": input_data.get("max_topics", 3),
            "max_follow_ups_per_topic": input_data.get(
                "max_follow_ups_per_topic", 3
            ),
            "current_topic_count": state.get("current_topic_count"),
            "current_follow_up_count": state.get("current_follow_up_count"),
        },
    }
