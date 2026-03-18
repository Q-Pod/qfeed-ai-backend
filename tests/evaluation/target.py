"""Evaluation target - 루브릭 평가 파이프라인을 실행하는 task 함수

run_experiment의 task 파라미터로 전달되어, 각 golden dataset item에 대해
실제 rubric_evaluator 노드를 호출하고 결과를 반환한다.
"""

from schemas.feedback import (
    QATurn,
    RubricEvaluationResult,
    InterviewType,
    QuestionType,
)
from graphs.feedback.state import create_initial_state
from project.qfeed.graphs.nodes.rubric_evaluator import rubric_evaluator

RUBRIC_DIMENSIONS = ["accuracy", "logic", "specificity", "completeness", "delivery"]


async def rubric_eval_task(*, item, **kwargs) -> dict:
    """Langfuse experiment task: 루브릭 평가 실행

    Args:
        item: DatasetItemClient (Langfuse dataset) 또는 dict (local data)

    Returns:
        각 루브릭 차원별 점수 + 평균 점수
    """
    input_data = item.input if hasattr(item, "input") else item["input"]

    interview_history = [QATurn(**turn) for turn in input_data["interview_history"]]

    state = create_initial_state(
        user_id=input_data["user_id"],
        question_id=input_data.get("question_id", 0),
        interview_history=interview_history,
        interview_type=InterviewType(input_data["interview_type"]),
        question_type=QuestionType(input_data["question_type"]),
        session_id=input_data.get("session_id"),
        keywords=input_data.get("keywords"),
    )

    result = await rubric_evaluator(state)
    rubric: RubricEvaluationResult = result["rubric_result"]

    scores = {dim: getattr(rubric, dim) for dim in RUBRIC_DIMENSIONS}
    scores["average"] = sum(scores.values()) / len(RUBRIC_DIMENSIONS)

    return scores
