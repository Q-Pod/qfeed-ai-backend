from prompts.CS.new_topic import build_cs_new_topic_prompt
from schemas.feedback import CSCategory


def test_cs_new_topic_prompt_includes_taxonomy_for_free_selection():
    prompt = build_cs_new_topic_prompt(
        interview_history=[],
        available_categories=["OS", "NETWORK"],
    )

    assert "category는 반드시 다음 ID 중 하나를 선택하세요: OS, NETWORK" in prompt
    assert "subcategory는 선택한 category 하위의 소분류 ID 중 하나여야 합니다." in prompt
    assert "[OS:" in prompt
    assert "[NETWORK:" in prompt


def test_cs_new_topic_prompt_includes_subcategories_for_forced_category():
    prompt = build_cs_new_topic_prompt(
        interview_history=[],
        forced_category=CSCategory.OS,
    )

    assert "category는 반드시 `OS`를 선택하세요." in prompt
    assert "subcategory는 `OS` 하위 소분류 ID 중 하나여야 합니다." in prompt
    assert "현재 카테고리: OS" in prompt
