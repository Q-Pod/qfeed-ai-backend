"""Router 분석 품질 오프라인 평가 실행.

Usage:
    # 1. (최초 1회) Langfuse에 dataset 업로드
    python -m tests.evaluation_v2.setup_router_analysis_dataset

    # 2. 평가 실행
    python -m tests.evaluation_v2.run_router_analysis_eval
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv
from langfuse import get_client

from tests.evaluation_v2.evaluators import router_analysis_judge_evaluator
from tests.evaluation_v2.router_analysis_target import router_analysis_eval_task
from tests.evaluation_v2.setup_router_analysis_dataset import DATASET_NAME

load_dotenv()


def run_router_analysis_evaluation(
    experiment_name: str | None = None,
    max_concurrency: int = 2,
    provider: str | None = None,
):
    """Router 분석 품질 평가를 실행한다."""
    langfuse = get_client()

    try:
        dataset = langfuse.get_dataset(DATASET_NAME)
    except Exception:
        print(f"Dataset '{DATASET_NAME}'이 존재하지 않습니다.")
        print("먼저 실행: python -m tests.evaluation_v2.setup_router_analysis_dataset")
        sys.exit(1)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M")
    name = experiment_name or f"router-analysis-{provider or 'default'}-{timestamp}"

    metadata = {
        "eval_type": "router_analysis_judge_v2",
        "timestamp": timestamp,
        "judge_model": router_analysis_judge_evaluator.JUDGE_MODEL,
    }
    if provider:
        metadata["provider"] = provider

    print(f"실험 시작: {name}")
    print(f"Dataset: {DATASET_NAME}")
    print("Evaluators: analysis_accuracy, direction_appropriateness, routing_decision")
    print(f"Concurrency: {max_concurrency}")
    print("-" * 60)

    result = dataset.run_experiment(
        name=name,
        description=f"Router 분석 품질 평가 (LLM-as-Judge) | {timestamp}",
        task=router_analysis_eval_task,
        evaluators=router_analysis_judge_evaluator.all_item_evaluators,
        run_evaluators=router_analysis_judge_evaluator.all_run_evaluators,
        max_concurrency=max_concurrency,
        metadata=metadata,
    )

    print("\n" + "=" * 60)
    print("실험 결과")
    print("=" * 60)
    print(result.format())
    _print_summary(result)

    return result


def _verdict(name: str, value: float) -> str:
    if name.endswith("_avg"):
        if value >= 0.85:
            return f"{name}={value:.3f} (양호)"
        if value >= 0.70:
            return f"{name}={value:.3f} (개선 필요)"
        return f"{name}={value:.3f} (심각)"

    if name == "router_pass_rate":
        if value >= 0.8:
            return f"{name}={value:.3f} (양호)"
        if value >= 0.6:
            return f"{name}={value:.3f} (개선 필요)"
        return f"{name}={value:.3f} (심각)"

    return f"{name}={value:.3f}"


def _print_summary(result) -> None:
    print("\n" + "-" * 60)
    print("Run-level 평가 결과")
    print("-" * 60)

    verdicts = []
    for eval_result in result.run_evaluations:
        value_str = f"{eval_result.value}" if eval_result.value is not None else "N/A"
        comment = eval_result.comment or ""
        print(f"  {eval_result.name}: {value_str}")
        if comment:
            print(f"    └─ {comment}")

        if eval_result.value is not None:
            verdicts.append(_verdict(eval_result.name, float(eval_result.value)))

    if verdicts:
        print(f"\n  종합: {' | '.join(verdicts)}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Router 분석 품질 오프라인 평가 (LLM-as-Judge)"
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
        default=2,
        help="동시 실행 수 (기본: 2)",
    )
    parser.add_argument(
        "--provider",
        type=str,
        choices=["gemini", "vllm"],
        default=None,
        help="메타데이터에 기록할 provider 이름",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_router_analysis_evaluation(
        experiment_name=args.name,
        max_concurrency=args.concurrency,
        provider=args.provider,
    )
