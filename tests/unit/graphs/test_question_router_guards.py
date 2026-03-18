import pytest

from graphs.nodes.CS.question_router import _parse_router_result as parse_cs_router_result
from graphs.nodes.PF.question_router import _parse_router_result as parse_pf_router_result
from schemas.question import (
    RouteDecision,
    CSAnswerAnalysis,
    CSNewTopicResult,
    EndSessionRouterResult,
    PortfolioAnswerAnalysis,
    PortfolioNewTopicResult,
)


class TestQuestionRouterTopicCapGuards:
    def test_cs_최대_토픽_도달시_new_topic을_end_session으로_강제(self):
        result = CSNewTopicResult(
            analysis=CSAnswerAnalysis(
                correctness="정확합니다.",
                has_error=False,
                completeness="핵심 요소를 포함했습니다.",
                has_missing_concepts=False,
                depth="원리까지 설명했습니다.",
                is_superficial=False,
                is_well_structured=True,
            ),
            topic_transition_reason="현재 토픽을 충분히 다뤘습니다.",
            reasoning="새 토픽으로 넘어가도 됩니다.",
        )
        state = {
            "session_id": "cs-topic-cap",
            "current_topic_count": 3,
            "max_topics": 3,
        }

        parsed = parse_cs_router_result(result, state)

        assert parsed["route_decision"] == RouteDecision.END_SESSION
        assert "최대 토픽 수(3)" in parsed["route_reasoning"]
        assert parsed["router_analysis"]["has_error"] is False

    def test_cs_최대_토픽_미도달이면_new_topic_유지(self):
        result = CSNewTopicResult(
            analysis=CSAnswerAnalysis(
                correctness="정확합니다.",
                has_error=False,
                completeness="핵심 요소를 포함했습니다.",
                has_missing_concepts=False,
                depth="원리까지 설명했습니다.",
                is_superficial=False,
                is_well_structured=True,
            ),
            topic_transition_reason="현재 토픽을 충분히 다뤘습니다.",
            reasoning="새 토픽으로 넘어가도 됩니다.",
        )
        state = {
            "session_id": "cs-under-cap",
            "current_topic_count": 2,
            "max_topics": 3,
        }

        parsed = parse_cs_router_result(result, state)

        assert parsed["route_decision"] == RouteDecision.NEW_TOPIC
        assert parsed["router_analysis"]["has_error"] is False

    def test_cs_end_session도_router_analysis를_유지(self):
        result = EndSessionRouterResult(
            analysis=CSAnswerAnalysis(
                correctness="정확합니다.",
                has_error=False,
                completeness="핵심 요소를 포함했습니다.",
                has_missing_concepts=False,
                depth="원리까지 설명했습니다.",
                is_superficial=False,
                is_well_structured=True,
            ),
            reasoning="면접을 충분히 진행했습니다.",
        )
        state = {
            "session_id": "cs-end-session",
            "current_topic_count": 3,
            "max_topics": 3,
        }

        parsed = parse_cs_router_result(result, state)

        assert parsed["route_decision"] == RouteDecision.END_SESSION
        assert parsed["router_analysis"]["has_error"] is False

    def test_pf_최대_토픽_도달시_new_topic을_end_session으로_강제(self):
        result = PortfolioNewTopicResult(
            analysis=PortfolioAnswerAnalysis(
                completeness="핵심 구현을 충분히 설명했습니다.",
                has_evidence=True,
                has_tradeoff=True,
                has_problem_solving=True,
                is_well_structured=True,
            ),
            topic_transition_reason="현재 토픽을 충분히 다뤘습니다.",
            reasoning="새 토픽으로 넘어가도 됩니다.",
        )
        state = {
            "session_id": "pf-topic-cap",
            "current_topic_count": 3,
            "max_topics": 3,
        }

        parsed = parse_pf_router_result(result, state)

        assert parsed["route_decision"] == RouteDecision.END_SESSION
        assert "최대 토픽 수(3)" in parsed["route_reasoning"]
        assert parsed["router_analysis"]["has_tradeoff"] is True
