"""LLM-as-Judge 새 토픽(new_topic) 질문 품질 평가

Judge 모델(예: Claude)을 사용하여 new_topic 질문의 의미적 품질을 평가한다.

Item-level evaluators:
    - tradeoff_depth      : Trade-off(선택과 타협)를 얼마나 잘 묻는가? (1-5)
    - constraint_quality  : 실무적 제약 조건(Constraints)의 적절성 (1-5)
    - hook_richness       : 꼬리질문을 위한 Hook 풍부도 (1-5)
    - cushion_quality     : 쿠션어가 면접 UX를 얼마나 잘 만드는가 (1-5)

Run-level evaluators:
    - tradeoff_depth_avg      : 평균 (1-5)
    - constraint_quality_avg  : 평균 (1-5)
    - hook_richness_avg       : 평균 (1-5)
    - cushion_quality_avg     : 평균 (1-5)
    - new_topic_quality_score : 가중 종합 (0-5)
    - new_topic_diversity      : 질문 다양성 (1-5, Run-level)
"""

import hashlib
import json
import os
from typing import Dict, Any

import anthropic
from langfuse import Evaluation

from tests.evaluation.prompts.new_topic_judge_prompts import (
    NEW_TOPIC_TRADEOFF_SYSTEM,
    NEW_TOPIC_CONSTRAINT_SYSTEM,
    NEW_TOPIC_HOOK_SYSTEM,
    NEW_TOPIC_CUSHION_SYSTEM,
    NEW_TOPIC_DIVERSITY_SYSTEM,
    build_tradeoff_user_prompt,
    build_constraint_user_prompt,
    build_hook_user_prompt,
    build_cushion_user_prompt,
    build_new_topic_diversity_user_prompt,
)


_raw_model = os.getenv("JUDGE_MODEL", "claude-sonnet-4-5-20250929")
JUDGE_MODEL = _raw_model.removeprefix("anthropic/")

_client: anthropic.Anthropic | None = None
_eval_cache: dict[str, Evaluation] = {}


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
        print(f"[new_topic_judge ERROR] {type(e).__name__}: {e}")
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

def tradeoff_depth(*, output, **kwargs):
    """Trade-off(선택과 타협)를 얼마나 잘 묻는가? (1-5)"""
    cache_key = f"nt-tradeoff:{_output_hash(output)}"
    if cache_key in _eval_cache:
        return _eval_cache[cache_key]

    question_text = (output.get("question_text") or "").strip()
    if not question_text:
        ev = Evaluation(
            name="tradeoff_depth",
            value=0,
            comment="question_text 없음 (skip)",
        )
        _eval_cache[cache_key] = ev
        return ev

    question_type = output.get("question_type") or ""
    history = output.get("interview_history") or []
    user_prompt = build_tradeoff_user_prompt(question_type, question_text, history)
    ev = _evaluate_with_judge(
        "tradeoff_depth",
        NEW_TOPIC_TRADEOFF_SYSTEM,
        user_prompt,
    )
    _eval_cache[cache_key] = ev
    return ev


def constraint_quality(*, output, **kwargs):
    """실무적 제약 조건(Constraints)의 적절성 (1-5)"""
    cache_key = f"nt-constraint:{_output_hash(output)}"
    if cache_key in _eval_cache:
        return _eval_cache[cache_key]

    question_text = (output.get("question_text") or "").strip()
    if not question_text:
        ev = Evaluation(
            name="constraint_quality",
            value=0,
            comment="question_text 없음 (skip)",
        )
        _eval_cache[cache_key] = ev
        return ev

    question_type = output.get("question_type") or ""
    user_prompt = build_constraint_user_prompt(question_type, question_text)
    ev = _evaluate_with_judge(
        "constraint_quality",
        NEW_TOPIC_CONSTRAINT_SYSTEM,
        user_prompt,
    )
    _eval_cache[cache_key] = ev
    return ev


def hook_richness(*, output, **kwargs):
    """꼬리질문 Hook 풍부도 (1-5)"""
    cache_key = f"nt-hook:{_output_hash(output)}"
    if cache_key in _eval_cache:
        return _eval_cache[cache_key]

    question_text = (output.get("question_text") or "").strip()
    if not question_text:
        ev = Evaluation(
            name="hook_richness",
            value=0,
            comment="question_text 없음 (skip)",
        )
        _eval_cache[cache_key] = ev
        return ev

    question_type = output.get("question_type") or ""
    user_prompt = build_hook_user_prompt(question_type, question_text)
    ev = _evaluate_with_judge(
        "hook_richness",
        NEW_TOPIC_HOOK_SYSTEM,
        user_prompt,
    )
    _eval_cache[cache_key] = ev
    return ev


def cushion_quality(*, output, **kwargs):
    """쿠션어 면접 UX 품질 (1-5)"""
    cache_key = f"nt-cushion:{_output_hash(output)}"
    if cache_key in _eval_cache:
        return _eval_cache[cache_key]

    cushion_text = (output.get("cushion_text") or "").strip()
    question_text = (output.get("question_text") or "").strip()
    if not cushion_text:
        ev = Evaluation(
            name="cushion_quality",
            value=0,
            comment="cushion_text 없음 (skip)",
        )
        _eval_cache[cache_key] = ev
        return ev

    question_type = output.get("question_type") or ""
    history = output.get("interview_history") or []
    user_prompt = build_cushion_user_prompt(
        question_type,
        cushion_text,
        question_text,
        history,
    )
    ev = _evaluate_with_judge(
        "cushion_quality",
        NEW_TOPIC_CUSHION_SYSTEM,
        user_prompt,
    )
    _eval_cache[cache_key] = ev
    return ev


all_item_evaluators = [
    tradeoff_depth,
    constraint_quality,
    hook_richness,
    cushion_quality,
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
    dist = {i: scores.count(float(i)) for i in range(1, 6)}
    dist_str = " | ".join(f"{k}점:{v}건" for k, v in dist.items() if v > 0)

    return Evaluation(
        name=name,
        value=round(avg, 2),
        comment=f"avg={avg:.2f}/5.0 | n={n} | {dist_str}",
    )


def tradeoff_depth_avg(*, item_results, **kwargs):
    return _run_avg("tradeoff_depth_avg", tradeoff_depth, item_results=item_results)


def constraint_quality_avg(*, item_results, **kwargs):
    return _run_avg(
        "constraint_quality_avg",
        constraint_quality,
        item_results=item_results,
    )


def hook_richness_avg(*, item_results, **kwargs):
    return _run_avg("hook_richness_avg", hook_richness, item_results=item_results)


def cushion_quality_avg(*, item_results, **kwargs):
    return _run_avg("cushion_quality_avg", cushion_quality, item_results=item_results)


def new_topic_quality_score(*, item_results, **kwargs):
    """가중 종합 점수:
    - Trade-off 깊이: 0.35
    - 제약 조건의 질: 0.25
    - Hook 풍부도: 0.20
    - 쿠션어 품질: 0.20
    """
    composites: list[float] = []
    for r in item_results:
        if not r.output:
            continue

        td = tradeoff_depth(output=r.output)
        cq = constraint_quality(output=r.output)
        hr = hook_richness(output=r.output)
        csh = cushion_quality(output=r.output)

        if any(e.value is None or e.value == 0 for e in [td, cq, hr, csh]):
            continue

        t, c, h, cu = td.value, cq.value, hr.value, csh.value
        score = t * 0.35 + c * 0.25 + h * 0.20 + cu * 0.20
        composites.append(round(score, 2))

    if not composites:
        return Evaluation(
            name="new_topic_quality_score",
            value=0,
            comment="유효한 결과 없음",
        )

    n = len(composites)
    avg = sum(composites) / n
    return Evaluation(
        name="new_topic_quality_score",
        value=round(avg, 2),
        comment=(
            f"weighted_avg={avg:.2f}/5.0 | n={n} | "
            "weights: Tradeoff=0.35 Constraint=0.25 Hook=0.20 Cushion=0.20"
        ),
    )


_MAX_QUESTIONS_FOR_DIVERSITY = 30


def new_topic_diversity(*, item_results, **kwargs) -> Evaluation:
    """Run-level: 생성된 new_topic 질문들의 다양성(1-5)을 LLM-as-Judge로 평가."""
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
            name="new_topic_diversity",
            value=0,
            comment="질문이 2개 미만이라 다양성 평가 불가",
        )

    if total_count > _MAX_QUESTIONS_FOR_DIVERSITY:
        step = total_count / _MAX_QUESTIONS_FOR_DIVERSITY
        indices = [int(i * step) for i in range(_MAX_QUESTIONS_FOR_DIVERSITY)]
        question_texts = [question_texts[i] for i in indices]

    user_prompt = build_new_topic_diversity_user_prompt(question_texts)
    result = _call_judge(NEW_TOPIC_DIVERSITY_SYSTEM, user_prompt)

    if "error" in result:
        return Evaluation(
            name="new_topic_diversity",
            value=0,
            comment=f"Judge 호출 실패: {result['error']}",
        )

    score = result.get("score")
    reasoning = result.get("reasoning", "")

    if not isinstance(score, (int, float)) or not (1 <= score <= 5):
        return Evaluation(
            name="new_topic_diversity",
            value=0,
            comment=f"유효하지 않은 score: {score} | {reasoning}",
        )

    used = len(question_texts)
    return Evaluation(
        name="new_topic_diversity",
        value=float(score),
        comment=f"n={total_count} (평가에 사용 {used}개) | {reasoning}",
    )


all_run_evaluators = [
    tradeoff_depth_avg,
    constraint_quality_avg,
    hook_richness_avg,
    cushion_quality_avg,
    new_topic_quality_score,
    new_topic_diversity,
]

