"""LLM-as-Judge 꼬리질문(follow_up) 품질 평가

Judge 모델(예: Claude)을 사용하여 꼬리질문의 의미적 품질을 평가한다.
prompts/follow_up.py 기준: 맥락 유지, 1-Concept Rule, 기술적 정확성, 쿠션어 품질.

Item-level evaluators:
    - follow_up_context       : 맥락 유지 (1-5)
    - follow_up_one_concept    : 1-Concept Rule (1-5)
    - follow_up_technical_fact : 기술적 전제 정확성 (1-5)
    - follow_up_cushion        : 쿠션어 품질 (1-5)

Run-level evaluators:
    - follow_up_context_avg, follow_up_one_concept_avg, ...
    - follow_up_quality_score : 가중 종합 (0-5)
    - follow_up_diversity     : 질문 다양성 (1-5, Run-level)
"""

import hashlib
import json
import os
from typing import Any, Dict

import anthropic
from langfuse import Evaluation

from tests.evaluation.prompts.follow_up_judge_prompts import (
    FOLLOW_UP_CONTEXT_SYSTEM,
    FOLLOW_UP_ONE_CONCEPT_SYSTEM,
    FOLLOW_UP_TECHNICAL_FACTUAL_SYSTEM,
    FOLLOW_UP_CUSHION_SYSTEM,
    FOLLOW_UP_DIVERSITY_SYSTEM,
    build_context_user_prompt,
    build_one_concept_user_prompt,
    build_technical_factual_user_prompt,
    build_cushion_user_prompt,
    build_follow_up_diversity_user_prompt,
)


_raw_model = os.getenv("JUDGE_MODEL", "claude-sonnet-4-5-20250929")
JUDGE_MODEL = _raw_model.removeprefix("anthropic/")

_client: anthropic.Anthropic | None = None
_eval_cache: Dict[str, Evaluation] = {}


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY 환경변수가 설정되어 있지 않습니다.")
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def _output_hash(output: Dict[str, Any]) -> str:
    """cushion_text + question_text 조합으로 캐시 키 생성"""
    cushion = (output.get("cushion_text") or "").strip()
    question = (output.get("question_text") or "").strip()
    key = cushion + "\n" + question
    return hashlib.md5(key.encode("utf-8")).hexdigest()


def _extract_json(text: str) -> dict:
    """응답 텍스트에서 JSON 객체를 추출한다."""
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start : end + 1])
    raise json.JSONDecodeError("No JSON object found", text, 0)


def _call_judge(system: str, user_msg: str) -> dict:
    """Judge 모델 호출 후 JSON 응답 파싱"""
    try:
        client = _get_client()
        response = client.messages.create(
            model=JUDGE_MODEL,
            max_tokens=512,
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
        print(f"[follow_up_judge ERROR] {type(e).__name__}: {e}")
        return {"error": f"{type(e).__name__}: {e}"}


def _evaluate_with_judge(name: str, system: str, user_prompt: str) -> Evaluation:
    result = _call_judge(system, user_prompt)

    if "error" in result:
        return Evaluation(name=name, value=0, comment=f"Judge 호출 실패: {result['error']}")

    score = result.get("score")
    reasoning = result.get("reasoning", "")

    if not isinstance(score, (int, float)) or not (1 <= score <= 5):
        return Evaluation(
            name=name,
            value=0,
            comment=f"유효하지 않은 score: {score} | {reasoning}",
        )

    return Evaluation(name=name, value=float(score), comment=reasoning)


# ---------------------------------------------------------------------------
# Item-level evaluators (with caching)
# ---------------------------------------------------------------------------


def follow_up_context(*, output, **kwargs):
    """맥락 유지 (1-5)"""
    cache_key = f"fu-ctx:{_output_hash(output)}"
    if cache_key in _eval_cache:
        return _eval_cache[cache_key]

    question_text = (output.get("question_text") or "").strip()
    if not question_text:
        ev = Evaluation(name="follow_up_context", value=0, comment="question_text 없음 (skip)")
        _eval_cache[cache_key] = ev
        return ev

    user_prompt = build_context_user_prompt(
        question_type=output.get("question_type") or "",
        category=output.get("category"),
        cushion_text=(output.get("cushion_text") or "").strip(),
        question_text=question_text,
        interview_history=output.get("interview_history") or [],
    )
    ev = _evaluate_with_judge("follow_up_context", FOLLOW_UP_CONTEXT_SYSTEM, user_prompt)
    _eval_cache[cache_key] = ev
    return ev


def follow_up_one_concept(*, output, **kwargs):
    """1-Concept Rule (1-5)"""
    cache_key = f"fu-1c:{_output_hash(output)}"
    if cache_key in _eval_cache:
        return _eval_cache[cache_key]

    question_text = (output.get("question_text") or "").strip()
    if not question_text:
        ev = Evaluation(name="follow_up_one_concept", value=0, comment="question_text 없음 (skip)")
        _eval_cache[cache_key] = ev
        return ev

    user_prompt = build_one_concept_user_prompt(
        output.get("question_type") or "",
        question_text,
    )
    ev = _evaluate_with_judge(
        "follow_up_one_concept",
        FOLLOW_UP_ONE_CONCEPT_SYSTEM,
        user_prompt,
    )
    _eval_cache[cache_key] = ev
    return ev


def follow_up_technical_fact(*, output, **kwargs):
    """기술적 전제 정확성 (1-5)"""
    cache_key = f"fu-tf:{_output_hash(output)}"
    if cache_key in _eval_cache:
        return _eval_cache[cache_key]

    question_text = (output.get("question_text") or "").strip()
    if not question_text:
        ev = Evaluation(
            name="follow_up_technical_fact",
            value=0,
            comment="question_text 없음 (skip)",
        )
        _eval_cache[cache_key] = ev
        return ev

    user_prompt = build_technical_factual_user_prompt(
        output.get("question_type") or "",
        question_text,
    )
    ev = _evaluate_with_judge(
        "follow_up_technical_fact",
        FOLLOW_UP_TECHNICAL_FACTUAL_SYSTEM,
        user_prompt,
    )
    _eval_cache[cache_key] = ev
    return ev


def follow_up_cushion(*, output, **kwargs):
    """쿠션어 품질 (1-5)"""
    cache_key = f"fu-cushion:{_output_hash(output)}"
    if cache_key in _eval_cache:
        return _eval_cache[cache_key]

    cushion_text = (output.get("cushion_text") or "").strip()
    question_text = (output.get("question_text") or "").strip()
    if not cushion_text:
        ev = Evaluation(
            name="follow_up_cushion",
            value=0,
            comment="cushion_text 없음 (skip)",
        )
        _eval_cache[cache_key] = ev
        return ev

    user_prompt = build_cushion_user_prompt(
        cushion_text,
        question_text,
        output.get("interview_history") or [],
    )
    ev = _evaluate_with_judge(
        "follow_up_cushion",
        FOLLOW_UP_CUSHION_SYSTEM,
        user_prompt,
    )
    _eval_cache[cache_key] = ev
    return ev


all_item_evaluators = [
    follow_up_context,
    follow_up_one_concept,
    follow_up_technical_fact,
    follow_up_cushion,
]


# ---------------------------------------------------------------------------
# Run-level evaluators
# ---------------------------------------------------------------------------


def _run_avg(name: str, eval_fn, *, item_results) -> Evaluation:
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
    dist = {i: sum(1 for s in scores if int(s) == i) for i in range(1, 6)}
    dist_str = " | ".join(f"{k}점:{v}건" for k, v in dist.items() if v > 0)

    return Evaluation(
        name=name,
        value=round(avg, 2),
        comment=f"avg={avg:.2f}/5.0 | n={n} | {dist_str}",
    )


def follow_up_context_avg(*, item_results, **kwargs):
    return _run_avg("follow_up_context_avg", follow_up_context, item_results=item_results)


def follow_up_one_concept_avg(*, item_results, **kwargs):
    return _run_avg(
        "follow_up_one_concept_avg",
        follow_up_one_concept,
        item_results=item_results,
    )


def follow_up_technical_fact_avg(*, item_results, **kwargs):
    return _run_avg(
        "follow_up_technical_fact_avg",
        follow_up_technical_fact,
        item_results=item_results,
    )


def follow_up_cushion_avg(*, item_results, **kwargs):
    return _run_avg("follow_up_cushion_avg", follow_up_cushion, item_results=item_results)


def follow_up_quality_score(*, item_results, **kwargs):
    """가중 종합 점수:
    - 맥락 유지: 0.30
    - 1-Concept: 0.30
    - 기술적 정확성: 0.25
    - 쿠션어: 0.15
    """
    composites: list[float] = []
    for r in item_results:
        if not r.output:
            continue

        ctx = follow_up_context(output=r.output)
        one = follow_up_one_concept(output=r.output)
        tech = follow_up_technical_fact(output=r.output)
        csh = follow_up_cushion(output=r.output)

        if any(e.value is None or e.value == 0 for e in [ctx, one, tech, csh]):
            continue

        score = (
            ctx.value * 0.30
            + one.value * 0.30
            + tech.value * 0.25
            + csh.value * 0.15
        )
        composites.append(round(score, 2))

    if not composites:
        return Evaluation(
            name="follow_up_quality_score",
            value=0,
            comment="유효한 결과 없음",
        )

    n = len(composites)
    avg = sum(composites) / n
    return Evaluation(
        name="follow_up_quality_score",
        value=round(avg, 2),
        comment=(
            f"weighted_avg={avg:.2f}/5.0 | n={n} | "
            "weights: Context=0.30 OneConcept=0.30 Technical=0.25 Cushion=0.15"
        ),
    )


_MAX_QUESTIONS_FOR_DIVERSITY = 30


def follow_up_diversity(*, item_results, **kwargs) -> Evaluation:
    """Run-level: 생성된 꼬리질문들의 다양성(1-5)을 LLM-as-Judge로 평가."""
    question_texts = []
    for r in item_results:
        if not r.output:
            continue
        q = (r.output.get("question_text") or "").strip()
        if q:
            question_texts.append(q)

    total_count = len(question_texts)
    if total_count < 2:
        return Evaluation(
            name="follow_up_diversity",
            value=0,
            comment="질문이 2개 미만이라 다양성 평가 불가",
        )

    if total_count > _MAX_QUESTIONS_FOR_DIVERSITY:
        step = total_count / _MAX_QUESTIONS_FOR_DIVERSITY
        indices = [int(i * step) for i in range(_MAX_QUESTIONS_FOR_DIVERSITY)]
        question_texts = [question_texts[i] for i in indices]

    user_prompt = build_follow_up_diversity_user_prompt(question_texts)
    result = _call_judge(FOLLOW_UP_DIVERSITY_SYSTEM, user_prompt)

    if "error" in result:
        return Evaluation(
            name="follow_up_diversity",
            value=0,
            comment=f"Judge 호출 실패: {result['error']}",
        )

    score = result.get("score")
    reasoning = result.get("reasoning", "")

    if not isinstance(score, (int, float)) or not (1 <= score <= 5):
        return Evaluation(
            name="follow_up_diversity",
            value=0,
            comment=f"유효하지 않은 score: {score} | {reasoning}",
        )

    used = len(question_texts)
    return Evaluation(
        name="follow_up_diversity",
        value=float(score),
        comment=f"n={total_count} (평가에 사용 {used}개) | {reasoning}",
    )


all_run_evaluators = [
    follow_up_context_avg,
    follow_up_one_concept_avg,
    follow_up_technical_fact_avg,
    follow_up_cushion_avg,
    follow_up_quality_score,
    follow_up_diversity,
]
