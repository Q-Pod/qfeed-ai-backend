"""꼬리질문 생성 품질 Rule-based Evaluator

prompts/follow_up.py(vllm) 기준으로 확정적으로 검증 가능한 글자 수만 검증한다.
- 쿠션어: 30자 이내
- 꼬리질문(question_text): 30자~80자

의미적 품질(맥락 유지, 1-Concept Rule 등)은 LLM-as-Judge에서 평가한다.

Item-level evaluators:
    - follow_up_length_check: 쿠션어·질문 글자 수 적절성 (0.0-1.0, 2개 규칙)

Run-level evaluators:
    - follow_up_length_pass_rate: length compliance 평균 & 통과율
"""

from langfuse import Evaluation


# ---------------------------------------------------------------------------
# Rule Definitions (follow_up.py vllm 기준)
# ---------------------------------------------------------------------------

CUSHION_MAX_CHARS = 50
QUESTION_MIN_CHARS = 50
QUESTION_MAX_CHARS = 150


# ---------------------------------------------------------------------------
# Item-level evaluators
# ---------------------------------------------------------------------------

def follow_up_length_check(*, output, **kwargs):
    """쿠션어·꼬리질문 글자 수 적절성 (0.0-1.0, 2개 규칙)

    쿠션어: 30자 이내
    꼬리질문: 30자~80자
    """
    cushion = output.get("cushion_text", "")
    question = output.get("question_text", "")
    violations: list[str] = []

    c_len = len(cushion)
    if c_len > CUSHION_MAX_CHARS:
        violations.append(f"쿠션어 초과({c_len}자 > {CUSHION_MAX_CHARS}자)")

    q_len = len(question)
    if q_len < QUESTION_MIN_CHARS:
        violations.append(f"질문 짧음({q_len}자 < {QUESTION_MIN_CHARS}자)")
    elif q_len > QUESTION_MAX_CHARS:
        violations.append(f"질문 초과({q_len}자 > {QUESTION_MAX_CHARS}자)")

    total_checks = 2
    score = round((total_checks - len(violations)) / total_checks, 2)
    info = f"cushion={c_len}자 question={q_len}자"
    comment = f"{info} | PASS" if not violations else f"{info} | " + " | ".join(violations)

    return Evaluation(name="follow_up_length_check", value=score, comment=comment)


all_item_evaluators = [
    follow_up_length_check,
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


def follow_up_length_pass_rate(*, item_results, **kwargs):
    return _run_level_metric(
        "follow_up_length_pass_rate",
        follow_up_length_check,
        item_results=item_results,
    )


all_run_evaluators = [
    follow_up_length_pass_rate,
]
