"""새 토픽 질문 생성 품질 Rule-based Evaluator

확정적으로 판단 가능한 구조적 규칙만 검증한다.
쿠션어 품질, 질문 형식, 카테고리 적합성 등 의미적 판단은 LLM-as-Judge에서 평가한다.

Item-level evaluators:
    - question_length_check    : 쿠션어·질문 텍스트 길이 적절성 (0.0-1.0, 2개 규칙)

Run-level evaluators:
    - question_length_pass_rate: length compliance 평균 & 통과율
"""

from langfuse import Evaluation


# ---------------------------------------------------------------------------
# Rule Definitions
# ---------------------------------------------------------------------------

CUSHION_LENGTH_RANGE = (10, 60)
QUESTION_LENGTH_RANGE = (20, 200)


# ---------------------------------------------------------------------------
# Item-level evaluators
# ---------------------------------------------------------------------------

def question_length_check(*, output, **kwargs):
    """쿠션어·질문 텍스트 길이 적절성 (0.0-1.0, 2개 규칙)

    쿠션어: 10-50자
    질문:   20-150자
    """
    cushion = output.get("cushion_text", "")
    question = output.get("question_text", "")
    violations: list[str] = []

    c_len = len(cushion)
    c_lo, c_hi = CUSHION_LENGTH_RANGE
    if c_len < c_lo:
        violations.append(f"쿠션어 너무 짧음({c_len}자<{c_lo})")
    elif c_len > c_hi:
        violations.append(f"쿠션어 너무 김({c_len}자>{c_hi})")

    q_len = len(question)
    q_lo, q_hi = QUESTION_LENGTH_RANGE
    if q_len < q_lo:
        violations.append(f"질문 너무 짧음({q_len}자<{q_lo})")
    elif q_len > q_hi:
        violations.append(f"질문 너무 김({q_len}자>{q_hi})")

    total_checks = 2
    score = round((total_checks - len(violations)) / total_checks, 2)
    info = f"cushion={c_len}자 question={q_len}자"
    comment = f"{info} | PASS" if not violations else f"{info} | " + " | ".join(violations)

    return Evaluation(name="question_length_check", value=score, comment=comment)


all_item_evaluators = [
    question_length_check,
]


# ---------------------------------------------------------------------------
# Run-level evaluators
# ---------------------------------------------------------------------------

def _run_level_metric(name: str, eval_fn, *, item_results):
    """공통 Run-level 집계: 평균 score + 완전 통과율(score==1.0)"""
    scores: list[float] = []
    for r in item_results:
        if not r.output:
            continue
        ev = eval_fn(output=r.output)
        if ev.value is not None:
            scores.append(ev.value)

    if not scores:
        return Evaluation(name=name, value=None, comment="No data")

    n = len(scores)
    avg = sum(scores) / n
    perfect = sum(1 for s in scores if s >= 1.0)

    return Evaluation(
        name=name,
        value=round(avg, 3),
        comment=f"avg={avg:.3f} | perfect={perfect}/{n} ({perfect / n:.0%})",
    )


def question_length_pass_rate(*, item_results, **kwargs):
    return _run_level_metric(
        "question_length_pass_rate", question_length_check,
        item_results=item_results,
    )


all_run_evaluators = [
    question_length_pass_rate,
]
