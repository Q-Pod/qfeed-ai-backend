"""Evaluation target - 새 토픽 질문 생성 파이프라인을 실행하는 task 함수

run_experiment의 task 파라미터로 전달되어, 각 golden dataset item에 대해
_generate_new_topic_llm을 호출하고 결과를 반환한다.

반환 형태 (evaluator가 소비하는 구조):
    {
        "question_type": "CS" | "SYSTEM_DESIGN",
        "is_first_question": bool,
        "category_expected": str | None,       # forced일 때만 존재
        "category_generated": str,             # LLM이 생성한 카테고리
        "available_categories": list[str] | None,
        "cushion_text": str,
        "question_text": str,
        "combined_text": str,
        "interview_history": list[dict],       # 중복 체크용
    }
"""

from schemas.feedback import QATurn, QuestionType, parse_category, get_valid_categories
from graphs.question.state import create_initial_state
from graphs.nodes.new_topic_generator import _generate_new_topic_llm


async def new_topic_eval_task(*, item, **kwargs) -> dict:
    """Langfuse experiment task: 새 토픽 질문 생성 후 evaluator용 dict 반환"""
    input_data = item.input if hasattr(item, "input") else item["input"]

    question_type = QuestionType(input_data["question_type"])
    interview_history = [QATurn(**turn) for turn in input_data.get("interview_history", [])]

    initial_category_str = input_data.get("initial_category")

    #첫 질문일때 고정 카테고리 사용
    if not interview_history and initial_category_str:
        forced_category = parse_category(question_type, initial_category_str)
        available_categories = None
    else:
        forced_category = None
        available_categories = get_valid_categories(question_type)

    state = create_initial_state(
        user_id=input_data.get("user_id", 1),
        session_id=input_data.get("session_id", "eval-session"),
        question_type=question_type,
        category=forced_category,
        interview_history=interview_history,
    )

    question_output = await _generate_new_topic_llm(
        state,
        forced_category=forced_category,
        available_categories=available_categories,
    )

    return {
        "question_type": input_data["question_type"],
        "is_first_question": len(interview_history) == 0,
        "category_expected": initial_category_str,
        "category_generated": question_output.category,
        "available_categories": available_categories,
        "cushion_text": question_output.cushion_text,
        "question_text": question_output.question_text,
        "combined_text": f"{question_output.cushion_text} {question_output.question_text}",
        "interview_history": [
            {"question": t.question, "turn_type": t.turn_type}
            for t in interview_history
        ],
    }
