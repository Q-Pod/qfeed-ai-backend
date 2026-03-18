import pytest

from graphs.nodes.PF import followup_generator as pf_followup_generator
from schemas.feedback import PortfolioCategory, QATurn
from prompts.PF.follow_up import build_pf_follow_up_user_prompt


def test_normalize_pf_follow_up_pairs_normalizes_and_filters_invalid_values():
    tech_aspect_pairs, tech_tags, aspect_tags = (
        pf_followup_generator._normalize_pf_follow_up_pairs(
            raw_pairs=[
                {"tech_tag": "Redis", "aspect_tag": "optimization"},
                {"tech_tag": "spring boot", "aspect_tag": "tradeoff"},
                {"tech_tag": "Redis", "aspect_tag": "optimization"},
                {"tech_tag": "Kafka", "aspect_tag": "invalid_tag"},
            ],
        )
    )

    assert tech_aspect_pairs == [
        {"tech_tag": "redis", "aspect_tag": "optimization"},
        {"tech_tag": "spring_boot", "aspect_tag": "tradeoff"},
    ]
    assert tech_tags == ["redis", "spring_boot"]
    assert aspect_tags == ["optimization", "tradeoff"]


def test_build_pf_follow_up_user_prompt_includes_taxonomy_lists_and_existing_tags():
    prompt = build_pf_follow_up_user_prompt(
        portfolio_summary="Redis 캐시와 Kafka 이벤트 무효화를 운영했습니다.",
        current_topic_turns=[
            QATurn(
                question="Redis 캐시 무효화를 어떻게 설계했나요?",
                category=PortfolioCategory.PORTFOLIO,
                answer_text="Kafka 이벤트로 무효화했습니다.",
                tech_tags=["redis", "kafka"],
                aspect_tags=["optimization"],
                turn_type="new_topic",
                turn_order=0,
                topic_id=1,
            )
        ],
        follow_up_direction="tradeoff_probe",
        direction_detail="이벤트 기반 무효화의 운영 복잡도와 대안을 확인",
        last_question="Redis 캐시 무효화를 어떻게 설계했나요?",
        last_answer="Kafka 이벤트로 무효화했습니다.",
    )

    assert "<tech_tags_list>" in prompt
    assert "<aspect_tags_list>" in prompt
    assert "tech_aspect_pairs" in prompt
    assert "redis, kafka" in prompt
    assert "optimization" in prompt
