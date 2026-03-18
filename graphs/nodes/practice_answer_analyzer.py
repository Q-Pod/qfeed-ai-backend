from langfuse import observe

from core.dependencies import get_llm_provider
from core.logging import get_logger
from graphs.feedback.state import FeedbackGraphState
from prompts.practice_answer_analysis import (
    build_practice_answer_analysis_prompt,
    get_practice_analysis_system_prompt,
)
from schemas.feedback import QuestionType
from schemas.feedback_v2 import RouterAnalysisTurn
from schemas.question import CSAnswerAnalysis, PortfolioAnswerAnalysis

logger = get_logger(__name__)


@observe(name="practice_answer_analyzer", as_type="generation")
async def practice_answer_analyzer(state: FeedbackGraphState) -> dict:
    question_type = state["question_type"]
    llm = get_llm_provider("gemini")

    prompt = build_practice_answer_analysis_prompt(
        question_type=question_type,
        interview_history=state["interview_history"],
        category=state.get("category"),
    )
    system_prompt = get_practice_analysis_system_prompt(question_type)
    response_model = (
        PortfolioAnswerAnalysis
        if question_type == QuestionType.PORTFOLIO
        else CSAnswerAnalysis
    )

    result = await llm.generate_structured(
        prompt=prompt,
        response_model=response_model,
        system_prompt=system_prompt,
        temperature=0.0,
        max_tokens=1200,
    )

    last_turn = state["interview_history"][-1]
    router_analysis = _to_router_analysis_turn(
        question_type=question_type,
        turn=last_turn,
        analysis=result.model_dump(),
    )

    logger.info(
        "Practice answer analyzed | question_type=%s | topic_id=%s | turn_order=%s",
        question_type.value,
        last_turn.topic_id,
        last_turn.turn_order,
    )

    return {
        "router_analyses": [router_analysis],
        "current_step": "practice_answer_analyzer",
    }


def _to_router_analysis_turn(
    *,
    question_type: QuestionType,
    turn,
    analysis: dict,
) -> RouterAnalysisTurn:
    base = {
        "topic_id": turn.topic_id,
        "turn_order": turn.turn_order,
        "turn_type": turn.turn_type,
        "is_well_structured": analysis.get("is_well_structured"),
        "follow_up_direction": None,
    }

    if question_type == QuestionType.PORTFOLIO:
        return RouterAnalysisTurn(
            **base,
            completeness_detail=analysis.get("completeness"),
            has_evidence=analysis.get("has_evidence"),
            has_tradeoff=analysis.get("has_tradeoff"),
            has_problem_solving=analysis.get("has_problem_solving"),
        )

    return RouterAnalysisTurn(
        **base,
        correctness_detail=analysis.get("correctness"),
        has_error=analysis.get("has_error"),
        completeness_cs_detail=analysis.get("completeness"),
        has_missing_concepts=analysis.get("has_missing_concepts"),
        depth_detail=analysis.get("depth"),
        is_superficial=analysis.get("is_superficial"),
    )
