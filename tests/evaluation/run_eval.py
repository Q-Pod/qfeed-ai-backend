"""루브릭 평가 오프라인 실험 실행

Golden dataset의 각 케이스에 대해 rubric_evaluator를 실행하고,
실제 LLM이 매긴 점수의 정확도(MAE)와 변별력(Spearman)을 평가한다.

Usage:
    # 1. (최초 1회) Langfuse에 golden dataset 업로드
    python -m tests.evaluation.setup_dataset

    # 2. 루브릭 평가 실험 실행
    python -m tests.evaluation.run_eval

    # 3. 특정 provider로 실행
    python -m tests.evaluation.run_eval --provider gemini
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv
load_dotenv()

from langfuse import get_client

from tests.evaluation.target import rubric_eval_task
from tests.evaluation.evaluators.rubric_evaluator import (
    all_item_evaluators,
    all_run_evaluators,
)
from tests.evaluation.setup_dataset import DATASET_NAME


def run_rubric_evaluation(
    experiment_name: str | None = None,
    max_concurrency: int = 3,
    provider: str | None = None,
):
    """루브릭 평가 실험 실행

    Args:
        experiment_name: 실험 이름 (기본: 자동 생성)
        max_concurrency: 동시 실행 수
        provider: LLM provider (gemini / vllm)
    """
    langfuse = get_client()

    try:
        dataset = langfuse.get_dataset(DATASET_NAME)
    except Exception:
        print(f"Dataset '{DATASET_NAME}'이 존재하지 않습니다.")
        print("먼저 실행: python -m tests.evaluation.setup_dataset")
        sys.exit(1)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M")
    name = experiment_name or f"rubric-eval-{provider}-{timestamp}"

    metadata = {
        "eval_type": "rubric",
        "mode": "practice",
        "timestamp": timestamp,
    }
    if provider:
        metadata["provider"] = provider

    print(f"실험 시작: {name}")
    print(f"Dataset: {DATASET_NAME}")
    print(f"Concurrency: {max_concurrency}")
    print("-" * 60)

    result = dataset.run_experiment(
        name=name,
        description=f"루브릭 점수 calibration 평가 | {timestamp}",
        task=rubric_eval_task,
        evaluators=all_item_evaluators,
        run_evaluators=all_run_evaluators,
        max_concurrency=max_concurrency,
        metadata=metadata,
    )

    print("\n" + "=" * 60)
    print("실험 결과")
    print("=" * 60)
    print(result.format())

    _print_summary(result)

    return result


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

    mae_eval = next(
        (e for e in result.run_evaluations if e.name == "dimension_mae"),
        None,
    )
    spearman_eval = next(
        (e for e in result.run_evaluations if e.name == "dimension_spearman"),
        None,
    )

    verdicts = []
    if mae_eval and mae_eval.value is not None:
        mae = mae_eval.value
        if mae <= 0.5:
            verdicts.append(f"MAE={mae:.3f} (양호)")
        elif mae <= 1.0:
            verdicts.append(f"MAE={mae:.3f} (개선 필요)")
        else:
            verdicts.append(f"MAE={mae:.3f} (calibration 재검토)")

    if spearman_eval and spearman_eval.value is not None:
        rho = spearman_eval.value
        if rho >= 0.7:
            verdicts.append(f"Spearman={rho:.3f} (변별력 양호)")
        elif rho >= 0.4:
            verdicts.append(f"Spearman={rho:.3f} (변별력 보통)")
        else:
            verdicts.append(f"Spearman={rho:.3f} (변별력 부족)")

    bias_eval = next(
        (e for e in result.run_evaluations if e.name == "dimension_bias"),
        None,
    )
    if bias_eval and bias_eval.value is not None:
        bias = bias_eval.value
        if bias > 0.3:
            verdicts.append(f"Bias={bias:+.3f} (과대채점 경향)")
        elif bias > 0:
            verdicts.append(f"Bias={bias:+.3f} (약간 후한 채점)")
        elif bias > -0.3:
            verdicts.append(f"Bias={bias:+.3f} (약간 엄격한 채점)")
        else:
            verdicts.append(f"Bias={bias:+.3f} (과소채점 경향)")

    cross_corr_eval = next(
        (e for e in result.run_evaluations if e.name == "dimension_cross_corr"),
        None,
    )
    if cross_corr_eval and cross_corr_eval.value is not None:
        cc = cross_corr_eval.value
        if cc > 0.85:
            verdicts.append(f"CrossCorr={cc:.3f} (후광효과 의심)")
        elif cc > 0.6:
            verdicts.append(f"CrossCorr={cc:.3f} (적정 상관)")
        else:
            verdicts.append(f"CrossCorr={cc:.3f} (차원 독립성 양호)")

    if verdicts:
        print(f"\n  종합: {' | '.join(verdicts)}")


def parse_args():
    parser = argparse.ArgumentParser(description="루브릭 평가 오프라인 실험")
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
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_rubric_evaluation(
        experiment_name=args.name,
        max_concurrency=args.concurrency,
        provider=args.provider,
    )
