# graphs/nodes/new_topic_generator.py

"""새 토픽 질문 생성 노드"""

from langfuse import observe

from schemas.question import QuestionOutput, GeneratedQuestion, QuestionType
from schemas.feedback import QuestionCategory, parse_category, get_valid_categories
from prompts.new_topic import get_new_topic_system_prompt, build_new_topic_prompt
from graphs.question.state import QuestionState
from core.dependencies import get_llm_provider
from core.logging import get_logger

logger = get_logger(__name__)


@observe(name="new_topic_generator")
async def new_topic_generator(state: QuestionState) -> dict:
    """새 토픽 질문 생성 노드"""
    current_topic_id = state.get("current_topic_id", 0)
    current_topic_count = state.get("current_topic_count", 0)
    new_topic_id = current_topic_id + 1
    interview_history = state.get("interview_history", [])
    question_type = state.get("question_type", QuestionType.CS)
    valid_categories = get_valid_categories(question_type)

    if not interview_history:
        initial_category = state.get("category")
        if initial_category is None and question_type != QuestionType.PORTFOLIO:
            raise ValueError("initial_category is required for first question")
        
        question_output = await _generate_new_topic_llm(
            state, 
            forced_category=initial_category,
        )
        category = initial_category
    else:
        # 이후 질문: LLM이 카테고리 선택
        question_output = await _generate_new_topic_llm(
            state, 
            available_categories=valid_categories
        )
        
        # LLM 출력(문자열)을 Enum으로 파싱
        if question_output.category:
            try:
                category = parse_category(question_type, question_output.category)
            except ValueError:
                logger.warning(f"LLM generated invalid category: {question_output.category}. Falling back.")
                # Fallback: 남은 카테고리 중 랜덤 선택하거나 기본값 할당
                category = None 
        else:
            category = None

    combined_text = f"{question_output.cushion_text} {question_output.question_text}"
    logger.debug(
        f"new topic generate | topic_id={new_topic_id} | "
        f"category={category.value if category else None}"
    )
    
    generated_question = GeneratedQuestion(
        user_id=state.get("user_id"),
        session_id=state.get("session_id"),
        question_text=combined_text,
        category=category,
        topic_id=new_topic_id,
        turn_type="main",
        is_session_ended=False,
        end_reason=None,
        is_bad_case=False,
        bad_case_feedback=None,
    )
    
    logger.info(
        f"새 토픽 질문 생성 완료 | topic_id={new_topic_id}",
        extra={
            "user_id": state.get("user_id"),
            "session_id": state.get("session_id"),
            "topic_id": new_topic_id,
            "category": category.value if category else None,
            "question_preview": combined_text[:50],
        }
    )
    
    return {
        "generated_question": generated_question,
        "current_topic_id": new_topic_id,
        "current_topic_count": current_topic_count + 1,
        "current_follow_up_count": 0,
    }
        

@observe(name="new_topic_llm")
async def _generate_new_topic_llm(state: QuestionState, forced_category: QuestionCategory | None = None, available_categories: list | None = None) -> QuestionOutput:
    """LLM 호출하여 새 토픽 질문 생성"""
    
    llm = get_llm_provider()
    
    system_prompt = get_new_topic_system_prompt(llm.provider_name)
    user_prompt = build_new_topic_prompt(
        question_type=state.get("question_type", QuestionType.CS),
        forced_category=forced_category,
        interview_history=state.get("interview_history", []),
        available_categories = available_categories,
    )

    question_output = await llm.generate_structured(
            prompt=user_prompt,
            response_model=QuestionOutput,
            system_prompt=system_prompt,
            temperature=0.7,
        )
    
    return question_output