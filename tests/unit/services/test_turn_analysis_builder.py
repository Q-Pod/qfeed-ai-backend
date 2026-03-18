from services.turn_analysis_builder import TurnAnalysisBuilder
from schemas.feedback import PortfolioCategory, QATurn, QuestionType
from schemas.question import QuestionGenerateRequest, QuestionGenerateResponse
from schemas.pf_question_pools import TechAspectPair


def test_turn_analysis_builder_copies_portfolio_tags_and_pairs():
    builder = TurnAnalysisBuilder()
    request = QuestionGenerateRequest(
        user_id=1,
        session_id="session-1",
        portfolio_id=10,
        question_type=QuestionType.PORTFOLIO,
        interview_history=[
            QATurn(
                question="Redis 캐시를 왜 도입했나요?",
                question_id=101,
                category=PortfolioCategory.PORTFOLIO,
                answer_text="메뉴 조회 병목을 줄이기 위해 도입했습니다.",
                tech_aspect_pairs=[
                    TechAspectPair(tech_tag="redis", aspect_tag="optimization"),
                    TechAspectPair(tech_tag="spring_boot", aspect_tag="tech_choice"),
                ],
                turn_type="new_topic",
                turn_order=0,
                topic_id=1,
            )
        ],
    )
    result = {
        "route_decision": "follow_up",
        "route_reasoning": "기술 선택 근거를 더 확인할 필요가 있다.",
        "follow_up_direction": "why_probe",
        "direction_detail": "Redis 대신 다른 선택지를 비교했는지 확인",
        "router_analysis": {
            "completeness": "성과는 설명했지만 선택 근거가 부족하다.",
            "has_evidence": True,
            "has_tradeoff": False,
            "has_problem_solving": False,
            "is_well_structured": True,
        },
    }

    doc = builder.build(request, result)

    assert doc.tech_tags == ["redis", "spring_boot"]
    assert doc.aspect_tags == ["optimization", "tech_choice"]
    assert doc.tech_aspect_pairs == [
        {"tech_tag": "redis", "aspect_tag": "optimization"},
        {"tech_tag": "spring_boot", "aspect_tag": "tech_choice"},
    ]


def test_question_response_from_question_pool_copies_tags():
    response = QuestionGenerateResponse.from_question_pool(
        user_id=1,
        session_id="session-1",
        selected_question={
            "question_id": 10,
            "question_text": "Redis 캐시 무효화를 어떻게 설계했나요?",
            "tech_tags": ["redis", "kafka"],
            "aspect_tags": ["optimization", "tradeoff"],
            "tech_aspect_pairs": [
                {"tech_tag": "redis", "aspect_tag": "optimization"},
                {"tech_tag": "kafka", "aspect_tag": "tradeoff"},
            ],
        },
    )

    assert response.data.tech_tags == ["redis", "kafka"]
    assert response.data.aspect_tags == ["optimization", "tradeoff"]
    assert response.data.tech_aspect_pairs == [
        TechAspectPair(tech_tag="redis", aspect_tag="optimization"),
        TechAspectPair(tech_tag="kafka", aspect_tag="tradeoff"),
    ]
