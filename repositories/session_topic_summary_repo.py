# repositories/session_topic_summary_repo.py

from datetime import datetime, timezone

from pymongo import ASCENDING

from core.logging import get_logger
from core.mongodb import get_collection

logger = get_logger(__name__)


class SessionTopicSummaryRepository:
    COLLECTION_NAME = "session_topic_summaries"

    # async def ensure_indexes(self) -> None:
    #     collection = get_collection(self.COLLECTION_NAME)

    #     await collection.create_index(
    #         [("session_id", ASCENDING), ("topic_id", ASCENDING)],
    #         unique=True,
    #         name="session_topic_unique_idx",
    #     )

    #     await collection.create_index(
    #         [("user_id", ASCENDING), ("session_id", ASCENDING)],
    #         name="user_session_idx",
    #     )

    async def save_topic_summary(self, doc: dict) -> None:
        collection = get_collection(self.COLLECTION_NAME)

        now = datetime.now(timezone.utc)

        payload = dict(doc)
        payload["updated_at"] = now

        filter_query = {
            "session_id": payload["session_id"],
            "topic_id": payload["topic_id"],
        }

        await collection.update_one(
            filter_query,
            {
                "$set": payload,
                "$setOnInsert": {
                    "created_at": now,
                },
            },
            upsert=True,
        )

        logger.info(
            "session topic summary saved | session_id=%s | topic_id=%s",
            payload["session_id"],
            payload["topic_id"],
        )