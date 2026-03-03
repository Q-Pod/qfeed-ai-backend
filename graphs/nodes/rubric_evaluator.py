from graphs.feedback.state import FeedbackGraphState
from schemas.feedback import RubricEvaluationResult
from prompts.rubric import get_rubric_system_prompt, build_rubric_prompt
from core.dependencies import get_llm_provider
from core.logging import get_logger
from langfuse import observe

logger = get_logger(__name__)

RUBRIC_DIMS = ["accuracy", "logic", "specificity", "completeness", "delivery"]

# Provider별 조건부 calibration 규칙
# threshold: 이 점수 이하일 때만 +1 보정 적용 (정수 점수의 과소채점 보정)
#   - 높은 threshold(4) → 대부분의 점수에 +1 (심한 과소채점 차원용)
#   - 낮은 threshold(3) → 낮은 점수에만 +1 (약한 과소채점, 과대보정 방지)
CALIBRATION_RULES: dict[str, dict[str, int]] = {
    "vllm": {
        "accuracy": 3,
        "logic": 3,
        "specificity": 2,
        "completeness": 2,
        "delivery": 3,
    },
}


def _calibrate(
    result: RubricEvaluationResult,
    provider: str,
) -> RubricEvaluationResult:
    """Post-hoc calibration: provider별 채점 편향을 조건부로 보정한다.

    raw_score ≤ threshold인 경우에만 +1을 적용하고 [1, 5] 범위로 clamp.
    이미 높은 점수(threshold 초과)는 변경하지 않아 과대보정을 방지한다.
    """
    rules = CALIBRATION_RULES.get(provider)
    if not rules:
        return result

    calibrated: dict[str, int] = {}
    for dim in RUBRIC_DIMS:
        raw = getattr(result, dim)
        threshold = rules.get(dim, 0)
        calibrated[dim] = min(5, raw + 1) if raw <= threshold else raw

    logger.debug(
        f"calibration applied | provider={provider} | "
        + " ".join(f"{d}:{getattr(result, d)}→{calibrated[d]}" for d in RUBRIC_DIMS)
    )
    return result.model_copy(update=calibrated)


@observe(name="rubric_evaluator", as_type="generation")
async def rubric_evaluator(state: FeedbackGraphState) -> dict:
    """루브릭 기반 평가 노드"""
    logger.debug(f"rubric evaluator start | interview_type={state['interview_type']}")

    llm = get_llm_provider("gemini")

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

    result = _calibrate(result, llm.provider_name)
    logger.info("Rubric evaluate completed")

    return {
        "rubric_result": result,
        "current_step": "rubric_evaluator",
    }