from types import SimpleNamespace

import pytest

from graphs.feedback.state import create_initial_state
from graphs.nodes import practice_answer_analyzer as analyzer
from schemas.feedback import CSCategory, PortfolioCategory, QuestionType
from schemas.feedback_v2 import RouterAnalysisTurn
from schemas.question import CSAnswerAnalysis, PortfolioAnswerAnalysis


class _MockLLM:
    def __init__(self, result):
        self._result = result

    async def generate_structured(self, **kwargs):
        return self._result


@pytest.mark.asyncio
async def test_practice_answer_analyzer_returns_cs_router_analysis(monkeypatch):
    state = create_initial_state(
        user_id=1,
        question_id=10,
        interview_history=[
            SimpleNamespace(
                question="프로세스와 스레드의 차이는 무엇인가요?",
                question_id=10,
                category=CSCategory.OS,
                answer_text="프로세스는 자원을 따로 가지고 스레드는 공유합니다.",
                turn_type="new_topic",
                turn_order=0,
                topic_id=1,
            )
        ],
        interview_type="PRACTICE_INTERVIEW",
        question_type=QuestionType.CS,
        category=CSCategory.OS,
        keywords=["프로세스", "스레드"],
    )
    result_model = CSAnswerAnalysis(
        correctness="핵심 차이는 맞게 설명했습니다.",
        has_error=False,
        completeness="메모리 구조 설명은 일부 생략됐습니다.",
        has_missing_concepts=True,
        depth="원리 설명은 부족합니다.",
        is_superficial=True,
        is_well_structured=True,
    )
    monkeypatch.setattr(analyzer, "get_llm_provider", lambda *_args, **_kwargs: _MockLLM(result_model))

    result = await analyzer.practice_answer_analyzer(state)

    assert result["current_step"] == "practice_answer_analyzer"
    assert len(result["router_analyses"]) == 1
    analysis = result["router_analyses"][0]
    assert isinstance(analysis, RouterAnalysisTurn)
    assert analysis.has_error is False
    assert analysis.has_missing_concepts is True
    assert analysis.is_superficial is True
    assert analysis.correctness_detail == "핵심 차이는 맞게 설명했습니다."


@pytest.mark.asyncio
async def test_practice_answer_analyzer_returns_portfolio_router_analysis(monkeypatch):
    state = create_initial_state(
        user_id=1,
        question_id=20,
        interview_history=[
            SimpleNamespace(
                question="Redis 캐시 전략을 왜 선택했나요?",
                question_id=20,
                category=PortfolioCategory.PORTFOLIO,
                answer_text="응답 속도를 줄이기 위해 Redis를 썼습니다.",
                turn_type="new_topic",
                turn_order=0,
                topic_id=3,
            )
        ],
        interview_type="PRACTICE_INTERVIEW",
        question_type=QuestionType.PORTFOLIO,
        category=PortfolioCategory.PORTFOLIO,
        keywords=None,
    )
    result_model = PortfolioAnswerAnalysis(
        completeness="핵심 의도는 답했지만 구체성이 부족합니다.",
        has_evidence=False,
        has_tradeoff=False,
        has_problem_solving=False,
        is_well_structured=True,
    )
    monkeypatch.setattr(analyzer, "get_llm_provider", lambda *_args, **_kwargs: _MockLLM(result_model))

    result = await analyzer.practice_answer_analyzer(state)

    analysis = result["router_analyses"][0]
    assert analysis.topic_id == 3
    assert analysis.has_evidence is False
    assert analysis.has_tradeoff is False
    assert analysis.has_problem_solving is False
    assert analysis.completeness_detail == "핵심 의도는 답했지만 구체성이 부족합니다."
