"""Evaluation target - follow-up 생성 결과를 evaluator 입력 형태로 반환."""

from typing import Any

from graphs.nodes.CS.follow_up_generator import _generate_cs_follow_up_llm
from graphs.nodes.PF.followup_generator import _generate_pf_follow_up_llm
from graphs.question.state import create_initial_state
from schemas.feedback import QATurn, QuestionType


def _enum_value(value: Any) -> Any:
    if hasattr(value, "value"):
        return value.value
    return value


def _build_history(turns: list[dict]) -> list[QATurn]:
    return [QATurn(**turn) for turn in turns]


def _turn_to_dict(turn: QATurn) -> dict[str, Any]:
    return {
        "question": turn.question,
        "category": _enum_value(turn.category),
        "answer_text": turn.answer_text,
        "turn_type": turn.turn_type,
        "turn_order": turn.turn_order,
        "topic_id": turn.topic_id,
    }


async def generated_question_eval_task(*, item, **kwargs) -> dict:
    """Langfuse experiment task: follow-up 생성 후 evaluator용 dict 반환."""
    input_data = item.input if hasattr(item, "input") else item["input"]

    question_type = QuestionType(input_data["question_type"])
    interview_history = _build_history(input_data.get("interview_history", []))

    if not interview_history:
        raise ValueError("generated question 평가는 interview_history가 필요합니다.")

    follow_up_direction = (input_data.get("follow_up_direction") or "").strip()
    direction_detail = (input_data.get("direction_detail") or "").strip()

    if not follow_up_direction:
        raise ValueError("follow_up_direction이 비어 있습니다.")

    state = create_initial_state(
        user_id=input_data.get("user_id", 1),
        session_id=input_data.get("session_id", "eval-generated-question"),
        question_type=question_type,
        interview_history=interview_history,
        portfolio_summary=input_data.get("portfolio_summary"),
        max_topics=input_data.get("max_topics", 3),
        max_follow_ups_per_topic=input_data.get("max_follow_ups_per_topic", 3),
    )

    current_topic_id = state.get("current_topic_id", 1)
    current_topic_turns = [
        t for t in interview_history if t.topic_id == current_topic_id
    ]
    if not current_topic_turns:
        raise ValueError(f"topic_id={current_topic_id}에 해당하는 턴이 없습니다.")

    state["follow_up_direction"] = follow_up_direction
    state["direction_detail"] = direction_detail

    if question_type == QuestionType.PORTFOLIO:
        follow_up_output = await _generate_pf_follow_up_llm(
            state=state,
            current_topic_turns=current_topic_turns,
            follow_up_direction=follow_up_direction,
            direction_detail=direction_detail,
        )
    else:
        follow_up_output = await _generate_cs_follow_up_llm(
            state=state,
            current_topic_turns=current_topic_turns,
            follow_up_direction=follow_up_direction,
            direction_detail=direction_detail,
        )

    last_turn = current_topic_turns[-1]
    question_text = (follow_up_output.question_text or "").strip()
    cushion_text = (follow_up_output.cushion_text or "").strip()

    return {
        "question_type": question_type.value,
        "follow_up_direction": follow_up_direction,
        "direction_detail": direction_detail,
        "portfolio_summary": input_data.get("portfolio_summary"),
        "current_topic_id": current_topic_id,
        "interview_history": [_turn_to_dict(t) for t in interview_history],
        "current_topic_turns": [_turn_to_dict(t) for t in current_topic_turns],
        "last_question": last_turn.question,
        "last_answer": last_turn.answer_text,
        "cushion_text": cushion_text,
        "question_text": question_text,
        "combined_text": f"{cushion_text} {question_text}".strip(),
        "question_char_count": len(question_text),
    }
