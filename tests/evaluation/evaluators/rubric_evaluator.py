"""루브릭 점수 평가용 Evaluator 함수들

Item-level evaluators:
    - rubric_{dim}_score    : 각 차원별 실제 점수 기록 (Langfuse 시각화용)
    - rubric_{dim}_error    : 각 차원별 |actual - expected| 절대 오차
    - rubric_avg_score      : 평균 점수 기록

Run-level evaluators:
    - dimension_mae         : 차원별 Mean Absolute Error + 전체 평균
    - dimension_spearman    : 차원별 Spearman 순위 상관계수
    - dimension_cross_corr  : 차원 간 Spearman 상관계수 (후광효과 검증)
"""

from langfuse import Evaluation
from scipy.stats import spearmanr

RUBRIC_DIMENSIONS = ["accuracy", "logic", "specificity", "completeness", "delivery"]


# ---------------------------------------------------------------------------
# Item-level evaluators
# ---------------------------------------------------------------------------

def _create_score_reporter(dim: str):
    """특정 루브릭 차원의 실제 점수를 Langfuse에 기록하는 evaluator"""

    def evaluator(*, output, **kwargs):
        return Evaluation(
            name=f"rubric_{dim}",
            value=float(output[dim]),
        )

    evaluator.__name__ = f"rubric_{dim}_score"
    return evaluator


def _create_error_reporter(dim: str):
    """특정 루브릭 차원의 절대 오차(|actual - expected|)를 기록하는 evaluator"""

    def evaluator(*, output, expected_output, **kwargs):
        actual = output[dim]
        expected = expected_output.get("rubric_expectations", {}).get(dim)

        if expected is None:
            return Evaluation(name=f"rubric_{dim}_error", value=None)

        error = abs(actual - expected)
        return Evaluation(
            name=f"rubric_{dim}_error",
            value=round(error, 2),
            comment=f"{dim}: actual={actual}, expected={expected}, error={error:.2f}",
        )

    evaluator.__name__ = f"rubric_{dim}_error"
    return evaluator


def rubric_avg_score(*, output, **kwargs):
    """평균 루브릭 점수를 Langfuse에 기록"""
    return Evaluation(
        name="rubric_avg",
        value=round(output["average"], 2),
    )


rubric_score_reporters = [_create_score_reporter(d) for d in RUBRIC_DIMENSIONS]
rubric_error_reporters = [_create_error_reporter(d) for d in RUBRIC_DIMENSIONS]

all_item_evaluators = [
    *rubric_score_reporters,
    *rubric_error_reporters,
    rubric_avg_score,
]


# ---------------------------------------------------------------------------
# Run-level evaluators (전체 실험 결과 집계)
# ---------------------------------------------------------------------------

def dimension_mae(*, item_results, **kwargs):
    """차원별 MAE + 전체 평균 MAE

    각 차원에 대해 모든 케이스의 |actual - expected| 평균을 계산한다.
    최종 value는 전체 차원의 MAE 평균이다.
    """
    dim_errors: dict[str, list[int]] = {d: [] for d in RUBRIC_DIMENSIONS}

    for r in item_results:
        expected = (
            r.item.expected_output
            if hasattr(r.item, "expected_output")
            else r.item.get("expected_output")
        )
        if not r.output or not expected:
            continue

        rubric_exp = expected.get("rubric_expectations", {})
        for d in RUBRIC_DIMENSIONS:
            exp_val = rubric_exp.get(d)
            if exp_val is not None:
                actual_val = r.output.get(d, 0)
                dim_errors[d].append(abs(actual_val - exp_val))

    lines = []
    dim_maes = []
    for d in RUBRIC_DIMENSIONS:
        errs = dim_errors[d]
        if errs:
            mae = sum(errs) / len(errs)
            dim_maes.append(mae)
            lines.append(f"{d}: MAE={mae:.3f} (n={len(errs)})")

    overall_mae = round(sum(dim_maes) / len(dim_maes), 3) if dim_maes else 0.0

    return Evaluation(
        name="dimension_mae",
        value=overall_mae,
        comment=" | ".join(lines),
    )


def _spearman_correlation(x: list[float], y: list[float]) -> float | None:
    """Spearman 순위 상관계수 계산"""
    if len(x) < 3:
        return None
    rho, _ = spearmanr(x, y)
    return rho


def dimension_spearman(*, item_results, **kwargs):
    """차원별 Spearman 순위 상관계수

    각 차원에 대해 모든 케이스의 (expected, actual) 쌍으로
    Spearman 상관계수를 계산한다.
    최종 value는 전체 차원의 Spearman 평균이다.
    """
    dim_expected: dict[str, list[float]] = {d: [] for d in RUBRIC_DIMENSIONS}
    dim_actual: dict[str, list[float]] = {d: [] for d in RUBRIC_DIMENSIONS}

    for r in item_results:
        expected = (
            r.item.expected_output
            if hasattr(r.item, "expected_output")
            else r.item.get("expected_output")
        )
        if not r.output or not expected:
            continue

        rubric_exp = expected.get("rubric_expectations", {})
        for d in RUBRIC_DIMENSIONS:
            exp_val = rubric_exp.get(d)
            if exp_val is not None:
                dim_expected[d].append(exp_val)
                dim_actual[d].append(r.output.get(d, 0))

    lines = []
    spearmans = []
    for d in RUBRIC_DIMENSIONS:
        rho = _spearman_correlation(dim_expected[d], dim_actual[d])
        if rho is not None:
            spearmans.append(rho)
            lines.append(f"{d}: ρ={rho:.3f} (n={len(dim_expected[d])})")
        else:
            lines.append(f"{d}: N/A (insufficient data)")

    avg_rho = round(sum(spearmans) / len(spearmans), 3) if spearmans else None

    return Evaluation(
        name="dimension_spearman",
        value=avg_rho,
        comment=" | ".join(lines),
    )


def dimension_bias(*, item_results, **kwargs):
    """차원별 편향(Bias) 분석

    각 차원에 대해 (actual - expected)의 평균을 계산한다.
      - 양수: LLM이 사람보다 후하게 채점 (over-scoring)
      - 음수: LLM이 사람보다 엄격하게 채점 (under-scoring)

    comment에는 차원별 bias, over/under/exact 건수, 점수별 분포를 포함한다.
    """
    dim_diffs: dict[str, list[int]] = {d: [] for d in RUBRIC_DIMENSIONS}

    for r in item_results:
        expected = (
            r.item.expected_output
            if hasattr(r.item, "expected_output")
            else r.item.get("expected_output")
        )
        if not r.output or not expected:
            continue

        rubric_exp = expected.get("rubric_expectations", {})
        for d in RUBRIC_DIMENSIONS:
            exp_val = rubric_exp.get(d)
            if exp_val is not None:
                actual_val = r.output.get(d, 0)
                dim_diffs[d].append(actual_val - exp_val)

    lines = []
    all_biases = []
    for d in RUBRIC_DIMENSIONS:
        diffs = dim_diffs[d]
        if not diffs:
            continue
        mean_bias = sum(diffs) / len(diffs)
        all_biases.append(mean_bias)
        over = sum(1 for x in diffs if x > 0)
        under = sum(1 for x in diffs if x < 0)
        exact = sum(1 for x in diffs if x == 0)
        direction = "↑후하게" if mean_bias > 0 else ("↓엄격하게" if mean_bias < 0 else "=정확")
        lines.append(
            f"{d}: bias={mean_bias:+.2f}({direction}) "
            f"[over={over}/under={under}/exact={exact}]"
        )

    overall_bias = round(sum(all_biases) / len(all_biases), 3) if all_biases else 0.0

    return Evaluation(
        name="dimension_bias",
        value=overall_bias,
        comment=" | ".join(lines),
    )


def dimension_cross_correlation(*, item_results, **kwargs):
    """차원 간 Spearman 상관계수 (Cross-correlation)

    LLM이 매긴 실제 점수를 기준으로, 모든 차원 쌍(C(5,2)=10쌍)의
    Spearman 상관계수를 계산한다.

    활용:
      - 후광효과(Halo Effect) 검증: 평균 cross-corr이 지나치게 높으면(>0.85)
        LLM이 차원을 구분하지 못하고 일괄적으로 점수를 매기는 경향
      - 루브릭 독립성 검증: 특정 차원 쌍이 항상 동일한 패턴이면
        루브릭 설계 자체에 중복이 있을 가능성
    """
    dim_scores: dict[str, list[float]] = {d: [] for d in RUBRIC_DIMENSIONS}

    for r in item_results:
        if not r.output:
            continue
        for d in RUBRIC_DIMENSIONS:
            dim_scores[d].append(r.output.get(d, 0))

    pair_lines = []
    pair_rhos = []

    for i, dim_a in enumerate(RUBRIC_DIMENSIONS):
        for dim_b in RUBRIC_DIMENSIONS[i + 1:]:
            rho = _spearman_correlation(dim_scores[dim_a], dim_scores[dim_b])
            if rho is not None:
                pair_rhos.append(rho)
                pair_lines.append(f"{dim_a}-{dim_b}: {rho:.3f}")

    avg_cross = round(sum(pair_rhos) / len(pair_rhos), 3) if pair_rhos else None

    halo_warning = ""
    if avg_cross is not None and avg_cross > 0.85:
        halo_warning = " ⚠ 후광효과 의심 (avg > 0.85)"

    return Evaluation(
        name="dimension_cross_corr",
        value=avg_cross,
        comment=" | ".join(pair_lines) + halo_warning,
    )


all_run_evaluators = [
    dimension_mae,
    dimension_spearman,
    dimension_bias,
    dimension_cross_correlation,
]
