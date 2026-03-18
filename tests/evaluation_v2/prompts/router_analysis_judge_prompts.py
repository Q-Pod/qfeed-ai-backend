"""Router 분석 품질 LLM-as-Judge 프롬프트."""

import json
from typing import Any


ROUTER_ANALYSIS_JUDGE_SYSTEM = """당신은 시니어 기술면접관이자 LLM 평가자입니다.
주어진 면접 시나리오에서 router 출력이 골든 기준과 얼마나 잘 맞는지 평가하세요.

[당신이 평가할 것]
1. analysis_text_alignment
- router의 서술형 분석 텍스트가 골든 분석과 개념적으로 얼마나 잘 맞는지 0.0~1.0으로 평가
- 표현이 달라도 의미가 같으면 높게 평가
- 답변을 오독했거나 핵심을 놓치면 낮게 평가

2. direction_detail_alignment
- follow_up 케이스에서 router의 direction_detail이 골든 방향과 얼마나 잘 맞는지 0.0~1.0으로 평가
- expected_follow_up_direction 자체의 일치 여부는 별도 코드에서 계산하므로,
  여기서는 direction_detail의 구체성과 정렬성을 본다
- follow_up이 아닌 케이스거나 방향 평가가 비적용이면 null

[출력 규칙]
- 반드시 JSON만 반환
- 점수는 0.0~1.0 범위의 숫자
- 비적용 항목은 null
- 애매하면 보수적으로 채점

반드시 아래 JSON만 출력하세요:
{
  "analysis_text_alignment": <0.0-1.0 또는 null>,
  "direction_detail_alignment": <0.0-1.0 또는 null>,
  "analysis_reasoning": "<근거>",
  "direction_reasoning": "<근거>"
}
"""


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def build_router_analysis_judge_prompt(
    *,
    output: dict[str, Any],
    expected_output: dict[str, Any],
) -> str:
    """Router 평가용 judge prompt 생성."""
    scenario = output.get("input_snapshot", {})
    metric_app = expected_output.get("metric_applicability", {})

    expected_view = {
        "expected_route_decision": expected_output.get("expected_route_decision"),
        "expected_analysis": expected_output.get("expected_analysis"),
        "expected_follow_up_direction": expected_output.get(
            "expected_follow_up_direction"
        ),
        "direction_detail_reference": expected_output.get(
            "direction_detail_reference"
        ),
        "direction_detail_keywords": expected_output.get(
            "direction_detail_keywords", []
        ),
        "expected_topic_transition_reason": expected_output.get(
            "expected_topic_transition_reason"
        ),
        "judge_notes": expected_output.get("judge_notes"),
        "tags": expected_output.get("tags", []),
        "metric_applicability": metric_app,
    }

    actual_view = {
        "route_decision": output.get("route_decision"),
        "route_reasoning": output.get("route_reasoning"),
        "follow_up_direction": output.get("follow_up_direction"),
        "direction_detail": output.get("direction_detail"),
        "analysis": output.get("analysis"),
        "topic_transition_reason": output.get("topic_transition_reason"),
    }

    return (
        "[면접 시나리오]\n"
        f"{_dump(scenario)}\n\n"
        "[골든 기준]\n"
        f"{_dump(expected_view)}\n\n"
        "[실제 router 출력]\n"
        f"{_dump(actual_view)}\n\n"
        "골든 기준 대비 실제 router 출력의 분석 서술 정렬성과 direction_detail 정렬성을 평가하세요."
    )
