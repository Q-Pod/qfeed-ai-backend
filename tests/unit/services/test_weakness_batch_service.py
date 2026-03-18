from datetime import datetime, timezone

from services.weakness_batch_service import WeaknessBatchService


class FakeTurnRepo:
    def __init__(self, turns):
        self.turns = turns
        self.marked = []

    async def list_unprocessed_turns(self, *, limit: int = 500):
        return self.turns[:limit]

    async def mark_turn_processed(
        self,
        *,
        session_id: str,
        turn_order: int,
        session=None,
    ):
        self.marked.append((session_id, turn_order))


class FakeProfileRepo:
    def __init__(self, initial_profiles=None):
        self.initial_profiles = initial_profiles or {}
        self.saved = {}

    async def get_profile(self, *, user_id: int, session=None):
        return self.initial_profiles.get(user_id)

    async def upsert_profile(
        self,
        *,
        user_id: int,
        profile_data: dict,
        session=None,
    ):
        self.saved[user_id] = profile_data


async def test_weakness_batch_service_updates_cs_profile_scores():
    turn = {
        "user_id": 1,
        "session_id": "cs-session",
        "turn_order": 3,
        "question_id": 11,
        "interview_type": "REAL_INTERVIEW",
        "question_type": "CS",
        "question_category": "OS",
        "question_subcategory": "process_thread",
        "analysis": {
            "has_error": True,
            "has_missing_concepts": False,
            "is_superficial": True,
            "is_well_structured": False,
        },
        "follow_up": {
            "direction": "reasoning",
        },
        "created_at": datetime(2026, 3, 17, tzinfo=timezone.utc),
    }
    turn_repo = FakeTurnRepo([turn])
    profile_repo = FakeProfileRepo()
    service = WeaknessBatchService(
        turn_repo=turn_repo,
        profile_repo=profile_repo,
        use_transactions=False,
    )

    result = await service.run_once(batch_size=10)

    saved = profile_repo.saved[1]
    category = saved["real_cs"]["categories"][0]
    dimensions = category["dimensions"]

    assert result["processed"] == 1
    assert dimensions["correctness"]["score"] == 1.0
    assert dimensions["completeness"]["score"] == 0.0
    assert dimensions["reasoning"]["score"] == 1.0
    assert dimensions["depth"]["score"] == 1.0
    assert dimensions["delivery"]["score"] == 1.0
    assert turn_repo.marked == [("cs-session", 3)]


async def test_weakness_batch_service_updates_portfolio_pair_first_and_single_fallback():
    turn = {
        "user_id": 7,
        "session_id": "pf-session",
        "turn_order": 5,
        "question_id": 101,
        "interview_type": "REAL_INTERVIEW",
        "question_type": "PORTFOLIO",
        "analysis": {
            "has_evidence": False,
            "has_tradeoff": True,
            "has_problem_solving": False,
            "is_well_structured": True,
        },
        "tech_aspect_pairs": [
            {"tech_tag": "redis", "aspect_tag": "optimization"},
            {"tech_tag": "kafka", "aspect_tag": "tradeoff"},
        ],
        "tech_tags": ["should_not_be_used"],
        "aspect_tags": ["should_not_be_used"],
        "created_at": datetime(2026, 3, 17, tzinfo=timezone.utc),
    }
    turn_repo = FakeTurnRepo([turn])
    profile_repo = FakeProfileRepo()
    service = WeaknessBatchService(
        turn_repo=turn_repo,
        profile_repo=profile_repo,
        use_transactions=False,
    )

    result = await service.run_once(batch_size=10)

    saved = profile_repo.saved[7]
    profile = saved["real_portfolio_personalized"]
    pair_items = profile["tech_aspect_pairs"]
    tech_items = profile["tech_tags"]
    aspect_items = profile["aspect_tags"]

    assert result["processed"] == 1
    assert len(pair_items) == 2
    assert [item["tech_tag"] for item in tech_items] == ["redis", "kafka"]
    assert [item["aspect_tag"] for item in aspect_items] == [
        "optimization",
        "tradeoff",
    ]
    assert pair_items[0]["dimensions"]["evidence"]["score"] == 1.0
    assert pair_items[0]["dimensions"]["tradeoff"]["score"] == 0.0
    assert pair_items[0]["dimensions"]["problem_solving"]["score"] == 1.0
    assert pair_items[0]["dimensions"]["depth"]["score"] == 1.0
    assert pair_items[0]["dimensions"]["delivery"]["score"] == 0.0
