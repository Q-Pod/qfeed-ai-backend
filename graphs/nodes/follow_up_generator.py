# graphs/nodes/follow_up_generator.py
from langfuse import observe

from schemas.question import GeneratedQuestion, FollowUpOutput
from prompts.follow_up import get_follow_up_system_prompt, build_follow_up_prompt
from graphs.question.state import QuestionState
from core.dependencies import get_llm_provider
from core.logging import get_logger

logger = get_logger(__name__)


@observe(name="follow_up_generator")
async def follow_up_generator(state: QuestionState) -> dict:
    """꼬리질문 생성 노드"""
    
    current_topic_id = state.get("current_topic_id", 1)
    current_follow_up_count = state.get("current_follow_up_count", 0)
    interview_history = state.get("interview_history", [])
    
    # 현재 토픽의 카테고리 찾기
    current_topic_turns = [t for t in interview_history if t.topic_id == current_topic_id]
    if not current_topic_turns:
        raise ValueError(f"No history found for topic_id={current_topic_id}")
    
    # 메인 질문의 카테고리 사용
    main_turn = next((t for t in current_topic_turns if t.turn_type == "new_topic"), None)
    current_category = main_turn.category if main_turn else current_topic_turns[0].category
    
    logger.debug(
        f"꼬리질문 생성 시작 | topic_id={current_topic_id} | "
        f"category={current_category.value if current_category else None}"
    )
    
    question_output = await _generate_follow_up_llm(state, current_topic_turns)

    combined_text = f"{question_output.cushion_text} {question_output.question_text}"
    
    generated_question = GeneratedQuestion(
        user_id = state.get("user_id"),
        session_id = state.get("session_id"),
        question_text=combined_text,
        category=current_category,  # 현재 토픽 카테고리 유지
        topic_id=current_topic_id,
        turn_type="follow_up",
        is_session_ended=False,
        end_reason=None,
        is_bad_case=False,
        bad_case_feedback=None,
    )
    
    logger.info(
        f"꼬리질문 생성 완료 | topic_id={current_topic_id}",
        extra={
            "session_id": state.get("session_id"),
            "topic_id": current_topic_id,
            "category": current_category.value if current_category else None,
            "question_preview": question_output.question_text[:50],
        }
    )
    
    return {
        "generated_question": generated_question,
        "current_follow_up_count": current_follow_up_count + 1,
    }


@observe(name="follow_up_llm")
async def _generate_follow_up_llm(
    state: QuestionState,
    topic_turns: list,
) -> FollowUpOutput:
    """LLM 호출하여 꼬리질문 생성"""
    
    llm = get_llm_provider()
    
    system_prompt = get_follow_up_system_prompt(llm.provider_name)
    user_prompt = build_follow_up_prompt(
        question_type=state.get("question_type", "CS"),
        topic_turns=topic_turns,
    )
    
    question_output = await llm.generate_structured(
        prompt=user_prompt,
        response_model=FollowUpOutput,
        system_prompt=system_prompt,
        temperature=0.7,
    )
    
    
    return question_output
        