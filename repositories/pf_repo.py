# repositories/portfolio_repo.py
"""포트폴리오 분석 프로필 및 질문 풀 MongoDB Repository"""

from __future__ import annotations

from datetime import datetime, timezone

from core.mongodb import get_database
from core.logging import get_logger

logger = get_logger(__name__)

COLLECTION_ANALYSIS_PROFILES = "portfolio_analysis_profiles"
COLLECTION_QUESTION_POOLS = "portfolio_question_pools"


class PortfolioRepository:
    """포트폴리오 분석 결과 및 질문 풀 저장소"""

    def __init__(self):
        self._db = get_database()

    # ══════════════════════════════════════
    # 분석 프로필
    # ══════════════════════════════════════

    async def save_analysis_profile(self, profile_data: dict) -> str:
        """분석 프로필 저장 (upsert — 같은 user_id + portfolio_id면 덮어쓰기)"""
        collection = self._db[COLLECTION_ANALYSIS_PROFILES]

        profile_data["updated_at"] = datetime.now(timezone.utc)

        result = await collection.update_one(
            {
                "user_id": profile_data["user_id"],
                "portfolio_id": profile_data["portfolio_id"],
            },
            {"$set": profile_data},
            upsert=True,
        )

        logger.info(
            "분석 프로필 저장 완료 | user_id=%s | portfolio_id=%s",
            profile_data.get("user_id"),
            profile_data.get("portfolio_id"),
        )
        return str(result.upserted_id or "updated")

    async def get_analysis_profile(
        self, user_id: int, portfolio_id: int
    ) -> dict | None:
        """분석 프로필 조회"""
        collection = self._db[COLLECTION_ANALYSIS_PROFILES]

        profile = await collection.find_one(
            {"user_id": user_id, "portfolio_id": portfolio_id}
        )

        if profile:
            profile.pop("_id", None)

        return profile

    # ══════════════════════════════════════
    # 질문 풀
    # ══════════════════════════════════════

    async def save_question_pool(
        self, questions: list[dict]
    ) -> int:
        """질문 풀 저장 (기존 질문 풀 교체 — 같은 user_id + portfolio_id)

        Returns:
            저장된 질문 수
        """
        if not questions:
            return 0

        collection = self._db[COLLECTION_QUESTION_POOLS]

        user_id = questions[0].get("user_id")
        portfolio_id = questions[0].get("portfolio_id")

        # 기존 질문 풀 삭제 후 새로 삽입
        await collection.delete_many(
            {"user_id": user_id, "portfolio_id": portfolio_id}
        )

        now = datetime.now(timezone.utc)
        for q in questions:
            q.setdefault("created_at", now)
            q.setdefault("updated_at", now)

        result = await collection.insert_many(questions)

        logger.info(
            "질문 풀 저장 완료 | user_id=%s | portfolio_id=%s | count=%s",
            user_id,
            portfolio_id,
            len(result.inserted_ids),
        )
        return len(result.inserted_ids)

    async def get_question_pool(
        self,
        user_id: int,
        portfolio_id: int,
        *,
        active_only: bool = True,
    ) -> list[dict]:
        """질문 풀 조회"""
        collection = self._db[COLLECTION_QUESTION_POOLS]

        query = {
            "user_id": user_id,
            "portfolio_id": portfolio_id,
        }
        if active_only:
            query["active"] = True

        cursor = collection.find(query).sort([
            ("priority", -1),
            ("used_count", 1),
            ("last_used_at", 1),
        ])
        questions = await cursor.to_list(length=200)

        for q in questions:
            q.pop("_id", None)

        return questions

    async def get_question_by_id(
        self,
        *,
        user_id: int,
        portfolio_id: int,
        question_id: int,
    ) -> dict | None:
        """질문 풀에서 단일 질문 조회"""
        collection = self._db[COLLECTION_QUESTION_POOLS]

        question = await collection.find_one(
            {
                "user_id": user_id,
                "portfolio_id": portfolio_id,
                "question_id": question_id,
            }
        )

        if question:
            question.pop("_id", None)

        return question

    async def increment_question_used(
        self,
        *,
        user_id: int,
        portfolio_id: int,
        question_id: int,
    ) -> None:
        """질문 사용 횟수 증가 + 마지막 사용 시점 갱신"""
        collection = self._db[COLLECTION_QUESTION_POOLS]

        now = datetime.now(timezone.utc)

        await collection.update_one(
            {
                "user_id": user_id,
                "portfolio_id": portfolio_id,
                "question_id": question_id,
            },
            {
                "$inc": {"used_count": 1},
                "$set": {
                    "last_used_at": now,
                    "updated_at": now,
                },
            },
        )

    async def deactivate_question(
        self,
        *,
        user_id: int,
        portfolio_id: int,
        question_id: int,
    ) -> None:
        """질문 비활성화"""
        collection = self._db[COLLECTION_QUESTION_POOLS]

        now = datetime.now(timezone.utc)

        await collection.update_one(
            {
                "user_id": user_id,
                "portfolio_id": portfolio_id,
                "question_id": question_id,
            },
            {
                "$set": {
                    "active": False,
                    "updated_at": now,
                },
            },
        )
