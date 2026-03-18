"""새 토픽 질문 생성 품질 오프라인 평가 실행

Golden dataset의 각 케이스에 대해 new_topic LLM을 실행하고,
Rule-based 및/또는 LLM-as-Judge 평가를 수행한다.

Usage:
    # Rule-based만 (기본)
    python -m tests.evaluation.run_new_topic_eval

    # Judge 평가 포함
    python -m tests.evaluation.run_new_topic_eval --judge

    # Judge 평가만 (Rule-based 제외)
    python -m tests.evaluation.run_new_topic_eval --judge --no-rule
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv
load_dotenv()

from langfuse import get_client

from tests.evaluation.new_topic_target import new_topic_eval_task
from tests.evaluation.evaluators import new_topic_evaluator, new_topic_judge_evaluator

DATASET_NAME = "golden-new-topic"


def _build_evaluators(use_rule: bool, use_judge: bool):
    """플래그에 따라 item-level / run-level evaluator 리스트를 조합한다."""
    item_evals = []
    run_evals = []

    if use_rule:
        item_evals.extend(new_topic_evaluator.all_item_evaluators)
        run_evals.extend(new_topic_evaluator.all_run_evaluators)

    if use_judge:
        item_evals.extend(new_topic_judge_evaluator.all_item_evaluators)
        run_evals.extend(new_topic_judge_evaluator.all_run_evaluators)

    return item_evals, run_evals


def run_new_topic_evaluation(
    experiment_name: str | None = None,
    max_concurrency: int = 3,
    provider: str | None = None,
    use_rule: bool = True,
    use_judge: bool = False,
):
    """새 토픽 질문 생성 품질 평가 실행

    Args:
        experiment_name: 실험 이름 (기본: 자동 생성)
        max_concurrency: 동시 실행 수
        provider: LLM provider (gemini / vllm)
        use_rule: Rule-based 평가 포함 여부
        use_judge: LLM-as-Judge 평가 포함 여부
    """
    langfuse = get_client()

    try:
        dataset = langfuse.get_dataset(DATASET_NAME)
    except Exception:
        print(f"Dataset '{DATASET_NAME}'이 존재하지 않습니다.")
        print("먼저 실행: python -m tests.evaluation.setup_new_topic_dataset")
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
    name = experiment_name or f"new-topic-{eval_label}-{provider or 'default'}-{timestamp}"

    metadata = {
        "eval_type": f"new_topic_{eval_label}",
        "timestamp": timestamp,
        "evaluators": eval_label,
    }
    if use_judge:
        metadata["judge_model"] = new_topic_judge_evaluator.JUDGE_MODEL
    if provider:
        metadata["provider"] = provider

    print(f"실험 시작: {name}")
    print(f"Dataset: {DATASET_NAME}")
    print(f"Evaluators: {eval_label}")
    print(f"Concurrency: {max_concurrency}")
    print("-" * 60)

    result = dataset.run_experiment(
        name=name,
        description=f"새 토픽 질문 생성 품질 평가 ({eval_label}) | {timestamp}",
        task=new_topic_eval_task,
        evaluators=item_evals,
        run_evaluators=run_evals,
        max_concurrency=max_concurrency,
        metadata=metadata,
    )

    print("\n" + "=" * 60)
    print("실험 결과")
    print("=" * 60)
    print(result.format())

    _print_summary(result)

    return result


JUDGE_METRICS = {
    "tradeoff_depth_avg",
    "constraint_quality_avg",
    "hook_richness_avg",
    "cushion_quality_avg",
    "new_topic_quality_score",
    "new_topic_diversity",
}


def _verdict(name: str, value: float) -> str:
    """Rule(0~1) vs Judge(1~5) 스케일에 맞는 판정"""
    if name in JUDGE_METRICS:
        if value >= 4.0:
            return f"{name}={value:.2f}/5.0 (양호)"
        elif value >= 3.0:
            return f"{name}={value:.2f}/5.0 (개선 필요)"
        else:
            return f"{name}={value:.2f}/5.0 (심각)"
    else:
        if value >= 0.9:
            return f"{name}={value:.3f} (양호)"
        elif value >= 0.7:
            return f"{name}={value:.3f} (개선 필요)"
        else:
            return f"{name}={value:.3f} (심각)"


def _print_summary(result):
    """실험 결과 요약 출력"""
    print("\n" + "-" * 60)
    print("Run-level 평가 결과")
    print("-" * 60)

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
        verdicts.append(_verdict(eval_result.name, eval_result.value))

    if verdicts:
        print(f"\n  종합: {' | '.join(verdicts)}")


def parse_args():
    parser = argparse.ArgumentParser(description="새 토픽 질문 생성 품질 오프라인 평가")
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
        help="LLM-as-Judge 평가 포함 (미구현)",
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
    run_new_topic_evaluation(
        experiment_name=args.name,
        max_concurrency=args.concurrency,
        provider=args.provider,
        use_rule=not args.no_rule,
        use_judge=args.judge,
    )
