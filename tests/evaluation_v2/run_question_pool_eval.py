"""질문 풀(question_pool) 품질 오프라인 평가 실행.

평가 방식:
- LLM-as-Judge
- 질문별 루브릭 4지표

Usage:
    # 1. (최초 1회) Langfuse에 dataset 업로드
    python -m tests.evaluation_v2.setup_question_pool_dataset

    # 2. 평가 실행
    python -m tests.evaluation_v2.run_question_pool_eval
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv
from langfuse import get_client

from tests.evaluation_v2.evaluators import question_pool_judge_evaluator
from tests.evaluation_v2.question_pool_target import question_pool_eval_task
from tests.evaluation_v2.setup_question_pool_dataset import DATASET_NAME

load_dotenv()


def run_question_pool_evaluation(
    experiment_name: str | None = None,
    max_concurrency: int = 2,
    provider: str | None = None,
):
    """질문 풀 품질 평가를 실행한다.

    Args:
        experiment_name: 실험 이름 (기본: 자동 생성)
        max_concurrency: 동시 실행 수
        provider: 실행 provider 메타데이터 (현재 task 내부에서는 기본 provider 사용)
    """
    langfuse = get_client()

    try:
        dataset = langfuse.get_dataset(DATASET_NAME)
    except Exception:
        print(f"Dataset '{DATASET_NAME}'이 존재하지 않습니다.")
        print("먼저 실행: python -m tests.evaluation_v2.setup_question_pool_dataset")
        sys.exit(1)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M")
    name = experiment_name or f"qpool-judge-{provider or 'default'}-{timestamp}"

    metadata = {
        "eval_type": "question_pool_judge_v2",
        "timestamp": timestamp,
        "judge_model": question_pool_judge_evaluator.JUDGE_MODEL,
    }
    if provider:
        metadata["provider"] = provider

    print(f"실험 시작: {name}")
    print(f"Dataset: {DATASET_NAME}")
    print("Evaluators: judge")
    print(f"Concurrency: {max_concurrency}")
    print("-" * 60)

    result = dataset.run_experiment(
        name=name,
        description=f"질문 풀 품질 평가 (LLM-as-Judge) | {timestamp}",
        task=question_pool_eval_task,
        evaluators=question_pool_judge_evaluator.all_item_evaluators,
        run_evaluators=question_pool_judge_evaluator.all_run_evaluators,
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
    "qpool_relevance_avg",
    "qpool_specificity_avg",
    "qpool_depth_potential_avg",
    "qpool_interview_fit_avg",
    "qpool_quality_score_avg",
}


def _verdict(name: str, value: float) -> str:
    if name in JUDGE_METRICS:
        if value >= 4.0:
            return f"{name}={value:.2f}/5.0 (양호)"
        if value >= 3.0:
            return f"{name}={value:.2f}/5.0 (개선 필요)"
        return f"{name}={value:.2f}/5.0 (심각)"

    if name == "qpool_pass_rate":
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
        verdicts.append(_verdict(eval_result.name, float(eval_result.value)))

    if verdicts:
        print(f"\n  종합: {' | '.join(verdicts)}")


def parse_args():
    parser = argparse.ArgumentParser(description="질문 풀 품질 오프라인 평가 (LLM-as-Judge)")
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
    run_question_pool_evaluation(
        experiment_name=args.name,
        max_concurrency=args.concurrency,
        provider=args.provider,
    )
