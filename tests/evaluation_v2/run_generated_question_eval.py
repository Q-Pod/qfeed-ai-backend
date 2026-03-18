"""생성된 질문 품질 오프라인 평가 실행.

평가 방식:
- LLM-as-Judge
- 생성 질문 루브릭 6지표 + portfolio 전용 1지표

Usage:
    # 1. (최초 1회) Langfuse에 dataset 업로드
    python -m tests.evaluation_v2.setup_generated_question_dataset

    # 2. 평가 실행
    python -m tests.evaluation_v2.run_generated_question_eval
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv
from langfuse import get_client

from tests.evaluation_v2.evaluators import generated_question_judge_evaluator
from tests.evaluation_v2.generated_question_target import generated_question_eval_task
from tests.evaluation_v2.setup_generated_question_dataset import DATASET_NAME

load_dotenv()


def run_generated_question_evaluation(
    experiment_name: str | None = None,
    max_concurrency: int = 2,
    provider: str | None = None,
):
    """생성 질문 품질 평가를 실행한다."""
    langfuse = get_client()

    try:
        dataset = langfuse.get_dataset(DATASET_NAME)
    except Exception:
        print(f"Dataset '{DATASET_NAME}'이 존재하지 않습니다.")
        print("먼저 실행: python -m tests.evaluation_v2.setup_generated_question_dataset")
        sys.exit(1)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M")
    name = experiment_name or f"generated-question-{provider or 'default'}-{timestamp}"

    metadata = {
        "eval_type": "generated_question_judge_v2",
        "timestamp": timestamp,
        "judge_model": generated_question_judge_evaluator.JUDGE_MODEL,
    }
    if provider:
        metadata["provider"] = provider

    print(f"실험 시작: {name}")
    print(f"Dataset: {DATASET_NAME}")
    print(
        "Evaluators: direction_adherence, naturalness, non_repetition, "
        "single_focus, appropriate_length, technical_factuality, "
        "portfolio_grounding"
    )
    print(f"Concurrency: {max_concurrency}")
    print("-" * 60)

    result = dataset.run_experiment(
        name=name,
        description=f"생성된 질문 품질 평가 (LLM-as-Judge) | {timestamp}",
        task=generated_question_eval_task,
        evaluators=generated_question_judge_evaluator.all_item_evaluators,
        run_evaluators=generated_question_judge_evaluator.all_run_evaluators,
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
    "gq_direction_adherence_avg",
    "gq_naturalness_avg",
    "gq_non_repetition_avg",
    "gq_single_focus_avg",
    "gq_appropriate_length_avg",
    "gq_technical_factuality_avg",
    "gq_portfolio_grounding_avg",
    "gq_quality_score_avg",
}


def _verdict(name: str, value: float) -> str:
    if name in JUDGE_METRICS:
        if value >= 4.0:
            return f"{name}={value:.2f}/5.0 (양호)"
        if value >= 3.0:
            return f"{name}={value:.2f}/5.0 (개선 필요)"
        return f"{name}={value:.2f}/5.0 (심각)"

    if name == "gq_pass_rate":
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
        description="생성된 질문 품질 오프라인 평가 (LLM-as-Judge)"
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
    run_generated_question_evaluation(
        experiment_name=args.name,
        max_concurrency=args.concurrency,
        provider=args.provider,
    )
