from __future__ import annotations

from typing import Final

from pymongo import ASCENDING,DESCENDING
from pymongo.asynchronous.mongo_client import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.errors import PyMongoError

from core.config import get_settings
from core.logging import get_logger


logger = get_logger(__name__)


class MongoCollections:
    SESSION_TOPIC_SUMMARIES: Final[str] = "session_topic_summaries"
    PORTFOLIO_ANALYSIS_PROFILES: Final[str] = "portfolio_analysis_profiles"
    PORTFOLIO_QUESTION_POOLS: Final[str] = "portfolio_question_pools"
    INTERVIEW_TURN_ANALYSES: Final[str] = "interview_turn_analyses"
    USER_WEAKNESS_PROFILES: Final[str] = "user_weakness_profiles"


_mongo_client: AsyncMongoClient | None = None


def get_mongo_client() -> AsyncMongoClient:
    global _mongo_client

    if _mongo_client is not None:
        return _mongo_client

    settings = get_settings()

    _mongo_client = AsyncMongoClient(
        settings.MONGODB_URI,
        appname=settings.MONGODB_APP_NAME,
        maxPoolSize=settings.MONGODB_MAX_POOL_SIZE,
        minPoolSize=settings.MONGODB_MIN_POOL_SIZE,
        serverSelectionTimeoutMS=settings.MONGODB_SERVER_SELECTION_TIMEOUT_MS,
        connectTimeoutMS=settings.MONGODB_CONNECT_TIMEOUT_MS,
        socketTimeoutMS=settings.MONGODB_SOCKET_TIMEOUT_MS,
        retryWrites=True,
    )

    logger.info(
        "MongoDB client initialized | db=%s | uri=%s",
        settings.MONGODB_DB_NAME,
        _mask_mongo_uri(settings.MONGODB_URI),
    )
    return _mongo_client


def get_database() -> AsyncDatabase:
    settings = get_settings()
    client = get_mongo_client()
    return client[settings.MONGODB_DB_NAME]


def get_collection(name: str) -> AsyncCollection:
    return get_database()[name]


async def ping_mongo() -> bool:
    try:
        await get_mongo_client().admin.command("ping")
        logger.info("MongoDB ping success")
        return True
    except PyMongoError as e:
        logger.error("MongoDB ping failed | %s: %s", type(e).__name__, e)
        return False


async def close_mongo_client() -> None:
    global _mongo_client

    if _mongo_client is None:
        return

    await _mongo_client.close()
    _mongo_client = None
    logger.info("MongoDB client closed")

async def ensure_mongo_indexes() -> None:
    db = get_database()

    qpool = db[MongoCollections.PORTFOLIO_QUESTION_POOLS]
    turn_analyze = db[MongoCollections.INTERVIEW_TURN_ANALYSES]


    # 1) 질문 조회용 인덱스
    await qpool.create_index(
        [
            ("user_id", ASCENDING),
            ("portfolio_id", ASCENDING),
            ("active", ASCENDING),
            ("priority", DESCENDING),
            ("used_count", ASCENDING),
            ("last_used_at", ASCENDING),
        ],
        name="idx_qpool_select",
    )

    # 2) 질문 상태 업데이트용 인덱스
    await qpool.create_index(
        [
            ("user_id", ASCENDING),
            ("portfolio_id", ASCENDING),
            ("question_pool_id", ASCENDING),
        ],
        name="uq_qpool_owner_poolid",
        unique=True,
    )

    await turn_analyze.creat_index(
        [
            ("session_id", ASCENDING), 
            ("turn_order", ASCENDING),
        ],
        name="uniq_session_turn_order",
        unique=True,
    )

    logger.info("MongoDB portfolio question pool indexes ensured")

# def ensure_mongo_indexes() -> None:
#     db = get_database()

#     db[MongoCollections.SESSION_TOPIC_SUMMARIES].create_index(
#         [
#             ("user_id", ASCENDING),
#             ("session_id", ASCENDING),
#             ("topic_id", ASCENDING),
#         ],
#         name="uq_user_session_topic",
#         unique=True,
#     )
#     db[MongoCollections.SESSION_TOPIC_SUMMARIES].create_index(
#         [("user_id", ASCENDING), ("created_at", ASCENDING)],
#         name="idx_session_topic_user_created_at",
#     )

#     db[MongoCollections.PORTFOLIO_ANALYSIS_PROFILES].create_index(
#         [("user_id", ASCENDING), ("portfolio_id", ASCENDING)],
#         name="uq_user_portfolio_analysis_profile",
#         unique=True,
#     )

#     db[MongoCollections.PORTFOLIO_QUESTION_POOLS].create_index(
#         [
#             ("user_id", ASCENDING),
#             ("portfolio_id", ASCENDING),
#             ("question_pool_id", ASCENDING),
#         ],
#         name="uq_user_portfolio_question_pool",
#         unique=True,
#     )
#     db[MongoCollections.PORTFOLIO_QUESTION_POOLS].create_index(
#         [
#             ("user_id", ASCENDING),
#             ("portfolio_id", ASCENDING),
#             ("active", ASCENDING),
#             ("priority", ASCENDING),
#         ],
#         name="idx_question_pool_active_priority",
#     )

#     db[MongoCollections.INTERVIEW_TURN_ANALYSES].create_index(
#         [
#             ("user_id", ASCENDING),
#             ("session_id", ASCENDING),
#             ("turn_order", ASCENDING),
#         ],
#         name="uq_user_session_turn_order",
#         unique=True,
#     )
#     db[MongoCollections.INTERVIEW_TURN_ANALYSES].create_index(
#         [
#             ("user_id", ASCENDING),
#             ("question_type", ASCENDING),
#             ("question_category", ASCENDING),
#             ("question_subcategory", ASCENDING),
#         ],
#         name="idx_turn_analysis_question_lookup",
#     )

#     db[MongoCollections.USER_WEAKNESS_PROFILES].create_index(
#         [("user_id", ASCENDING)],
#         name="uq_user_weakness_profile",
#         unique=True,
#     )

#     logger.info("MongoDB indexes ensured")


def _mask_mongo_uri(uri: str) -> str:
    """
    로그에 비밀번호가 그대로 남지 않도록 최소한 마스킹.
    mongodb://user:password@host:27017 형태 대응.
    """
    if "@" not in uri or "://" not in uri:
        return uri

    scheme, rest = uri.split("://", 1)
    if "@" not in rest:
        return uri

    auth_part, host_part = rest.split("@", 1)
    if ":" not in auth_part:
        return f"{scheme}://***@{host_part}"

    username, _ = auth_part.split(":", 1)
    return f"{scheme}://{username}:***@{host_part}"