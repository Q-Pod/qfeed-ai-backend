"""Evaluation target - 피드백 생성 파이프라인을 실행하는 task 함수

run_experiment의 task 파라미터로 전달되어, 각 golden dataset item에 대해
실제 feedback_generator 노드를 호출하고 결과를 반환한다.

반환 형태 (evaluator가 소비하는 구조):
    {
        "interview_type": "PRACTICE_INTERVIEW" | "REAL_INTERVIEW",
        "qa_text": str,  # Judge 평가용 원문 Q&A
        "overall_feedback": {"strengths": str, "improvements": str},
        "topics_feedback": [{"topic_id": int, "strengths": str, "improvements": str}] | None,
    }
"""

from schemas.feedback import (
    QATurn,
    OverallFeedback,
    TopicFeedback,
    InterviewType,
    QuestionType,
)
from graphs.feedback.state import create_initial_state
from project.qfeed.graphs.nodes.CS.feedback_generator import feedback_generator


async def feedback_eval_task(*, item, **kwargs) -> dict:
    """Langfuse experiment task: 피드백 생성 실행 후 evaluator용 dict 반환"""
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

    result = await feedback_generator(state)

    qa_lines = []
    for turn in interview_history:
        qa_lines.append(f"Q: {turn.question}")
        qa_lines.append(f"A: {turn.answer_text}")
        qa_lines.append("")

    output: dict = {
        "interview_type": input_data["interview_type"],
        "qa_text": "\n".join(qa_lines).strip(),
    }

    overall: OverallFeedback | None = result.get("overall_feedback")
    if overall:
        output["overall_feedback"] = {
            "strengths": overall.strengths,
            "improvements": overall.improvements,
        }

    topics: list[TopicFeedback] | None = result.get("topics_feedback")
    if topics:
        output["topics_feedback"] = [
            {
                "topic_id": t.topic_id,
                "main_question": t.main_question,
                "strengths": t.strengths,
                "improvements": t.improvements,
            }
            for t in topics
        ]

    return output
