# services/rubric_scorer.py

"""Rule-based 루브릭 점수 산출기

router_analyses (매 턴의 분석 결과)를 집계하여 루브릭 점수를 산출한다.
topic_summaries는 루브릭 산출에 사용하지 않음 (피드백 텍스트 생성 전용).

실전모드에서만 사용:
    - 포트폴리오: evidence, tradeoff, problem_solving, depth, delivery
    - CS: correctness, completeness, reasoning, depth, delivery

연습모드는 LLM rubric_evaluator를 그대로 사용한다.
"""

from schemas.feedback_v2 import (
    RouterAnalysisTurn,
    PortfolioRubricScores,
    CSRubricScores,
)
from core.logging import get_logger

logger = get_logger(__name__)


# ============================================================
# 포트폴리오 루브릭 scorer
# ============================================================

def score_portfolio_rubric(
    router_analyses: list[RouterAnalysisTurn],
) -> PortfolioRubricScores:
    """포트폴리오 실전모드 루브릭 점수 산출

    매 턴의 router_analysis bool 값을 집계하여 비율 → 점수로 변환.
    메인 질문에서 부족해도 꼬리질문에서 보완하면 비율에 자연스럽게 반영됨.
    """

    total = len(router_analyses)

    if total == 0:
        logger.warning("Empty router_analyses, returning minimum scores")
        return PortfolioRubricScores(
            evidence=1, tradeoff=1, problem_solving=1, depth=1, delivery=1
        )

    evidence_rate = _true_rate(router_analyses, "has_evidence")
    tradeoff_rate = _true_rate(router_analyses, "has_tradeoff")
    ps_rate = _true_rate(router_analyses, "has_problem_solving")
    delivery_rate = _true_rate(router_analyses, "is_well_structured")

    # depth: 포트폴리오는 별도 depth 필드가 없으므로
    # evidence + problem_solving 조합으로 추정
    # 둘 다 true인 턴 = 깊이 있는 답변으로 간주
    depth_rate = _combined_true_rate(
        router_analyses, "has_evidence", "has_problem_solving"
    )

    scores = PortfolioRubricScores(
        evidence=_rate_to_score(evidence_rate),
        tradeoff=_rate_to_score(tradeoff_rate),
        problem_solving=_rate_to_score(ps_rate),
        depth=_rate_to_score(depth_rate),
        delivery=_rate_to_score(delivery_rate),
    )

    logger.info(
        f"Portfolio rubric scored | "
        f"turns={total} | "
        f"evidence={scores.evidence} tradeoff={scores.tradeoff} "
        f"problem_solving={scores.problem_solving} depth={scores.depth} "
        f"delivery={scores.delivery}"
    )

    return scores


# ============================================================
# CS 루브릭 scorer
# ============================================================

def score_cs_rubric(
    router_analyses: list[RouterAnalysisTurn],
) -> CSRubricScores:
    """CS 실전모드 루브릭 점수 산출

    매 턴의 router_analysis bool 값을 집계하여 비율 → 점수로 변환.
    """

    total = len(router_analyses)

    if total == 0:
        logger.warning("Empty router_analyses, returning minimum scores")
        return CSRubricScores(
            correctness=1, completeness=1, reasoning=1, depth=1, delivery=1
        )

    # correctness: 오류가 없는 비율 (has_error True → 나쁨, 반전)
    error_free_rate = _false_rate(router_analyses, "has_error")

    # completeness: 핵심 개념 누락이 없는 비율 (반전)
    complete_rate = _false_rate(router_analyses, "has_missing_concepts")

    # reasoning: "reasoning" 꼬리질문이 나오지 않은 비율
    # reasoning 방향 꼬리질문 = "왜를 설명 못 해서" → 많을수록 나쁨
    reasoning_needed = sum(
        1 for r in router_analyses
        if r.follow_up_direction == "reasoning"
    ) / total
    reasoning_rate = 1.0 - reasoning_needed

    # depth: 표면적이지 않은 비율 (is_superficial True → 나쁨, 반전)
    deep_rate = _false_rate(router_analyses, "is_superficial")

    # delivery: 구조화된 전달
    delivery_rate = _true_rate(router_analyses, "is_well_structured")

    scores = CSRubricScores(
        correctness=_rate_to_score(error_free_rate),
        completeness=_rate_to_score(complete_rate),
        reasoning=_rate_to_score(reasoning_rate),
        depth=_rate_to_score(deep_rate),
        delivery=_rate_to_score(delivery_rate),
    )

    logger.info(
        f"CS rubric scored | "
        f"turns={total} | "
        f"correctness={scores.correctness} completeness={scores.completeness} "
        f"reasoning={scores.reasoning} depth={scores.depth} "
        f"delivery={scores.delivery}"
    )

    return scores


# ============================================================
# 헬퍼 함수
# ============================================================

def _true_rate(analyses: list[RouterAnalysisTurn], field: str) -> float:
    """특정 bool 필드가 True인 비율 (None은 제외)"""
    values = [getattr(r, field) for r in analyses if getattr(r, field) is not None]
    if not values:
        return 0.0
    return sum(1 for v in values if v) / len(values)


def _false_rate(analyses: list[RouterAnalysisTurn], field: str) -> float:
    """특정 bool 필드가 False인 비율 (None은 제외)

    has_error, has_missing_concepts, is_superficial처럼
    True일수록 나쁜 지표에 사용.
    """
    values = [getattr(r, field) for r in analyses if getattr(r, field) is not None]
    if not values:
        return 0.0
    return sum(1 for v in values if not v) / len(values)


def _combined_true_rate(
    analyses: list[RouterAnalysisTurn],
    field_a: str,
    field_b: str,
) -> float:
    """두 bool 필드가 모두 True인 비율 (둘 다 None이 아닌 턴만)"""
    valid = [
        r for r in analyses
        if getattr(r, field_a) is not None and getattr(r, field_b) is not None
    ]
    if not valid:
        return 0.0
    return sum(
        1 for r in valid
        if getattr(r, field_a) and getattr(r, field_b)
    ) / len(valid)


def _rate_to_score(rate: float) -> int:
    """비율(0.0~1.0)을 1-5 점수로 변환"""
    if rate >= 0.8:
        return 5
    if rate >= 0.6:
        return 4
    if rate >= 0.4:
        return 3
    if rate >= 0.2:
        return 2
    return 1