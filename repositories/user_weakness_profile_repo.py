from __future__ import annotations

from datetime import datetime, timezone

from core.mongodb import get_database
from core.logging import get_logger
from pymongo.asynchronous.client_session import AsyncClientSession

logger = get_logger(__name__)

COLLECTION_USER_WEAKNESS_PROFILES = "user_weakness_profiles"


class UserWeaknessProfileRepository:
    """사용자별 약점 프로파일 저장소"""

    def __init__(self):
        self._db = get_database()

    async def get_profile(
        self,
        *,
        user_id: int,
        session: AsyncClientSession | None = None,
    ) -> dict | None:
        """user_id 기준 약점 프로파일 조회"""
        collection = self._db[COLLECTION_USER_WEAKNESS_PROFILES]

        profile = await collection.find_one(
            {"user_id": user_id},
            session=session,
        )
        if profile:
            profile.pop("_id", None)
        return profile

    async def upsert_profile(
        self,
        *,
        user_id: int,
        profile_data: dict,
        session: AsyncClientSession | None = None,
    ) -> None:
        """user_id 기준 약점 프로파일 upsert"""
        collection = self._db[COLLECTION_USER_WEAKNESS_PROFILES]
        now = datetime.now(timezone.utc)

        payload = dict(profile_data)
        payload["user_id"] = user_id
        payload["updated_at"] = now

        await collection.update_one(
            {"user_id": user_id},
            {
                "$set": payload,
                "$setOnInsert": {
                    "created_at": now,
                },
            },
            upsert=True,
            session=session,
        )

        logger.info("user weakness profile upserted | user_id=%s", user_id)
