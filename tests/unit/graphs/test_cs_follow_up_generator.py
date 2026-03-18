from graphs.nodes.CS.follow_up_generator import _normalize_follow_up_subcategory
from schemas.feedback import CSCategory


def test_follow_up_subcategory_keeps_valid_generated_value():
    subcategory = _normalize_follow_up_subcategory(
        current_category=CSCategory.OS,
        generated_subcategory="process_thread",
        current_subcategory="synchronization",
    )

    assert subcategory == "process_thread"


def test_follow_up_subcategory_falls_back_to_current_subcategory():
    subcategory = _normalize_follow_up_subcategory(
        current_category=CSCategory.OS,
        generated_subcategory="not_a_real_subcategory",
        current_subcategory="process_thread",
    )

    assert subcategory == "process_thread"
