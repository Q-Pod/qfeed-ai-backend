# """Cross-run 질문 다양성 평가 스크립트
"""Cross-run 질문 다양성 평가 스크립트

여러 Langfuse experiment 결과에서 생성된 질문들을 모아,
LLM-as-Judge의 다양성 프롬프트로 한 번 더 평가한다.

용도:
    - follow_up: golden-follow-up 기반 꼬리질문들의 cross-run 다양성
    - new_topic: golden-new-topic 기반 메인 질문들의 cross-run 다양성

Usage 예시:
    # follow_up experiment들 중 이름에 'follow-up-judge'가 포함된 것만 대상으로
    python -m tests.evaluation.cross_run_diversity --target follow_up --name-substring follow-up-judge --dataset-name golden-follow-up

    # new_topic experiment들 중 이름에 'new-topic-judge'가 포함된 것만 대상으로
    python -m tests.evaluation.cross_run_diversity --target new_topic --name-substring new-topic-judge --dataset-name golden-new-topic

    # 모델별로 분리해서 평가
    python -m tests.evaluation.cross_run_diversity --target follow_up --dataset-name golden-follow-up --group-by-model
"""

import sys
import argparse
from pathlib import Path
from typing import Literal
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv

load_dotenv()

from langfuse import get_client

from tests.evaluation.prompts.follow_up_judge_prompts import (
    FOLLOW_UP_DIVERSITY_SYSTEM,
    build_follow_up_diversity_user_prompt,
)
from tests.evaluation.prompts.new_topic_judge_prompts import (
    NEW_TOPIC_DIVERSITY_SYSTEM,
    build_new_topic_diversity_user_prompt,
)
from tests.evaluation.evaluators.follow_up_judge_evaluator import _call_judge as _call_follow_up_judge
from tests.evaluation.evaluators.new_topic_judge_evaluator import _call_judge as _call_new_topic_judge


TargetType = Literal["follow_up", "new_topic"]

_MAX_QUESTIONS = 100


def _collect_questions(
    dataset_name: str,
    name_substring: str | None,
    limit: int | None,
    group_by_model: bool = False,
) -> dict[str, list[str]]:
    """Langfuse dataset runs에서 question_text를 cross-run으로 수집.
    
    Args:
        dataset_name: Langfuse에 등록된 dataset 이름
        name_substring: run 이름에 포함되어야 하는 부분 문자열 (필터링용)
        limit: 대상 run 개수 상한
        group_by_model: True면 모델별로 그룹화, False면 'all' 키로 통합
    
    Returns:
        모델명(또는 'all') -> 질문 리스트 딕셔너리
    """
    client = get_client()

    # 1. Dataset의 모든 runs 조회
    # Langfuse SDK v3: langfuse.api.datasets.get_runs(dataset_name)
    try:
        dataset_runs = client.api.datasets.get_runs(dataset_name)
    except Exception as e:
        print(f"Dataset '{dataset_name}'을 찾을 수 없거나 runs 조회 실패: {e}")
        return {}

    # 2. run 이름으로 필터링
    selected_runs = []
    for run in dataset_runs.data:
        run_name = getattr(run, "name", "") or ""
        if name_substring and name_substring not in run_name:
            continue
        selected_runs.append(run)

    if not selected_runs:
        print(f"조건에 맞는 dataset run을 찾지 못했습니다. (dataset: {dataset_name}, substring: {name_substring})")
        return {}

    if limit is not None:
        selected_runs = selected_runs[:limit]

    print(f"총 {len(selected_runs)}개의 dataset run을 찾았습니다.")

    # 3. 각 run의 items에서 output 수집
    # 모델별로 그룹화할 경우를 대비해 딕셔너리 사용
    questions_by_model: dict[str, list[str]] = defaultdict(list)

    for run in selected_runs:
        run_name = getattr(run, "name", "unknown")
        dataset_id = getattr(run, "dataset_id", None)
        
        if not dataset_id:
            print(f"  [WARN] Run '{run_name}'에 dataset_id가 없습니다. 스킵.")
            continue

        # 페이지네이션으로 모든 run items 조회
        page = 1
        while True:
            try:
                run_items = client.api.dataset_run_items.list(
                    dataset_id=dataset_id,
                    run_name=run_name,
                    page=page
                )
            except Exception as e:
                print(f"  [ERROR] Run '{run_name}' items 조회 실패: {e}")
                break

            if not run_items.data:
                break

            for item in run_items.data:
                # trace에서 output 가져오기
                trace_id = getattr(item, "trace_id", None)
                if not trace_id:
                    continue

                try:
                    trace = client.api.trace.get(trace_id)
                except Exception:
                    continue

                output = getattr(trace, "output", None) or {}
                
                # output이 dict가 아닌 경우 처리
                if isinstance(output, str):
                    q = output.strip()
                elif isinstance(output, dict):
                    q = (output.get("question_text") or output.get("question") or "").strip()
                else:
                    q = ""

                if not q:
                    continue

                # 모델 정보 추출 (metadata 또는 run_name에서)
                if group_by_model:
                    # 방법 1: trace metadata에서 모델 정보 추출
                    metadata = getattr(trace, "metadata", {}) or {}
                    model = metadata.get("model") or metadata.get("model_name") or ""
                    
                    # 방법 2: run_name에서 모델 추론 (예: "vllm-exaone-run-1", "gemini-run-1")
                    if not model:
                        run_name_lower = run_name.lower()
                        if "vllm" in run_name_lower or "exaone" in run_name_lower or "skt" in run_name_lower or "qwen" in run_name_lower:
                            model = "vllm"
                        elif "gemini" in run_name_lower:
                            model = "gemini"
                        else:
                            model = "unknown"
                    
                    # 모델명 정규화
                    model_lower = model.lower()
                    if any(k in model_lower for k in ["vllm", "exaone", "skt", "qwen", "local"]):
                        model = "vllm"
                    elif "gemini" in model_lower:
                        model = "gemini"
                    
                    questions_by_model[model].append(q)
                else:
                    questions_by_model["all"].append(q)

            page += 1

    # 결과 요약 출력
    for model, questions in questions_by_model.items():
        print(f"  - {model}: {len(questions)}개 질문 수집")

    return dict(questions_by_model)


def _evaluate_diversity_follow_up(question_texts: list[str], model_name: str = "all") -> None:
    if len(question_texts) < 2:
        print(f"follow_up ({model_name}): 질문이 2개 미만이라 다양성 평가를 수행할 수 없습니다.")
        return

    total = len(question_texts)
    if total > _MAX_QUESTIONS:
        step = total / _MAX_QUESTIONS
        indices = [int(i * step) for i in range(_MAX_QUESTIONS)]
        question_texts = [question_texts[i] for i in indices]

    user_prompt = build_follow_up_diversity_user_prompt(question_texts)
    result = _call_follow_up_judge(FOLLOW_UP_DIVERSITY_SYSTEM, user_prompt)

    score = result.get("score")
    reasoning = result.get("reasoning", "")

    print(f"\n=== Cross-run Follow-up Diversity [{model_name}] ===")
    print(f"총 수집 질문 수: {total} (평가에 사용 {len(question_texts)}개)")
    print(f"점수: {score} / 5")
    print(f"이유: {reasoning}")


def _evaluate_diversity_new_topic(question_texts: list[str], model_name: str = "all") -> None:
    if len(question_texts) < 2:
        print(f"new_topic ({model_name}): 질문이 2개 미만이라 다양성 평가를 수행할 수 없습니다.")
        return

    total = len(question_texts)
    if total > _MAX_QUESTIONS:
        step = total / _MAX_QUESTIONS
        indices = [int(i * step) for i in range(_MAX_QUESTIONS)]
        question_texts = [question_texts[i] for i in indices]

    user_prompt = build_new_topic_diversity_user_prompt(question_texts)
    result = _call_new_topic_judge(NEW_TOPIC_DIVERSITY_SYSTEM, user_prompt)

    score = result.get("score")
    reasoning = result.get("reasoning", "")

    print(f"\n=== Cross-run New-topic Diversity [{model_name}] ===")
    print(f"총 수집 질문 수: {total} (평가에 사용 {len(question_texts)}개)")
    print(f"점수: {score} / 5")
    print(f"이유: {reasoning}")


def run_cross_run_diversity(
    target: TargetType,
    dataset_name: str,
    name_substring: str | None,
    limit_experiments: int | None,
    group_by_model: bool = False,
) -> None:
    questions_by_model = _collect_questions(
        dataset_name=dataset_name,
        name_substring=name_substring,
        limit=limit_experiments,
        group_by_model=group_by_model,
    )
    
    if not questions_by_model:
        return

    for model_name, questions in questions_by_model.items():
        if target == "follow_up":
            _evaluate_diversity_follow_up(questions, model_name)
        else:
            _evaluate_diversity_new_topic(questions, model_name)


def parse_args():
    parser = argparse.ArgumentParser(description="Cross-run 질문 다양성 LLM-as-Judge 평가")
    parser.add_argument(
        "--target",
        type=str,
        choices=["follow_up", "new_topic"],
        required=True,
        help="대상 파이프라인 (follow_up / new_topic)",
    )
    parser.add_argument(
        "--dataset-name",
        type=str,
        required=True,
        help="Langfuse에 등록된 dataset 이름 (예: golden-follow-up, golden-new-topic)",
    )
    parser.add_argument(
        "--name-substring",
        type=str,
        default=None,
        help="dataset run 이름에 포함되어야 하는 부분 문자열 (필터링용)",
    )
    parser.add_argument(
        "--limit-experiments",
        type=int,
        default=None,
        help="대상 dataset run 개수 상한 (최신 순 일부만 보고 싶을 때 사용)",
    )
    parser.add_argument(
        "--group-by-model",
        action="store_true",
        help="vllm, gemini 등 모델별로 그룹화하여 별도 평가 수행",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_cross_run_diversity(
        target=args.target,
        dataset_name=args.dataset_name,
        name_substring=args.name_substring,
        limit_experiments=args.limit_experiments,
        group_by_model=args.group_by_model,
    )

# 여러 Langfuse experiment 결과에서 생성된 질문들을 모아,
# LLM-as-Judge의 다양성 프롬프트로 한 번 더 평가한다.

# 용도:
#     - follow_up: golden-follow-up 기반 꼬리질문들의 cross-run 다양성
#     - new_topic: golden-new-topic 기반 메인 질문들의 cross-run 다양성

# Usage 예시:
#     # follow_up experiment들 중 이름에 'follow-up-judge'가 포함된 것만 대상으로
#     python -m tests.evaluation.cross_run_diversity --target follow_up --name-substring follow-up-judge

#     # new_topic experiment들 중 이름에 'new-topic-judge'가 포함된 것만 대상으로
#     python -m tests.evaluation.cross_run_diversity --target new_topic --name-substring new-topic-judge
# """

# import sys
# import argparse
# from pathlib import Path
# from typing import Literal

# sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# from dotenv import load_dotenv

# load_dotenv()

# from langfuse import get_client

# from tests.evaluation.prompts.follow_up_judge_prompts import (
#     FOLLOW_UP_DIVERSITY_SYSTEM,
#     build_follow_up_diversity_user_prompt,
# )
# from tests.evaluation.prompts.new_topic_judge_prompts import (
#     NEW_TOPIC_DIVERSITY_SYSTEM,
#     build_new_topic_diversity_user_prompt,
# )
# from tests.evaluation.evaluators.follow_up_judge_evaluator import _call_judge as _call_follow_up_judge
# from tests.evaluation.evaluators.new_topic_judge_evaluator import _call_judge as _call_new_topic_judge


# TargetType = Literal["follow_up", "new_topic"]

# _MAX_QUESTIONS = 100


# def _collect_questions(
#     target: TargetType,
#     name_substring: str | None,
#     limit: int | None,
# ) -> list[str]:
#     """Langfuse experiments에서 question_text를 cross-run으로 수집."""
#     client = get_client()

#     experiments = client.get_experiments()
#     selected = []
#     for exp in experiments:
#         name = getattr(exp, "name", "") or ""
#         if name_substring and name_substring not in name:
#             continue
#         selected.append(exp)

#     if not selected:
#         print("조건에 맞는 experiment를 찾지 못했습니다.")
#         return []

#     if limit is not None:
#         selected = selected[:limit]

#     all_questions: list[str] = []

#     for exp in selected:
#         # Langfuse Python SDK의 experiment 결과 조회
#         # 각 experiment는 runs를 포함하고, 각 run에는 outputs가 있음.
#         runs = client.get_experiment_runs(exp.id)
#         for run in runs:
#             output = getattr(run, "output", None) or {}
#             q = (output.get("question_text") or "").strip()
#             if q:
#                 all_questions.append(q)

#     return all_questions


# def _evaluate_diversity_follow_up(question_texts: list[str]) -> None:
#     if len(question_texts) < 2:
#         print("follow_up: 질문이 2개 미만이라 다양성 평가를 수행할 수 없습니다.")
#         return

#     total = len(question_texts)
#     if total > _MAX_QUESTIONS:
#         step = total / _MAX_QUESTIONS
#         indices = [int(i * step) for i in range(_MAX_QUESTIONS)]
#         question_texts = [question_texts[i] for i in indices]

#     user_prompt = build_follow_up_diversity_user_prompt(question_texts)
#     result = _call_follow_up_judge(FOLLOW_UP_DIVERSITY_SYSTEM, user_prompt)

#     score = result.get("score")
#     reasoning = result.get("reasoning", "")

#     print("\n=== Cross-run Follow-up Diversity ===")
#     print(f"총 수집 질문 수: {total} (평가에 사용 {len(question_texts)}개)")
#     print(f"점수: {score} / 5")
#     print(f"이유: {reasoning}")


# def _evaluate_diversity_new_topic(question_texts: list[str]) -> None:
#     if len(question_texts) < 2:
#         print("new_topic: 질문이 2개 미만이라 다양성 평가를 수행할 수 없습니다.")
#         return

#     total = len(question_texts)
#     if total > _MAX_QUESTIONS:
#         step = total / _MAX_QUESTIONS
#         indices = [int(i * step) for i in range(_MAX_QUESTIONS)]
#         question_texts = [question_texts[i] for i in indices]

#     user_prompt = build_new_topic_diversity_user_prompt(question_texts)
#     result = _call_new_topic_judge(NEW_TOPIC_DIVERSITY_SYSTEM, user_prompt)

#     score = result.get("score")
#     reasoning = result.get("reasoning", "")

#     print("\n=== Cross-run New-topic Diversity ===")
#     print(f"총 수집 질문 수: {total} (평가에 사용 {len(question_texts)}개)")
#     print(f"점수: {score} / 5")
#     print(f"이유: {reasoning}")


# def run_cross_run_diversity(
#     target: TargetType,
#     name_substring: str | None,
#     limit_experiments: int | None,
# ) -> None:
#     questions = _collect_questions(target, name_substring, limit_experiments)
#     if not questions:
#         return

#     if target == "follow_up":
#         _evaluate_diversity_follow_up(questions)
#     else:
#         _evaluate_diversity_new_topic(questions)


# def parse_args():
#     parser = argparse.ArgumentParser(description="Cross-run 질문 다양성 LLM-as-Judge 평가")
#     parser.add_argument(
#         "--target",
#         type=str,
#         choices=["follow_up", "new_topic"],
#         required=True,
#         help="대상 파이프라인 (follow_up / new_topic)",
#     )
#     parser.add_argument(
#         "--name-substring",
#         type=str,
#         default=None,
#         help="experiment 이름에 포함되어야 하는 부분 문자열 (필터링용)",
#     )
#     parser.add_argument(
#         "--limit-experiments",
#         type=int,
#         default=None,
#         help="대상 experiment 개수 상한 (최신 순 일부만 보고 싶을 때 사용)",
#     )
#     return parser.parse_args()


# if __name__ == "__main__":
#     args = parse_args()
#     run_cross_run_diversity(
#         target=args.target, name_substring=args.name_substring, limit_experiments=args.limit_experiments
#     )

