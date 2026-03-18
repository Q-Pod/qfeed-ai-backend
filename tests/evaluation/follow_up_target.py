"""Evaluation target - 꼬리질문 생성 파이프라인을 실행하는 task 함수

run_experiment의 task 파라미터로 전달되어, 각 golden dataset item에 대해
_generate_follow_up_llm을 호출하고 결과를 반환한다.

반환 형태 (evaluator가 소비하는 구조):
    {
        "question_type": "CS" | "SYSTEM_DESIGN",
        "category": str,
        "cushion_text": str,
        "question_text": str,
        "combined_text": str,
        "interview_history": list[dict],
        "topic_id": int,
    }
"""

from schemas.feedback import QATurn, QuestionType
from graphs.question.state import create_initial_state
from graphs.nodes.follow_up_generator import _generate_follow_up_llm


async def follow_up_eval_task(*, item, **kwargs) -> dict:
    """Langfuse experiment task: 꼬리질문 생성 후 evaluator용 dict 반환"""
    input_data = item.input if hasattr(item, "input") else item["input"]

    question_type = QuestionType(input_data["question_type"])
    interview_history = [QATurn(**turn) for turn in input_data.get("interview_history", [])]

    if not interview_history:
        raise ValueError("꼬리질문 평가는 interview_history가 비어 있으면 안 됩니다.")

    state = create_initial_state(
        user_id=input_data.get("user_id", 1),
        session_id=input_data.get("session_id", "eval-session"),
        question_type=question_type,
        interview_history=interview_history,
    )

    current_topic_id = state["current_topic_id"]
    topic_turns = [t for t in interview_history if t.topic_id == current_topic_id]

    question_output = await _generate_follow_up_llm(state, topic_turns)

    category = None
    if topic_turns:
        main_turn = next(
            (t for t in topic_turns if t.turn_type == "new_topic"),
            topic_turns[0],
        )
        category = main_turn.category.value if main_turn.category else None

    return {
        "question_type": input_data["question_type"],
        "category": category,
        "cushion_text": question_output.cushion_text,
        "question_text": question_output.question_text,
        "combined_text": f"{question_output.cushion_text} {question_output.question_text}",
        "interview_history": [
            {
                "question": t.question,
                "answer_text": t.answer_text,
                "turn_type": t.turn_type,
                "topic_id": t.topic_id,
            }
            for t in interview_history
        ],
        "topic_id": current_topic_id,
    }
