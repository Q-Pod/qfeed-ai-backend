"""LLM-as-Judge 질문 풀(question_pool) 품질 평가기.

평가 구조:
1) 질문별(Question-level) 4개 지표
   - relevance
   - specificity
   - depth_potential
   - interview_fit
2) 케이스 최종 점수
   - (relevance + specificity + depth_potential + interview_fit) / 4
"""

import hashlib
import json
import os
from typing import Any

import anthropic
from langfuse import Evaluation

from tests.evaluation_v2.prompts.question_pool_judge_prompts import (
    QUESTION_RUBRIC_SYSTEM,
    build_question_rubric_user_prompt,
)

RUBRIC_METRICS = [
    "relevance",
    "specificity",
    "depth_potential",
    "interview_fit",
]

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


def _call_judge(system: str, user_prompt: str, max_tokens: int = 900) -> dict:
    """Claude Judge를 호출해 JSON 응답을 반환한다."""
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
        print(f"[question_pool_judge ERROR] {type(e).__name__}: {e}")
        return {"error": f"{type(e).__name__}: {e}"}


def _normalize_score(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and 1 <= float(value) <= 5:
        return float(value)
    return None


def _evaluate_question_rubric(
    portfolio_projects: list[dict],
    generated_question: dict,
    golden_question_pool: list[dict],
) -> dict[str, Any]:
    """질문 1개에 대해 4개 루브릭 점수를 산출한다."""
    user_prompt = build_question_rubric_user_prompt(
        portfolio_projects=portfolio_projects,
        generated_question=generated_question,
        golden_question_pool=golden_question_pool,
    )
    result = _call_judge(QUESTION_RUBRIC_SYSTEM, user_prompt)

    if "error" in result:
        return {
            "relevance": 0.0,
            "specificity": 0.0,
            "depth_potential": 0.0,
            "interview_fit": 0.0,
            "reasoning": f"Judge 호출 실패: {result['error']}",
            "metric_reasoning": {},
        }

    scores: dict[str, float] = {}
    for metric in RUBRIC_METRICS:
        score = _normalize_score(result.get(metric))
        if score is None:
            return {
                "relevance": 0.0,
                "specificity": 0.0,
                "depth_potential": 0.0,
                "interview_fit": 0.0,
                "reasoning": f"유효하지 않은 {metric} 점수: {result.get(metric)}",
                "metric_reasoning": {},
            }
        scores[metric] = score

    metric_reasoning = result.get("metric_reasoning")
    if not isinstance(metric_reasoning, dict):
        metric_reasoning = {}

    return {
        **scores,
        "reasoning": str(result.get("reasoning", "")).strip(),
        "metric_reasoning": {
            metric: str(metric_reasoning.get(metric, "")).strip()
            for metric in RUBRIC_METRICS
        },
    }


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _compute_case_evaluation(
    output: dict,
    expected_output: dict | None,
) -> dict[str, Any]:
    expected = expected_output or {}
    generated_question_pool = output.get("generated_question_pool") or []
    portfolio_projects = output.get("portfolio_projects") or []
    golden_question_pool = expected.get("golden_question_pool") or []

    valid_questions = [
        q for q in generated_question_pool if (q.get("question_text") or "").strip()
    ]

    if not valid_questions:
        return {
            "question_count": 0,
            "relevance": 0.0,
            "specificity": 0.0,
            "depth_potential": 0.0,
            "interview_fit": 0.0,
            "quality_score": 0.0,
            "question_details": [],
        }

    question_rows = []
    for question in valid_questions:
        rubric = _evaluate_question_rubric(
            portfolio_projects=portfolio_projects,
            generated_question=question,
            golden_question_pool=golden_question_pool,
        )

        question_rows.append(
            {
                "question_id": question.get("question_id"),
                "project_name": question.get("project_name"),
                "question_text": question.get("question_text"),
                **rubric,
            }
        )

    relevance_avg = _mean([row["relevance"] for row in question_rows])
    specificity_avg = _mean([row["specificity"] for row in question_rows])
    depth_avg = _mean([row["depth_potential"] for row in question_rows])
    interview_fit_avg = _mean([row["interview_fit"] for row in question_rows])

    quality_score = (
        relevance_avg
        + specificity_avg
        + depth_avg
        + interview_fit_avg
    ) / 4

    return {
        "question_count": len(valid_questions),
        "relevance": relevance_avg,
        "specificity": specificity_avg,
        "depth_potential": depth_avg,
        "interview_fit": interview_fit_avg,
        "quality_score": quality_score,
        "question_details": question_rows,
    }


def _case_cache_key(output: dict, expected_output: dict | None) -> str:
    expected = expected_output or {}
    key_payload = {
        "portfolio_projects": output.get("portfolio_projects") or [],
        "generated_question_pool": output.get("generated_question_pool") or [],
        "golden_question_pool": expected.get("golden_question_pool") or [],
    }
    return _stable_hash(key_payload)


def _evaluate_case(output: dict, expected_output: dict | None) -> dict[str, Any]:
    key = _case_cache_key(output, expected_output)
    if key not in _case_eval_cache:
        _case_eval_cache[key] = _compute_case_evaluation(output, expected_output)
    return _case_eval_cache[key]


def _format_case_comment(case_eval: dict[str, Any], metric: str) -> str:
    n = case_eval["question_count"]
    if n == 0:
        return "질문 없음"

    if metric in RUBRIC_METRICS:
        return f"n={n} | {_metric_breakdown(case_eval, metric)}"

    return f"n={n}"


def _metric_breakdown(case_eval: dict[str, Any], metric: str) -> str:
    chunks = []
    for row in case_eval.get("question_details", []):
        qid = row.get("question_id")
        label = f"Q{qid}" if qid is not None else "Q?"
        chunks.append(f"{label}:{row.get(metric, 0):.0f}")
    return " ".join(chunks[:12])


def _question_scores_metadata(case_eval: dict[str, Any]) -> dict[str, Any]:
    question_scores = []
    for row in case_eval.get("question_details", []):
        question_scores.append(
            {
                "question_id": row.get("question_id"),
                "project_name": row.get("project_name"),
                "relevance": row.get("relevance"),
                "specificity": row.get("specificity"),
                "depth_potential": row.get("depth_potential"),
                "interview_fit": row.get("interview_fit"),
                "reasoning": row.get("reasoning"),
                "metric_reasoning": row.get("metric_reasoning", {}),
            }
        )

    return {
        "question_count": case_eval.get("question_count"),
        "question_scores": question_scores,
    }


def _question_overall_breakdown(case_eval: dict[str, Any]) -> str:
    chunks = []
    for row in case_eval.get("question_details", []):
        qid = row.get("question_id")
        label = f"Q{qid}" if qid is not None else "Q?"
        chunks.append(
            (
                f"{label}(R{row.get('relevance', 0):.0f}"
                f"/S{row.get('specificity', 0):.0f}"
                f"/D{row.get('depth_potential', 0):.0f}"
                f"/I{row.get('interview_fit', 0):.0f})"
            )
        )
    return " ".join(chunks[:12])


# ---------------------------------------------------------------------------
# Item-level evaluators
# ---------------------------------------------------------------------------


def qpool_relevance(*, output, expected_output, **kwargs):
    case_eval = _evaluate_case(output, expected_output)
    return Evaluation(
        name="qpool_relevance",
        value=round(case_eval["relevance"], 2),
        comment=_format_case_comment(case_eval, "relevance"),
    )


def qpool_specificity(*, output, expected_output, **kwargs):
    case_eval = _evaluate_case(output, expected_output)
    return Evaluation(
        name="qpool_specificity",
        value=round(case_eval["specificity"], 2),
        comment=_format_case_comment(case_eval, "specificity"),
    )


def qpool_depth_potential(*, output, expected_output, **kwargs):
    case_eval = _evaluate_case(output, expected_output)
    return Evaluation(
        name="qpool_depth_potential",
        value=round(case_eval["depth_potential"], 2),
        comment=_format_case_comment(case_eval, "depth_potential"),
    )


def qpool_interview_fit(*, output, expected_output, **kwargs):
    case_eval = _evaluate_case(output, expected_output)
    return Evaluation(
        name="qpool_interview_fit",
        value=round(case_eval["interview_fit"], 2),
        comment=_format_case_comment(case_eval, "interview_fit"),
    )


def qpool_quality_score(*, output, expected_output, **kwargs):
    case_eval = _evaluate_case(output, expected_output)
    return Evaluation(
        name="qpool_quality_score",
        value=round(case_eval["quality_score"], 2),
        comment=(
            "score=(R+S+D+I)/4"
            f" | {_question_overall_breakdown(case_eval)}"
        ),
        metadata=_question_scores_metadata(case_eval),
    )


all_item_evaluators = [
    qpool_relevance,
    qpool_specificity,
    qpool_depth_potential,
    qpool_interview_fit,
    qpool_quality_score,
]


# ---------------------------------------------------------------------------
# Run-level evaluators
# ---------------------------------------------------------------------------


def _extract_expected_output(item: Any) -> dict:
    if hasattr(item, "expected_output"):
        return item.expected_output or {}
    if isinstance(item, dict):
        return item.get("expected_output", {}) or {}
    return {}


def _run_avg(metric: str, name: str, *, item_results) -> Evaluation:
    values: list[float] = []
    for result in item_results:
        if not result.output:
            continue
        expected_output = _extract_expected_output(result.item)
        case_eval = _evaluate_case(result.output, expected_output)
        values.append(float(case_eval[metric]))

    if not values:
        return Evaluation(name=name, value=0.0, comment="유효한 결과 없음")

    avg = _mean(values)
    return Evaluation(
        name=name,
        value=round(avg, 2),
        comment=f"avg={avg:.2f}/5.0 | n={len(values)}",
    )


def qpool_relevance_avg(*, item_results, **kwargs):
    return _run_avg("relevance", "qpool_relevance_avg", item_results=item_results)


def qpool_specificity_avg(*, item_results, **kwargs):
    return _run_avg("specificity", "qpool_specificity_avg", item_results=item_results)


def qpool_depth_potential_avg(*, item_results, **kwargs):
    return _run_avg(
        "depth_potential",
        "qpool_depth_potential_avg",
        item_results=item_results,
    )


def qpool_interview_fit_avg(*, item_results, **kwargs):
    return _run_avg(
        "interview_fit",
        "qpool_interview_fit_avg",
        item_results=item_results,
    )


def qpool_quality_score_avg(*, item_results, **kwargs):
    return _run_avg("quality_score", "qpool_quality_score_avg", item_results=item_results)


def _is_case_pass(case_eval: dict[str, Any], expected_output: dict) -> bool:
    rubric_exp = expected_output.get("rubric_expectations", {})
    metric_mapping = {
        "relevance_min": "relevance",
        "specificity_min": "specificity",
        "depth_potential_min": "depth_potential",
        "interview_fit_min": "interview_fit",
    }

    for min_key, metric in metric_mapping.items():
        min_score = rubric_exp.get(min_key)
        if min_score is None:
            continue
        if case_eval[metric] < float(min_score):
            return False

    count_range = expected_output.get("expected_question_count_range", {})
    min_count = count_range.get("min")
    max_count = count_range.get("max")

    if min_count is not None and case_eval["question_count"] < int(min_count):
        return False
    if max_count is not None and case_eval["question_count"] > int(max_count):
        return False

    return True


def qpool_pass_rate(*, item_results, **kwargs):
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
        return Evaluation(name="qpool_pass_rate", value=0.0, comment="유효한 결과 없음")

    rate = passed / total
    return Evaluation(
        name="qpool_pass_rate",
        value=round(rate, 3),
        comment=f"pass={passed}/{total}",
    )


all_run_evaluators = [
    qpool_relevance_avg,
    qpool_specificity_avg,
    qpool_depth_potential_avg,
    qpool_interview_fit_avg,
    qpool_quality_score_avg,
    qpool_pass_rate,
]
