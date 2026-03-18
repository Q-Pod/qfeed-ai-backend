"""Router 분석 품질 Golden dataset을 Langfuse Dataset으로 업로드.

Usage:
    python -m tests.evaluation_v2.setup_router_analysis_dataset
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv
from langfuse import get_client

DATASET_NAME = "golden-router-analysis-v2"
DATASET_DIR = Path(__file__).parent / "datasets"

load_dotenv()


def setup_router_analysis_dataset(dataset_path: str | None = None) -> None:
    """Router 분석 품질 평가용 Golden dataset을 Langfuse에 업로드한다."""
    langfuse = get_client()

    path = (
        Path(dataset_path)
        if dataset_path
        else DATASET_DIR / "golden_router_analysis.json"
    )
    with open(path, encoding="utf-8") as f:
        golden_data = json.load(f)

    langfuse.create_dataset(
        name=DATASET_NAME,
        description="질문 생성 Router 분석 품질 평가용 Golden Dataset (v2)",
        metadata={
            "version": "v1",
            "eval_type": "router_analysis_quality",
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
                "route": expected.get("expected_route_decision"),
            },
        )
        print(f"  [+] {case['id']}: {case.get('description', '')}")

    langfuse.flush()
    print(f"\nDataset '{DATASET_NAME}' 생성 완료 ({len(golden_data)} items)")


if __name__ == "__main__":
    setup_router_analysis_dataset()
