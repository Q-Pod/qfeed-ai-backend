# graphs/nodes/feedback_generator.py
from collections import defaultdict
from graphs.feedback.state import FeedbackGraphState, QATurn
from schemas.feedback import OverallFeedback,FeedbackGenerationResult
from prompts.feedback import (
    get_feedback_system_prompt,
    build_multi_topic_feedback_prompt,
    build_single_topic_feedback_prompt
)
from core.dependencies import get_llm_provider
from core.logging import get_logger

logger = get_logger(__name__)

def group_turns_by_topic(turns: list[QATurn]) -> dict[int, dict]:
    grouped : dict[int, list[QATurn]] = defaultdict(list)
    for turn in turns:
        grouped[turn.topic_id].append(turn)

    result = {}
    for topic_id, topic_turns in grouped.items():
        sorted_turns = sorted(topic_turns, key=lambda t: t.turn_order)

        # 메인 질문 추출 (첫 번째 main 타입)
        main_turn = next(
            (t for t in sorted_turns if t.turn_type == "main"),
            sorted_turns[0]  # fallback
        )
        main_question = main_turn.question
        # 토픽 카테고리 추출 (메인 질문의 카테고리)
        topic_category = main_turn.category

        # Q&A 텍스트 포맷팅
        qa_parts = []
        for turn in sorted_turns:
            prefix = "[메인]" if turn.turn_type == "main" else "[꼬리]"
            qa_parts.append(f"{prefix} Q: {turn.question}\nA: {turn.answer_text}")
        
        result[topic_id] = {
            "main_question": main_question,
            "category": topic_category,
            "qa_text": "\n\n".join(qa_parts),
        }
    return result


async def feedback_generator(
    state: FeedbackGraphState
) -> dict:
    """피드백 텍스트 생성 노드"""
    logger.debug("feedback generator start")
    
    llm = get_llm_provider()

    grouped_interview = group_turns_by_topic(state["interview_history"])

    is_single_topic = len(grouped_interview) == 1
    
    system_prompt = get_feedback_system_prompt(
        llm.provider_name,
        is_single_topic=is_single_topic
    )
    
    if is_single_topic:
        # 단일 토픽: 종합 피드백만 생성
        logger.debug("single topic feedback generate")
        result = await llm.generate_structured(
            prompt=build_single_topic_feedback_prompt(
                question_type=state["question_type"].value,
                category=state["category"].value if state["category"] else None,
                grouped_interview=grouped_interview,
                rubric_result=state["rubric_result"],
            ),
            response_model=OverallFeedback,  # 종합만
            system_prompt=system_prompt,
            temperature=0.5,
            max_tokens=500,
        )
        logger.info("feedback generate completed")
        return {
            "topics_feedback": None,
            "overall_feedback": result,
            "current_step": "feedback_generator",
        }
    else:
        # 멀티 토픽: 토픽별 + 종합 피드백
        logger.debug(f"multi feedback generate completed | topics={len(grouped_interview)}")
        result = await llm.generate_structured(
            prompt=build_multi_topic_feedback_prompt(
                question_type=state["question_type"].value,
                category=state["category"].value if state["category"] else None,
                grouped_interview=grouped_interview,
                rubric_result=state["rubric_result"],
            ),
            response_model=FeedbackGenerationResult,
            system_prompt=system_prompt,
            temperature=0.5,
            max_tokens=1500,
        )
        logger.info("feedback generate completed")
        return {
            "topics_feedback": result.topics_feedback,
            "overall_feedback": result.overall_feedback,
            "current_step": "feedback_generator",
        }