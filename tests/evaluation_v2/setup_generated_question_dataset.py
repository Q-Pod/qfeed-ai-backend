"""생성된 질문 품질 Golden dataset을 Langfuse Dataset으로 업로드.

Usage:
    python -m tests.evaluation_v2.setup_generated_question_dataset
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv
from langfuse import get_client

DATASET_NAME = "golden-generated-question-v3"
DATASET_DIR = Path(__file__).parent / "datasets"

load_dotenv()


def setup_generated_question_dataset(dataset_path: str | None = None) -> None:
    """생성 질문 품질 평가용 Golden dataset을 Langfuse에 업로드한다."""
    langfuse = get_client()

    path = (
        Path(dataset_path)
        if dataset_path
        else DATASET_DIR / "golden_generated_question.json"
    )
    with open(path, encoding="utf-8") as f:
        golden_data = json.load(f)

    langfuse.create_dataset(
        name=DATASET_NAME,
        description="생성된 질문 품질 평가용 Golden Dataset (7-rubric)",
        metadata={
            "version": "v2",
            "eval_type": "generated_question_quality",
            "items_count": len(golden_data),
        },
    )

    for case in golden_data:
        expected = case.get("expected_criteria", {})
        langfuse.create_dataset_item(
            dataset_name=DATASET_NAME,
            id=case["id"],
            input=case["input"],
            expected_output=expected,
            metadata={
                "case_id": case["id"],
                "group": expected.get("scenario_group"),
                "question_type": case["input"].get("question_type"),
                "direction": case["input"].get("follow_up_direction"),
            },
        )
        print(f"  [+] {case['id']}: {case.get('description', '')}")

    langfuse.flush()
    print(f"\nDataset '{DATASET_NAME}' 생성 완료 ({len(golden_data)} items)")


if __name__ == "__main__":
    setup_generated_question_dataset()
