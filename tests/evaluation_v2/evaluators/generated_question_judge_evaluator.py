"""LLM-as-Judge 생성 질문 품질 평가기.

평가 지표:
- 공통(각 1-5):
  direction_adherence, naturalness, non_repetition,
  single_focus, appropriate_length, technical_factuality
- PORTFOLIO 추가(1-5):
  portfolio_grounding

종합 점수:
- quality_score = 적용 가능한 지표 평균
"""

import hashlib
import json
import os
from typing import Any

import anthropic
from langfuse import Evaluation

from tests.evaluation_v2.prompts.generated_question_judge_prompts import (
    QUESTION_GENERATION_RUBRIC_SYSTEM,
    build_generated_question_rubric_prompt,
)

CORE_METRICS = [
    "direction_adherence",
    "naturalness",
    "non_repetition",
    "single_focus",
    "appropriate_length",
    "technical_factuality",
]
OPTIONAL_METRIC = "portfolio_grounding"
ALL_METRICS = [*CORE_METRICS, OPTIONAL_METRIC]

_raw_model = os.getenv("JUDGE_MODEL", "claude-sonnet-4-5-20250929")
JUDGE_MODEL = _raw_model.removeprefix("anthropic/")

_client: anthropic.Anthropic | None = None
_case_eval_cache: dict[str, dict[str, Any]] = {}


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY 환경변수가 설정되어 있지 않습니다.")
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def _stable_hash(payload: Any) -> str:
    dumped = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(dumped.encode("utf-8")).hexdigest()


def _extract_json(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start : end + 1])
    raise json.JSONDecodeError("No JSON object found", text, 0)


def _call_judge(system: str, user_prompt: str, max_tokens: int = 1000) -> dict:
    try:
        client = _get_client()
        response = client.messages.create(
            model=JUDGE_MODEL,
            max_tokens=max_tokens,
            temperature=0.0,
            system=[
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_prompt}],
        )
        if not response.content:
            raise ValueError("Judge 응답 content가 비어 있습니다.")
        text = (response.content[0].text or "").strip()
        if not text:
            raise ValueError("Judge 응답이 비어 있습니다.")
        return _extract_json(text)
    except Exception as e:
        print(f"[generated_question_judge ERROR] {type(e).__name__}: {e}")
        return {"error": f"{type(e).__name__}: {e}"}


def _normalize_score(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and 1 <= float(value) <= 5:
        return float(value)
    return None


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _is_portfolio_case(output: dict) -> bool:
    return str(output.get("question_type") or "").upper() == "PORTFOLIO"


def _empty_case(reason: str, *, question_char_count: int, is_portfolio: bool) -> dict[str, Any]:
    base = {metric: 0.0 for metric in CORE_METRICS}
    return {
        **base,
        OPTIONAL_METRIC: 0.0 if is_portfolio else None,
        "quality_score": 0.0,
        "reasoning": reason,
        "metric_reasoning": {},
        "metric_applicability": {
            OPTIONAL_METRIC: is_portfolio,
        },
        "question_char_count": question_char_count,
    }


def _compute_case_evaluation(output: dict, expected_output: dict | None) -> dict[str, Any]:
    _ = expected_output or {}

    question_text = (output.get("question_text") or "").strip()
    is_portfolio = _is_portfolio_case(output)

    if not question_text:
        return _empty_case(
            "question_text가 비어 있습니다.",
            question_char_count=0,
            is_portfolio=is_portfolio,
        )

    user_prompt = build_generated_question_rubric_prompt(
        question_type=str(output.get("question_type") or ""),
        follow_up_direction=str(output.get("follow_up_direction") or ""),
        direction_detail=str(output.get("direction_detail") or ""),
        interview_history=output.get("current_topic_turns")
        or output.get("interview_history")
        or [],
        cushion_text=str(output.get("cushion_text") or ""),
        question_text=question_text,
    )
    result = _call_judge(QUESTION_GENERATION_RUBRIC_SYSTEM, user_prompt)

    if "error" in result:
        return _empty_case(
            f"Judge 호출 실패: {result['error']}",
            question_char_count=len(question_text),
            is_portfolio=is_portfolio,
        )

    scores: dict[str, float] = {}
    for metric in CORE_METRICS:
        score = _normalize_score(result.get(metric))
        if score is None:
            return _empty_case(
                f"유효하지 않은 {metric} 점수: {result.get(metric)}",
                question_char_count=len(question_text),
                is_portfolio=is_portfolio,
            )
        scores[metric] = score

    portfolio_score: float | None = None
    if is_portfolio:
        portfolio_score = _normalize_score(result.get(OPTIONAL_METRIC))
        if portfolio_score is None:
            return _empty_case(
                f"유효하지 않은 {OPTIONAL_METRIC} 점수: {result.get(OPTIONAL_METRIC)}",
                question_char_count=len(question_text),
                is_portfolio=is_portfolio,
            )

    metric_reasoning = result.get("metric_reasoning")
    if not isinstance(metric_reasoning, dict):
        metric_reasoning = {}

    applicable_scores = [scores[m] for m in CORE_METRICS]
    if portfolio_score is not None:
        applicable_scores.append(portfolio_score)

    quality_score = _mean(applicable_scores)

    metric_reasoning_map: dict[str, str] = {}
    for metric in ALL_METRICS:
        if metric == OPTIONAL_METRIC and not is_portfolio:
            metric_reasoning_map[metric] = "N/A (non-portfolio)"
            continue
        metric_reasoning_map[metric] = str(metric_reasoning.get(metric, "")).strip()

    return {
        **scores,
        OPTIONAL_METRIC: portfolio_score,
        "quality_score": quality_score,
        "reasoning": str(result.get("reasoning", "")).strip(),
        "metric_reasoning": metric_reasoning_map,
        "metric_applicability": {
            OPTIONAL_METRIC: is_portfolio,
        },
        "question_char_count": len(question_text),
    }


def _case_cache_key(output: dict, expected_output: dict | None) -> str:
    expected = expected_output or {}
    key_payload = {
        "question_type": output.get("question_type"),
        "follow_up_direction": output.get("follow_up_direction"),
        "direction_detail": output.get("direction_detail"),
        "question_text": output.get("question_text"),
        "cushion_text": output.get("cushion_text"),
        "current_topic_turns": output.get("current_topic_turns")
        or output.get("interview_history")
        or [],
        "expected_criteria": expected,
    }
    return _stable_hash(key_payload)


def _evaluate_case(output: dict, expected_output: dict | None) -> dict[str, Any]:
    key = _case_cache_key(output, expected_output)
    if key not in _case_eval_cache:
        _case_eval_cache[key] = _compute_case_evaluation(output, expected_output)
    return _case_eval_cache[key]


def _extract_expected_output(item: Any) -> dict:
    if hasattr(item, "expected_output"):
        return item.expected_output or {}
    if isinstance(item, dict):
        return item.get("expected_output", {}) or {}
    return {}


def _metric_comment(case_eval: dict[str, Any], metric: str) -> str:
    char_count = case_eval.get("question_char_count", 0)

    if metric == OPTIONAL_METRIC and case_eval.get(metric) is None:
        return f"chars={char_count} | N/A(non-portfolio)"

    reasoning = case_eval.get("metric_reasoning", {}).get(metric, "")
    if reasoning:
        return f"chars={char_count} | {reasoning}"
    return f"chars={char_count}"


def _quality_metadata(output: dict, case_eval: dict[str, Any]) -> dict[str, Any]:
    return {
        "question_type": output.get("question_type"),
        "follow_up_direction": output.get("follow_up_direction"),
        "direction_detail": output.get("direction_detail"),
        "cushion_text": output.get("cushion_text"),
        "question_text": output.get("question_text"),
        "scores": {
            metric: case_eval.get(metric) for metric in ALL_METRICS
        },
        "reasoning": case_eval.get("reasoning"),
        "metric_reasoning": case_eval.get("metric_reasoning", {}),
        "metric_applicability": case_eval.get("metric_applicability", {}),
        "question_char_count": case_eval.get("question_char_count"),
    }


# ---------------------------------------------------------------------------
# Item-level evaluators
# ---------------------------------------------------------------------------


def gq_direction_adherence(*, output, expected_output, **kwargs):
    case_eval = _evaluate_case(output, expected_output)
    return Evaluation(
        name="gq_direction_adherence",
        value=round(case_eval["direction_adherence"], 2),
        comment=_metric_comment(case_eval, "direction_adherence"),
    )


def gq_naturalness(*, output, expected_output, **kwargs):
    case_eval = _evaluate_case(output, expected_output)
    return Evaluation(
        name="gq_naturalness",
        value=round(case_eval["naturalness"], 2),
        comment=_metric_comment(case_eval, "naturalness"),
    )


def gq_non_repetition(*, output, expected_output, **kwargs):
    case_eval = _evaluate_case(output, expected_output)
    return Evaluation(
        name="gq_non_repetition",
        value=round(case_eval["non_repetition"], 2),
        comment=_metric_comment(case_eval, "non_repetition"),
    )


def gq_single_focus(*, output, expected_output, **kwargs):
    case_eval = _evaluate_case(output, expected_output)
    return Evaluation(
        name="gq_single_focus",
        value=round(case_eval["single_focus"], 2),
        comment=_metric_comment(case_eval, "single_focus"),
    )


def gq_appropriate_length(*, output, expected_output, **kwargs):
    case_eval = _evaluate_case(output, expected_output)
    return Evaluation(
        name="gq_appropriate_length",
        value=round(case_eval["appropriate_length"], 2),
        comment=_metric_comment(case_eval, "appropriate_length"),
    )


def gq_technical_factuality(*, output, expected_output, **kwargs):
    case_eval = _evaluate_case(output, expected_output)
    return Evaluation(
        name="gq_technical_factuality",
        value=round(case_eval["technical_factuality"], 2),
        comment=_metric_comment(case_eval, "technical_factuality"),
    )


def gq_portfolio_grounding(*, output, expected_output, **kwargs):
    case_eval = _evaluate_case(output, expected_output)
    score = case_eval.get(OPTIONAL_METRIC)
    return Evaluation(
        name="gq_portfolio_grounding",
        value=round(score, 2) if score is not None else 0.0,
        comment=_metric_comment(case_eval, OPTIONAL_METRIC),
    )


def gq_quality_score(*, output, expected_output, **kwargs):
    case_eval = _evaluate_case(output, expected_output)
    pg_score = case_eval.get(OPTIONAL_METRIC)
    pg_text = f" PG={pg_score:.0f}" if pg_score is not None else " PG=N/A"
    return Evaluation(
        name="gq_quality_score",
        value=round(case_eval["quality_score"], 2),
        comment=(
            "score=avg(applicable metrics)"
            f" | chars={case_eval.get('question_char_count', 0)}"
            f" | DA={case_eval.get('direction_adherence', 0):.0f}"
            f" N={case_eval.get('naturalness', 0):.0f}"
            f" NR={case_eval.get('non_repetition', 0):.0f}"
            f" SF={case_eval.get('single_focus', 0):.0f}"
            f" AL={case_eval.get('appropriate_length', 0):.0f}"
            f" TF={case_eval.get('technical_factuality', 0):.0f}"
            f"{pg_text}"
        ),
        metadata=_quality_metadata(output, case_eval),
    )


all_item_evaluators = [
    gq_direction_adherence,
    gq_naturalness,
    gq_non_repetition,
    gq_single_focus,
    gq_appropriate_length,
    gq_technical_factuality,
    gq_portfolio_grounding,
    gq_quality_score,
]


# ---------------------------------------------------------------------------
# Run-level evaluators
# ---------------------------------------------------------------------------


def _run_avg(metric: str, name: str, *, item_results) -> Evaluation:
    values: list[float] = []
    skipped = 0

    for result in item_results:
        if not result.output:
            continue
        expected_output = _extract_expected_output(result.item)
        case_eval = _evaluate_case(result.output, expected_output)
        value = case_eval.get(metric)
        if value is None:
            skipped += 1
            continue
        values.append(float(value))

    if not values:
        return Evaluation(name=name, value=0.0, comment="유효한 결과 없음")

    avg = _mean(values)
    comment = f"avg={avg:.2f}/5.0 | n={len(values)}"
    if skipped:
        comment += f" | skipped={skipped}"
    return Evaluation(
        name=name,
        value=round(avg, 2),
        comment=comment,
    )


def gq_direction_adherence_avg(*, item_results, **kwargs):
    return _run_avg(
        "direction_adherence",
        "gq_direction_adherence_avg",
        item_results=item_results,
    )


def gq_naturalness_avg(*, item_results, **kwargs):
    return _run_avg("naturalness", "gq_naturalness_avg", item_results=item_results)


def gq_non_repetition_avg(*, item_results, **kwargs):
    return _run_avg(
        "non_repetition",
        "gq_non_repetition_avg",
        item_results=item_results,
    )


def gq_single_focus_avg(*, item_results, **kwargs):
    return _run_avg("single_focus", "gq_single_focus_avg", item_results=item_results)


def gq_appropriate_length_avg(*, item_results, **kwargs):
    return _run_avg(
        "appropriate_length",
        "gq_appropriate_length_avg",
        item_results=item_results,
    )


def gq_technical_factuality_avg(*, item_results, **kwargs):
    return _run_avg(
        "technical_factuality",
        "gq_technical_factuality_avg",
        item_results=item_results,
    )


def gq_portfolio_grounding_avg(*, item_results, **kwargs):
    return _run_avg(
        OPTIONAL_METRIC,
        "gq_portfolio_grounding_avg",
        item_results=item_results,
    )


def gq_quality_score_avg(*, item_results, **kwargs):
    return _run_avg("quality_score", "gq_quality_score_avg", item_results=item_results)


def _is_case_pass(case_eval: dict[str, Any], expected_output: dict) -> bool:
    rubric_exp = expected_output.get("rubric_expectations", {})
    metric_mapping = {
        "direction_adherence_min": "direction_adherence",
        "naturalness_min": "naturalness",
        "non_repetition_min": "non_repetition",
        "single_focus_min": "single_focus",
        "appropriate_length_min": "appropriate_length",
        "technical_factuality_min": "technical_factuality",
        "portfolio_grounding_min": OPTIONAL_METRIC,
    }

    for min_key, metric in metric_mapping.items():
        min_score = rubric_exp.get(min_key)
        if min_score is None:
            continue
        value = case_eval.get(metric)
        if value is None:
            return False
        if float(value) < float(min_score):
            return False

    char_range = expected_output.get("question_char_range", {})
    min_chars = char_range.get("min")
    max_chars = char_range.get("max")
    char_count = int(case_eval.get("question_char_count", 0))

    if min_chars is not None and char_count < int(min_chars):
        return False
    if max_chars is not None and char_count > int(max_chars):
        return False

    return True


def gq_pass_rate(*, item_results, **kwargs):
    total = 0
    passed = 0

    for result in item_results:
        if not result.output:
            continue
        expected_output = _extract_expected_output(result.item)
        case_eval = _evaluate_case(result.output, expected_output)

        total += 1
        if _is_case_pass(case_eval, expected_output):
            passed += 1

    if total == 0:
        return Evaluation(name="gq_pass_rate", value=0.0, comment="유효한 결과 없음")

    rate = passed / total
    return Evaluation(
        name="gq_pass_rate",
        value=round(rate, 3),
        comment=f"pass={passed}/{total}",
    )


all_run_evaluators = [
    gq_direction_adherence_avg,
    gq_naturalness_avg,
    gq_non_repetition_avg,
    gq_single_focus_avg,
    gq_appropriate_length_avg,
    gq_technical_factuality_avg,
    gq_portfolio_grounding_avg,
    gq_quality_score_avg,
    gq_pass_rate,
]
