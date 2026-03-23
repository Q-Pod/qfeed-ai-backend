# graphs/nodes/feedback_generator.py

"""연습모드 피드백 텍스트 생성 노드

연습모드에서만 사용. 단일 Q&A에 대한 종합 피드백을 생성한다.
실전모드는 feedback_generator_realmode.py가 담당.

question_type별로 다른 프롬프트를 사용:
    - CS: 정확성, 완성도, 논리적 추론, 깊이, 전달력 기준
    - (시스템디자인: 현재 미지원)
"""

from collections import defaultdict

from graphs.feedback.state import FeedbackGraphState, QATurn
from schemas.feedback_v2 import OverallFeedback
from prompts.feedback_practice_mode import (
    get_practice_feedback_system_prompt,
    build_practice_feedback_prompt,
)
from core.dependencies import get_llm_provider
from core.logging import get_logger
from langfuse import observe

logger = get_logger(__name__)


def group_turns_by_topic(turns: list[QATurn]) -> dict[int, dict]:
    """토픽별 Q&A 그룹핑 (연습모드는 보통 단일 토픽)"""
    grouped: dict[int, list[QATurn]] = defaultdict(list)
    for turn in turns:
        grouped[turn.topic_id].append(turn)

    result = {}
    for topic_id, topic_turns in grouped.items():
        sorted_turns = sorted(topic_turns, key=lambda t: t.turn_order)

        main_turn = next(
            (t for t in sorted_turns if t.turn_type == "new_topic"),
            sorted_turns[0],
        )

        qa_parts = []
        for turn in sorted_turns:
            prefix = "[메인]" if turn.turn_type == "new_topic" else "[꼬리]"
            qa_parts.append(f"{prefix} Q: {turn.question}\nA: {turn.answer_text}")

        result[topic_id] = {
            "main_question": main_turn.question,
            "category": main_turn.category,
            "qa_text": "\n\n".join(qa_parts),
        }
    return result


@observe(name="feedback_generator", as_type="generation")
async def feedback_generator(state: FeedbackGraphState) -> dict:
    """연습모드 피드백 텍스트 생성 노드

    단일 Q&A에 대한 종합 피드백(strengths + improvements)을 생성.
    question_type에 따라 다른 프롬프트를 사용.

    Returns:
        dict: topics_feedback(None) + overall_feedback + current_step
    """

    logger.debug(
        f"Practice feedback generator start | "
        f"question_type={state['question_type'].value}"
    )

    llm = get_llm_provider()

    grouped_interview = group_turns_by_topic(state["interview_history"])

    system_prompt = get_practice_feedback_system_prompt(state["question_type"])

    user_prompt = build_practice_feedback_prompt(
        question_type=state["question_type"],
        category=state.get("category"),
        grouped_interview=grouped_interview,
        keyword_result=state.get("keyword_result"),
        router_analyses=state.get("router_analyses"),
    )

    result = await llm.generate_structured(
        prompt=user_prompt,
        response_model=OverallFeedback,
        system_prompt=system_prompt,
        temperature=0.5,
        max_tokens=4000,
    )

    logger.info(
        f"Practice feedback generated | "
        f"question_type={state['question_type'].value} | "
        f"strengths_len={len(result.strengths)}"
    )

    return {
        "topics_feedback": None,
        "overall_feedback": result,
        "current_step": "feedback_generator",
    }
