# graphs/nodes/rubric_evaluator.py

"""연습모드 루브릭 평가 노드

연습모드에서만 사용. LLM이 직접 루브릭 점수를 산출한다.
실전모드는 services/rubric_scorer.py (rule-based)가 담당.

질문 유형별 다른 스키마와 프롬프트를 사용:
    - CS: CSRubricScores (correctness, completeness, reasoning, depth, delivery)
    - (시스템디자인: 현재 미지원)
"""

from graphs.feedback.state import FeedbackGraphState
from schemas.feedback import QuestionType
from schemas.feedback_v2 import CSRubricScores
from prompts.CS.rubric import (
    get_rubric_system_prompt,
    build_rubric_prompt,
)
from core.dependencies import get_llm_provider
from core.logging import get_logger
from langfuse import observe

logger = get_logger(__name__)


@observe(name="rubric_evaluator", as_type="generation")
async def rubric_evaluator(state: FeedbackGraphState) -> dict:
    """연습모드 루브릭 평가 노드

    question_type에 따라 다른 스키마와 프롬프트로 LLM 채점.

    Returns:
        dict: rubric_result + current_step
    """

    question_type = state["question_type"]

    logger.debug(
        f"Practice rubric evaluator start | "
        f"question_type={question_type.value}"
    )

    llm = get_llm_provider("gemini")

    # 면접 텍스트 구성
    interview_text = "\n\n".join(
        f"Q: {turn.question}\nA: {turn.answer_text}"
        for turn in state["interview_history"]
    )

    # 카테고리 추출
    categories = list(set(
        turn.category.value
        for turn in state["interview_history"]
        if turn.category
    ))

    # question_type별 프롬프트 + 스키마 선택
    if question_type == QuestionType.CS:
        system_prompt = get_rubric_system_prompt(question_type)
        user_prompt = build_rubric_prompt(
            question_type=question_type,
            categories=categories,
            interview_text=interview_text,
        )
        response_model = CSRubricScores

    else:
        # 미지원 유형은 CS로 fallback
        logger.warning(
            f"Unsupported question_type={question_type.value} "
            f"for rubric evaluation, falling back to CS"
        )
        system_prompt = get_rubric_system_prompt(QuestionType.CS)
        user_prompt = build_rubric_prompt(
            question_type=QuestionType.CS,
            categories=categories,
            interview_text=interview_text,
        )
        response_model = CSRubricScores

    # LLM 호출
    result = await llm.generate_structured(
        prompt=user_prompt,
        response_model=response_model,
        system_prompt=system_prompt,
        temperature=0.3,
        max_tokens=2000,
    )

    logger.info(
        f"Rubric evaluated | "
        f"question_type={question_type.value} | "
        f"scores: correctness={result.correctness} completeness={result.completeness} "
        f"reasoning={result.reasoning} depth={result.depth} delivery={result.delivery}"
    )

    return {
        "rubric_result": result,
        "current_step": "rubric_evaluator",
    }