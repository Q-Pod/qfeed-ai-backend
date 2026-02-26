from graphs.feedback.state import FeedbackGraphState
from schemas.feedback import RubricEvaluationResult
from prompts.rubric import get_rubric_system_prompt, build_rubric_prompt
from core.dependencies import get_llm_provider
from core.logging import get_logger
from langfuse import observe

logger = get_logger(__name__)

@observe(name="rubric_evaluator", as_type="generation")
async def rubric_evaluator(state: FeedbackGraphState) -> dict:
    """루브릭 기반 평가 노드"""
    logger.debug(f"rubric evaluator start | interview_type={state['interview_type']}")

    llm = get_llm_provider()

    # 토픽별 카테고리 정보 추출
    categories_in_session = list(set(
        turn.category.value for turn in state["interview_history"] 
        if turn.category and turn.turn_type == "main"
    ))
    
    interview_text = "\n\n".join(
        f"Q: {turn.question}\nA: {turn.answer_text}"
        for turn in state["interview_history"]
    )
    
    system_prompt = get_rubric_system_prompt(llm.provider_name)
    user_prompt = build_rubric_prompt(
        question_type=state["question_type"],
        categories=categories_in_session,
        interview_text=interview_text,
    )
    
    logger.debug(f"LLM call | provider={llm.provider_name}")
    
    # LLM 호출 - 실패 시 AppException(LLM_XXX) 발생
    result = await llm.generate_structured(
        prompt=user_prompt,
        response_model=RubricEvaluationResult,
        system_prompt=system_prompt,
        temperature=0.3,
        max_tokens=2000,
    )
    logger.info("Rubric evaluate completed")

    return {
        "rubric_result": result,
        "current_step": "rubric_evaluator",
    }