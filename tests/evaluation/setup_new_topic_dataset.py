"""새 토픽 질문 생성 Golden dataset을 Langfuse Dataset으로 업로드

Usage:
    python -m tests.evaluation.setup_new_topic_dataset
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv
load_dotenv()

from langfuse import get_client

DATASET_NAME = "golden-new-topic"
DATASET_DIR = Path(__file__).parent / "datasets"


def setup_new_topic_dataset(dataset_path: str | None = None):
    """새 토픽 Golden dataset을 Langfuse에 업로드

    Args:
        dataset_path: JSON 파일 경로 (기본: datasets/golden_new_topic.json)
    """
    langfuse = get_client()

    path = Path(dataset_path) if dataset_path else DATASET_DIR / "golden_new_topic.json"
    with open(path, encoding="utf-8") as f:
        golden_data = json.load(f)

    langfuse.create_dataset(
        name=DATASET_NAME,
        description="새 토픽 질문 생성 품질 평가 Golden Dataset",
        metadata={
            "version": "v1",
            "items_count": len(golden_data),
        },
    )

    for case in golden_data:
        langfuse.create_dataset_item(
            dataset_name=DATASET_NAME,
            id=case["id"],
            input=case["input"],
            expected_output=case.get("expected_criteria"),
            metadata={
                "case_id": case["id"],
                "description": case.get("description", ""),
                "question_type": case["input"]["question_type"],
            },
        )
        print(f"  [+] {case['id']}: {case['description']}")

    langfuse.flush()
    print(f"\nDataset '{DATASET_NAME}' 생성 완료 ({len(golden_data)} items)")


if __name__ == "__main__":
    setup_new_topic_dataset()
