# repositories/session_topic_summary_repo.py

from datetime import datetime, timezone

from pymongo import ASCENDING

from core.logging import get_logger
from core.mongodb import get_collection
from schemas.feedback_v2 import InterviewType, QuestionType

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

    async def list_session_topic_summaries(
        self,
        *,
        user_id: int,
        session_id: str,
        question_type: QuestionType,
        interview_type: InterviewType = InterviewType.REAL_INTERVIEW,
    ) -> list[dict]:
        """세션 단위 토픽 요약 조회"""
        collection = get_collection(self.COLLECTION_NAME)

        cursor = collection.find(
            {
                "user_id": user_id,
                "session_id": session_id,
                "question_type": question_type,
                "interview_type": interview_type,
            }
        ).sort([("topic_id", 1)])

        docs = await cursor.to_list(length=None)
        for doc in docs:
            doc.pop("_id", None)
        return docs
