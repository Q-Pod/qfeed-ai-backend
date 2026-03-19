from datetime import datetime, timezone

from core.mongodb import get_database
from core.logging import get_logger
from pymongo.asynchronous.client_session import AsyncClientSession
from schemas.feedback_v2 import InterviewType, QuestionType

logger = get_logger(__name__)

COLLECTION_INTERVIEW_TURN_ANALYSES = "interview_turn_analyses"


class InterviewTurnAnalysisRepository:
    """면접 턴 분석 저장소"""

    def __init__(self):
        self._db = get_database()

    async def save_turn_analysis(
        self,
        doc: dict,
        *,
        session: AsyncClientSession | None = None,
    ) -> None:
        """session_id + turn_order 기준 upsert 저장"""
        collection = self._db[COLLECTION_INTERVIEW_TURN_ANALYSES]

        now = datetime.now(timezone.utc)

        payload = dict(doc)
        payload["updated_at"] = now

        await collection.update_one(
            {
                "session_id": payload["session_id"],
                "turn_order": payload["turn_order"],
            },
            {
                "$set": payload,
                "$setOnInsert": {
                    "created_at": now,
                },
            },
            upsert=True,
            session=session,
        )

        logger.info(
            "interview_turn_analysis saved | session_id=%s | turn_order=%s | route=%s",
            payload["session_id"],
            payload["turn_order"],
            payload.get("route_decision"),
        )

    async def list_unprocessed_turns(
        self,
        *,
        limit: int = 500,
    ) -> list[dict]:
        """약점 프로파일에 아직 반영되지 않은 턴 분석 조회"""
        collection = self._db[COLLECTION_INTERVIEW_TURN_ANALYSES]

        cursor = collection.find(
            {"weakness_processed": {"$ne": True}}
        ).sort(
            [
                ("user_id", 1),
                ("created_at", 1),
                ("turn_order", 1),
            ]
        )

        docs = await cursor.to_list(length=limit)
        for doc in docs:
            doc.pop("_id", None)
        return docs

    async def list_session_turn_analyses(
        self,
        *,
        user_id: int,
        session_id: str,
        question_type: QuestionType,
        interview_type: InterviewType = InterviewType.REAL_INTERVIEW,
    ) -> list[dict]:
        """세션 단위 턴 분석 조회"""
        collection = self._db[COLLECTION_INTERVIEW_TURN_ANALYSES]

        cursor = collection.find(
            {
                "user_id": user_id,
                "session_id": session_id,
                "question_type": question_type,
                "interview_type": interview_type,
            }
        ).sort([("turn_order", 1)])

        docs = await cursor.to_list(length=None)
        for doc in docs:
            doc.pop("_id", None)
        return docs

    async def mark_turn_processed(
        self,
        *,
        session_id: str,
        turn_order: int,
        session: AsyncClientSession | None = None,
    ) -> None:
        """해당 턴 분석이 약점 프로파일에 반영되었음을 표시"""
        collection = self._db[COLLECTION_INTERVIEW_TURN_ANALYSES]
        now = datetime.now(timezone.utc)

        await collection.update_one(
            {
                "session_id": session_id,
                "turn_order": turn_order,
            },
            {
                "$set": {
                    "weakness_processed": True,
                    "weakness_processed_at": now,
                    "updated_at": now,
                }
            },
            session=session,
        )
