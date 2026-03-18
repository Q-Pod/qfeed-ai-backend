"""피드백 텍스트 품질 오프라인 평가 실행

Golden dataset의 각 케이스에 대해 feedback_generator를 실행하고,
Rule-based 및/또는 LLM-as-Judge 평가를 수행한다.

Usage:
    # 연습모드 Rule-based만 (기본)
    python -m tests.evaluation.run_feedback_eval

    # Judge 평가 포함
    python -m tests.evaluation.run_feedback_eval --judge

    # Judge 평가만 (Rule-based 제외)
    python -m tests.evaluation.run_feedback_eval --judge --no-rule

    # 실전모드
    python -m tests.evaluation.run_feedback_eval --mode real --judge
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv
load_dotenv()

from langfuse import get_client

from tests.evaluation.feedback_target import feedback_eval_task
from tests.evaluation.evaluators import feedback_evaluator
from tests.evaluation.evaluators import feedback_judge_evaluator

DATASET_NAMES = {
    "practice": "golden-practice-rubric",
    "real": "golden-real-rubric",
}


def _build_evaluators(use_rule: bool, use_judge: bool):
    """플래그에 따라 item-level / run-level evaluator 리스트를 조합한다."""
    item_evals = []
    run_evals = []

    if use_rule:
        item_evals.extend(feedback_evaluator.all_item_evaluators)
        run_evals.extend(feedback_evaluator.all_run_evaluators)

    if use_judge:
        item_evals.extend(feedback_judge_evaluator.all_item_evaluators)
        run_evals.extend(feedback_judge_evaluator.all_run_evaluators)

    return item_evals, run_evals


def run_feedback_evaluation(
    mode: str = "practice",
    experiment_name: str | None = None,
    max_concurrency: int = 3,
    provider: str | None = None,
    use_rule: bool = True,
    use_judge: bool = False,
):
    """피드백 텍스트 품질 평가 실행

    Args:
        mode: 평가 모드 (practice / real)
        experiment_name: 실험 이름 (기본: 자동 생성)
        max_concurrency: 동시 실행 수
        provider: LLM provider (gemini / vllm)
        use_rule: Rule-based 평가 포함 여부
        use_judge: LLM-as-Judge 평가 포함 여부
    """
    langfuse = get_client()
    dataset_name = DATASET_NAMES[mode]

    try:
        dataset = langfuse.get_dataset(dataset_name)
    except Exception:
        print(f"Dataset '{dataset_name}'이 존재하지 않습니다.")
        print("먼저 실행: python -m tests.evaluation.setup_dataset")
        sys.exit(1)

    item_evals, run_evals = _build_evaluators(use_rule, use_judge)
    if not item_evals and not run_evals:
        print("평가자가 선택되지 않았습니다. --judge 또는 rule-based 평가를 활성화하세요.")
        sys.exit(1)

    eval_tag = []
    if use_rule:
        eval_tag.append("rule")
    if use_judge:
        eval_tag.append("judge")
    eval_label = "+".join(eval_tag)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M")
    name = experiment_name or f"feedback-{eval_label}-{mode}-{provider or 'default'}-{timestamp}"

    metadata = {
        "eval_type": f"feedback_{eval_label}",
        "mode": mode,
        "timestamp": timestamp,
        "evaluators": eval_label,
    }
    if provider:
        metadata["provider"] = provider
    if use_judge:
        metadata["judge_model"] = feedback_judge_evaluator.JUDGE_MODEL

    print(f"실험 시작: {name}")
    print(f"Dataset: {dataset_name}")
    print(f"Mode: {mode}")
    print(f"Evaluators: {eval_label}")
    if use_judge:
        print(f"Judge Model: {feedback_judge_evaluator.JUDGE_MODEL}")
    print(f"Concurrency: {max_concurrency}")
    print("-" * 60)

    result = dataset.run_experiment(
        name=name,
        description=f"피드백 텍스트 품질 평가 ({eval_label}) | {mode} | {timestamp}",
        task=feedback_eval_task,
        evaluators=item_evals,
        run_evaluators=run_evals,
        max_concurrency=max_concurrency,
        metadata=metadata,
    )

    print("\n" + "=" * 60)
    print("실험 결과")
    print("=" * 60)
    print(result.format())

    _print_summary(result, use_judge=use_judge)

    return result


def _print_summary(result, use_judge: bool = False):
    """실험 결과 요약 출력"""
    print("\n" + "-" * 60)
    print("Run-level 평가 결과")
    print("-" * 60)

    judge_metrics = {
        "priority_compliance_avg",
        "factual_correctness_avg",
        "actionability_avg",
        "feedback_quality_score",
    }

    for eval_result in result.run_evaluations:
        value_str = f"{eval_result.value}" if eval_result.value is not None else "N/A"
        comment = eval_result.comment or ""
        print(f"  {eval_result.name}: {value_str}")
        if comment:
            print(f"    └─ {comment}")

    verdicts = []
    for eval_result in result.run_evaluations:
        if eval_result.value is None:
            continue
        v = eval_result.value
        name = eval_result.name

        if name in judge_metrics:
            if v >= 4.0:
                verdicts.append(f"{name}={v:.2f}/5 (양호)")
            elif v >= 3.0:
                verdicts.append(f"{name}={v:.2f}/5 (보통)")
            else:
                verdicts.append(f"{name}={v:.2f}/5 (개선 필요)")
        else:
            if v >= 0.85:
                verdicts.append(f"{name}={v:.3f} (양호)")
            elif v >= 0.7:
                verdicts.append(f"{name}={v:.3f} (개선 필요)")
            else:
                verdicts.append(f"{name}={v:.3f} (심각)")

    if verdicts:
        print(f"\n  종합: {' | '.join(verdicts)}")


def parse_args():
    parser = argparse.ArgumentParser(description="피드백 텍스트 품질 오프라인 평가")
    parser.add_argument(
        "--mode",
        type=str,
        choices=["practice", "real"],
        default="practice",
        help="평가 모드 (기본: practice)",
    )
    parser.add_argument(
        "--name",
        type=str,
        default=None,
        help="실험 이름 (기본: 자동 생성)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=3,
        help="동시 실행 수 (기본: 3)",
    )
    parser.add_argument(
        "--provider",
        type=str,
        choices=["gemini", "vllm"],
        default=None,
        help="LLM provider 지정",
    )
    parser.add_argument(
        "--judge",
        action="store_true",
        default=False,
        help="LLM-as-Judge 평가 포함 (Claude)",
    )
    parser.add_argument(
        "--no-rule",
        action="store_true",
        default=False,
        help="Rule-based 평가 제외 (--judge와 함께 사용)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_feedback_evaluation(
        mode=args.mode,
        experiment_name=args.name,
        max_concurrency=args.concurrency,
        provider=args.provider,
        use_rule=not args.no_rule,
        use_judge=args.judge,
    )
