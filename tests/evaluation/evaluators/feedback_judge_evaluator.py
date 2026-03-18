"""LLM-as-Judge 피드백 품질 평가 (Stage 2)

Claude를 Judge 모델로 사용하여 피드백의 의미적 품질을 평가한다.
각 지표는 독립적인 관점만 평가하며 서로 겹치지 않는다.

Item-level evaluators:
    - priority_compliance  : 보완점 배치 순서 + 불필요 항목 여부 (1-5)
    - factual_correctness  : 피드백 기술적 정확성 / hallucination (1-5)
    - actionability        : 보완점 구체성 / 실행 가능성 (1-5)

Run-level evaluators:
    - priority_compliance_avg  : 평균 (1-5)
    - factual_correctness_avg  : 평균 (1-5)
    - actionability_avg        : 평균 (1-5)
    - feedback_quality_score   : 가중 종합 (0-5)
"""

import hashlib
import json
import os

import anthropic
from langfuse import Evaluation

from tests.evaluation.prompts.judge_prompts import (
    ACTIONABILITY_SYSTEM,
    FACTUAL_CORRECTNESS_SYSTEM,
    PRIORITY_COMPLIANCE_SYSTEM,
    build_actionability_user_prompt,
    build_factual_user_prompt,
    build_priority_user_prompt,
)


_raw_model = os.getenv("JUDGE_MODEL", "claude-sonnet-4-5-20250929")
JUDGE_MODEL = _raw_model.removeprefix("anthropic/")

_client = None
_eval_cache: dict[str, Evaluation] = {}


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY 환경변수가 설정되어 있지 않습니다.")
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def _output_hash(output: dict) -> str:
    of = output.get("overall_feedback") or {}
    key = of.get("improvements", "") + of.get("strengths", "")
    return hashlib.md5(key.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Claude API Call
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> dict:
    """응답 텍스트에서 JSON 객체를 추출한다."""
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start:end + 1])
    raise json.JSONDecodeError("No JSON object found", text, 0)


def _call_judge(system: str, user_msg: str) -> dict:
    """Claude Judge를 호출하고 JSON 응답을 파싱하여 반환한다."""
    try:
        client = _get_client()
        response = client.messages.create(
            model=JUDGE_MODEL,
            max_tokens=1024,
            temperature=0.0,
            system=[
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_msg}],
        )
        text = response.content[0].text.strip()
        return _extract_json(text)
    except Exception as e:
        print(f"[Judge ERROR] {type(e).__name__}: {e}")
        return {"error": f"{type(e).__name__}: {e}"}


def _evaluate_with_judge(name: str, system: str, user_prompt: str) -> Evaluation:
    """공통 Judge 평가 로직: API 호출 → score/reasoning 파싱 → Evaluation 반환"""
    result = _call_judge(system, user_prompt)

    if "error" in result:
        return Evaluation(name=name, value=0, comment=f"Judge 호출 실패: {result['error']}")

    score = result.get("score")
    reasoning = result.get("reasoning", "")

    if not isinstance(score, (int, float)) or not (1 <= score <= 5):
        return Evaluation(name=name, value=0, comment=f"유효하지 않은 score: {score} | {reasoning}")

    return Evaluation(name=name, value=float(score), comment=reasoning)


# ---------------------------------------------------------------------------
# Item-level evaluators (with caching for run-level reuse)
# ---------------------------------------------------------------------------

def priority_compliance(*, output, **kwargs):
    """보완점 배치 순서 + 불필요 항목 여부 (1-5)"""
    cache_key = f"pc:{_output_hash(output)}"
    if cache_key in _eval_cache:
        return _eval_cache[cache_key]

    of = output.get("overall_feedback") or {}
    improvements = of.get("improvements", "")
    if not improvements:
        ev = Evaluation(name="priority_compliance", value=0, comment="improvements 없음 (skip)")
        _eval_cache[cache_key] = ev
        return ev

    qa_text = output.get("qa_text", "")
    if not qa_text:
        ev = Evaluation(name="priority_compliance", value=0, comment="qa_text 없음 (skip)")
        _eval_cache[cache_key] = ev
        return ev

    user_prompt = build_priority_user_prompt(qa_text, improvements)
    ev = _evaluate_with_judge("priority_compliance", PRIORITY_COMPLIANCE_SYSTEM, user_prompt)
    _eval_cache[cache_key] = ev
    return ev


def factual_correctness(*, output, **kwargs):
    """피드백 기술적 정확성 / hallucination 검출 (1-5)"""
    cache_key = f"fc:{_output_hash(output)}"
    if cache_key in _eval_cache:
        return _eval_cache[cache_key]

    of = output.get("overall_feedback") or {}
    strengths = of.get("strengths", "")
    improvements = of.get("improvements", "")
    feedback_text = f"[강점]\n{strengths}\n\n[보완점]\n{improvements}"

    if not strengths and not improvements:
        ev = Evaluation(name="factual_correctness", value=0, comment="피드백 텍스트 없음 (skip)")
        _eval_cache[cache_key] = ev
        return ev

    qa_text = output.get("qa_text", "")
    if not qa_text:
        ev = Evaluation(name="factual_correctness", value=0, comment="qa_text 없음 (skip)")
        _eval_cache[cache_key] = ev
        return ev

    user_prompt = build_factual_user_prompt(qa_text, feedback_text)
    ev = _evaluate_with_judge("factual_correctness", FACTUAL_CORRECTNESS_SYSTEM, user_prompt)
    _eval_cache[cache_key] = ev
    return ev


def actionability(*, output, **kwargs):
    """보완점 구체성 / 실행 가능성 (1-5)"""
    cache_key = f"ac:{_output_hash(output)}"
    if cache_key in _eval_cache:
        return _eval_cache[cache_key]

    of = output.get("overall_feedback") or {}
    improvements = of.get("improvements", "")
    if not improvements:
        ev = Evaluation(name="actionability", value=0, comment="improvements 없음 (skip)")
        _eval_cache[cache_key] = ev
        return ev

    user_prompt = build_actionability_user_prompt(improvements)
    ev = _evaluate_with_judge("actionability", ACTIONABILITY_SYSTEM, user_prompt)
    _eval_cache[cache_key] = ev
    return ev


all_item_evaluators = [priority_compliance, factual_correctness, actionability]


# ---------------------------------------------------------------------------
# Run-level evaluators
# ---------------------------------------------------------------------------

def _run_avg(name: str, eval_fn, *, item_results) -> Evaluation:
    """공통 run-level 평균 집계 (캐시된 item 결과 재사용)"""
    scores: list[float] = []
    for r in item_results:
        if not r.output:
            continue
        ev = eval_fn(output=r.output)
        if ev.value is not None and ev.value > 0:
            scores.append(ev.value)

    if not scores:
        return Evaluation(name=name, value=0, comment="유효한 결과 없음")

    n = len(scores)
    avg = sum(scores) / n
    dist = {i: scores.count(float(i)) for i in range(1, 6)}
    dist_str = " | ".join(f"{k}점:{v}건" for k, v in dist.items() if v > 0)

    return Evaluation(name=name, value=round(avg, 2), comment=f"avg={avg:.2f}/5.0 | n={n} | {dist_str}")


def priority_compliance_avg(*, item_results, **kwargs):
    return _run_avg("priority_compliance_avg", priority_compliance, item_results=item_results)


def factual_correctness_avg(*, item_results, **kwargs):
    return _run_avg("factual_correctness_avg", factual_correctness, item_results=item_results)


def actionability_avg(*, item_results, **kwargs):
    return _run_avg("actionability_avg", actionability, item_results=item_results)


def feedback_quality_score(*, item_results, **kwargs):
    """가중 종합 점수: Factual(0.4) + Priority(0.3) + Actionability(0.3)
    Factual <= 2이면 quality = factual * 0.6 (사실이 틀리면 나머지 무의미)
    """
    composites: list[float] = []
    for r in item_results:
        if not r.output:
            continue
        pc = priority_compliance(output=r.output)
        fc = factual_correctness(output=r.output)
        ac = actionability(output=r.output)

        if any(e.value is None or e.value == 0 for e in [pc, fc, ac]):
            continue

        f, p, a = fc.value, pc.value, ac.value
        if f <= 2:
            score = f * 0.6
        else:
            score = f * 0.4 + p * 0.3 + a * 0.3
        composites.append(round(score, 2))

    if not composites:
        return Evaluation(name="feedback_quality_score", value=0, comment="유효한 결과 없음")

    n = len(composites)
    avg = sum(composites) / n

    return Evaluation(
        name="feedback_quality_score",
        value=round(avg, 2),
        comment=f"weighted_avg={avg:.2f}/5.0 | n={n} | weights: F=0.4 P=0.3 A=0.3",
    )


all_run_evaluators = [
    priority_compliance_avg,
    factual_correctness_avg,
    actionability_avg,
    feedback_quality_score,
]
