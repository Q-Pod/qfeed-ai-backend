"""LLM-as-Judge Router 분석 품질 평가기."""

import hashlib
import json
import os
from typing import Any

import anthropic
from langfuse import Evaluation

from tests.evaluation_v2.prompts.router_analysis_judge_prompts import (
    ROUTER_ANALYSIS_JUDGE_SYSTEM,
    build_router_analysis_judge_prompt,
)

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


def _call_judge(system: str, user_prompt: str, max_tokens: int = 700) -> dict:
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
        print(f"[router_analysis_judge ERROR] {type(e).__name__}: {e}")
        return {"error": f"{type(e).__name__}: {e}"}


def _safe_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        f = float(value)
        if 0.0 <= f <= 1.0:
            return f
    return None


def _extract_expected_output(item: Any) -> dict:
    if hasattr(item, "expected_output"):
        return item.expected_output or {}
    if isinstance(item, dict):
        return item.get("expected_output", {}) or {}
    return {}


def _flag_match_rate(
    expected_analysis: dict[str, Any] | None,
    actual_analysis: dict[str, Any] | None,
) -> tuple[float | None, list[str]]:
    if not expected_analysis:
        return None, []

    actual = actual_analysis or {}
    bool_keys = [
        key
        for key, value in expected_analysis.items()
        if isinstance(value, bool)
    ]
    if not bool_keys:
        return None, []

    matches = 0
    details = []
    for key in bool_keys:
        expected_value = expected_analysis.get(key)
        actual_value = actual.get(key)
        is_match = actual_value == expected_value
        if is_match:
            matches += 1
        details.append(
            f"{key}={'OK' if is_match else 'MISS'}(exp={expected_value}, act={actual_value})"
        )

    return matches / len(bool_keys), details


def _keyword_coverage(keywords: list[str], text: str | None) -> float | None:
    if not keywords:
        return None
    source = (text or "").lower()
    if not source:
        return 0.0

    matched = 0
    for keyword in keywords:
        if keyword.lower() in source:
            matched += 1
    return matched / len(keywords)


def _maybe_call_judge(output: dict, expected_output: dict) -> dict[str, Any]:
    metric_app = expected_output.get("metric_applicability", {})
    if not metric_app.get("analysis_accuracy") and not metric_app.get(
        "direction_appropriateness"
    ):
        return {
            "analysis_text_alignment": None,
            "direction_detail_alignment": None,
            "analysis_reasoning": "N/A",
            "direction_reasoning": "N/A",
        }

    user_prompt = build_router_analysis_judge_prompt(
        output=output,
        expected_output=expected_output,
    )
    result = _call_judge(ROUTER_ANALYSIS_JUDGE_SYSTEM, user_prompt)
    if "error" in result:
        return {
            "analysis_text_alignment": 0.0
            if metric_app.get("analysis_accuracy")
            else None,
            "direction_detail_alignment": 0.0
            if metric_app.get("direction_appropriateness")
            else None,
            "analysis_reasoning": f"Judge 호출 실패: {result['error']}",
            "direction_reasoning": f"Judge 호출 실패: {result['error']}",
        }

    return {
        "analysis_text_alignment": _safe_float(
            result.get("analysis_text_alignment")
        ),
        "direction_detail_alignment": _safe_float(
            result.get("direction_detail_alignment")
        ),
        "analysis_reasoning": str(result.get("analysis_reasoning", "")).strip(),
        "direction_reasoning": str(result.get("direction_reasoning", "")).strip(),
    }


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _compute_case_evaluation(
    output: dict,
    expected_output: dict | None,
) -> dict[str, Any]:
    expected = expected_output or {}
    metric_app = expected.get("metric_applicability", {})
    judge_result = _maybe_call_judge(output, expected)

    route_expected = expected.get("expected_route_decision")
    route_actual = output.get("route_decision")
    routing_decision = (
        1.0 if route_expected is not None and route_actual == route_expected else 0.0
    )

    expected_analysis = expected.get("expected_analysis")
    actual_analysis = output.get("analysis")
    flag_match_rate, flag_details = _flag_match_rate(
        expected_analysis,
        actual_analysis,
    )

    analysis_accuracy = None
    if metric_app.get("analysis_accuracy"):
        text_alignment = judge_result.get("analysis_text_alignment")
        if flag_match_rate is None and text_alignment is None:
            analysis_accuracy = 0.0
        elif flag_match_rate is None:
            analysis_accuracy = text_alignment
        elif text_alignment is None:
            analysis_accuracy = flag_match_rate
        else:
            analysis_accuracy = (flag_match_rate * 0.7) + (text_alignment * 0.3)

    direction_appropriateness = None
    direction_keywords = expected.get("direction_detail_keywords", [])
    if metric_app.get("direction_appropriateness"):
        expected_direction = expected.get("expected_follow_up_direction")
        actual_direction = output.get("follow_up_direction")
        direction_match = 1.0 if actual_direction == expected_direction else 0.0
        detail_alignment = judge_result.get("direction_detail_alignment")
        keyword_coverage = _keyword_coverage(
            direction_keywords,
            output.get("direction_detail"),
        )

        sub_scores = [direction_match]
        if detail_alignment is not None:
            sub_scores.append(detail_alignment)
        if keyword_coverage is not None:
            sub_scores.append(keyword_coverage)
        direction_appropriateness = _mean(sub_scores)
    else:
        direction_match = None
        keyword_coverage = None

    quality_values = [
        score
        for score in [
            analysis_accuracy,
            direction_appropriateness,
            routing_decision,
        ]
        if score is not None
    ]
    quality_score = _mean(quality_values) if quality_values else None

    return {
        "analysis_accuracy": analysis_accuracy,
        "direction_appropriateness": direction_appropriateness,
        "routing_decision": routing_decision,
        "quality_score": quality_score,
        "flag_match_rate": flag_match_rate,
        "flag_details": flag_details,
        "direction_match": direction_match,
        "keyword_coverage": keyword_coverage,
        "judge_result": judge_result,
        "metric_applicability": metric_app,
    }


def _case_cache_key(output: dict, expected_output: dict | None) -> str:
    key_payload = {
        "output": output,
        "expected_output": expected_output or {},
    }
    return _stable_hash(key_payload)


def _evaluate_case(output: dict, expected_output: dict | None) -> dict[str, Any]:
    key = _case_cache_key(output, expected_output)
    if key not in _case_eval_cache:
        _case_eval_cache[key] = _compute_case_evaluation(output, expected_output)
    return _case_eval_cache[key]


def _metric_comment(case_eval: dict[str, Any], metric: str) -> str:
    if metric == "analysis_accuracy":
        if case_eval["analysis_accuracy"] is None:
            return "N/A"
        parts = []
        if case_eval["flag_match_rate"] is not None:
            parts.append(f"flag_match={case_eval['flag_match_rate']:.2f}")
        parts.append(
            "text_align="
            f"{(case_eval['judge_result'].get('analysis_text_alignment') or 0.0):.2f}"
        )
        reasoning = case_eval["judge_result"].get("analysis_reasoning") or ""
        if reasoning:
            parts.append(reasoning)
        return " | ".join(parts)

    if metric == "direction_appropriateness":
        if case_eval["direction_appropriateness"] is None:
            return "N/A"
        parts = []
        if case_eval["direction_match"] is not None:
            parts.append(f"dir_match={case_eval['direction_match']:.2f}")
        if case_eval["keyword_coverage"] is not None:
            parts.append(f"kw={case_eval['keyword_coverage']:.2f}")
        parts.append(
            "detail_align="
            f"{(case_eval['judge_result'].get('direction_detail_alignment') or 0.0):.2f}"
        )
        reasoning = case_eval["judge_result"].get("direction_reasoning") or ""
        if reasoning:
            parts.append(reasoning)
        return " | ".join(parts)

    if metric == "routing_decision":
        return "exact_match" if case_eval["routing_decision"] == 1.0 else "mismatch"

    if metric == "quality_score":
        return "applicable metrics average"

    return ""


def _metric_metadata(case_eval: dict[str, Any]) -> dict[str, Any]:
    return {
        "analysis_applicable": case_eval.get("metric_applicability", {}).get(
            "analysis_accuracy", False
        ),
        "direction_applicable": case_eval.get("metric_applicability", {}).get(
            "direction_appropriateness", False
        ),
        "flag_match_rate": case_eval.get("flag_match_rate"),
        "direction_match": case_eval.get("direction_match"),
        "keyword_coverage": case_eval.get("keyword_coverage"),
    }


def router_analysis_accuracy(*, output, expected_output, **kwargs):
    case_eval = _evaluate_case(output, expected_output)
    score = case_eval["analysis_accuracy"]
    return Evaluation(
        name="router_analysis_accuracy",
        value=round(score, 3) if score is not None else 0.0,
        comment=_metric_comment(case_eval, "analysis_accuracy"),
        metadata=_metric_metadata(case_eval),
    )


def router_direction_appropriateness(*, output, expected_output, **kwargs):
    case_eval = _evaluate_case(output, expected_output)
    score = case_eval["direction_appropriateness"]
    return Evaluation(
        name="router_direction_appropriateness",
        value=round(score, 3) if score is not None else 0.0,
        comment=_metric_comment(case_eval, "direction_appropriateness"),
        metadata=_metric_metadata(case_eval),
    )


def router_routing_decision(*, output, expected_output, **kwargs):
    case_eval = _evaluate_case(output, expected_output)
    return Evaluation(
        name="router_routing_decision",
        value=round(case_eval["routing_decision"], 3),
        comment=_metric_comment(case_eval, "routing_decision"),
    )


def router_quality_score(*, output, expected_output, **kwargs):
    case_eval = _evaluate_case(output, expected_output)
    score = case_eval["quality_score"]
    return Evaluation(
        name="router_quality_score",
        value=round(score, 3) if score is not None else 0.0,
        comment=_metric_comment(case_eval, "quality_score"),
        metadata=_metric_metadata(case_eval),
    )


all_item_evaluators = [
    router_analysis_accuracy,
    router_direction_appropriateness,
    router_routing_decision,
    router_quality_score,
]


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
    comment = f"avg={avg:.3f} | n={len(values)}"
    if skipped:
        comment += f" | skipped={skipped}"
    return Evaluation(name=name, value=round(avg, 3), comment=comment)


def router_analysis_accuracy_avg(*, item_results, **kwargs):
    return _run_avg(
        "analysis_accuracy",
        "router_analysis_accuracy_avg",
        item_results=item_results,
    )


def router_direction_appropriateness_avg(*, item_results, **kwargs):
    return _run_avg(
        "direction_appropriateness",
        "router_direction_appropriateness_avg",
        item_results=item_results,
    )


def router_routing_decision_avg(*, item_results, **kwargs):
    return _run_avg(
        "routing_decision",
        "router_routing_decision_avg",
        item_results=item_results,
    )


def router_quality_score_avg(*, item_results, **kwargs):
    return _run_avg(
        "quality_score",
        "router_quality_score_avg",
        item_results=item_results,
    )


def _is_case_pass(case_eval: dict[str, Any]) -> bool:
    if case_eval["routing_decision"] < 1.0:
        return False
    if (
        case_eval["analysis_accuracy"] is not None
        and case_eval["analysis_accuracy"] < 0.8
    ):
        return False
    if (
        case_eval["direction_appropriateness"] is not None
        and case_eval["direction_appropriateness"] < 0.75
    ):
        return False
    return True


def router_pass_rate(*, item_results, **kwargs):
    total = 0
    passed = 0

    for result in item_results:
        if not result.output:
            continue
        expected_output = _extract_expected_output(result.item)
        case_eval = _evaluate_case(result.output, expected_output)
        total += 1
        if _is_case_pass(case_eval):
            passed += 1

    if total == 0:
        return Evaluation(name="router_pass_rate", value=0.0, comment="유효한 결과 없음")

    rate = passed / total
    return Evaluation(
        name="router_pass_rate",
        value=round(rate, 3),
        comment=f"pass={passed}/{total}",
    )


all_run_evaluators = [
    router_analysis_accuracy_avg,
    router_direction_appropriateness_avg,
    router_routing_decision_avg,
    router_quality_score_avg,
    router_pass_rate,
]
