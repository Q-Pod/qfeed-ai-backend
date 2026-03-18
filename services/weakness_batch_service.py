from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from core.logging import get_logger
from core.mongodb import get_mongo_client
from repositories.interview_turn_analysis_repo import InterviewTurnAnalysisRepository
from repositories.user_weakness_profile_repo import UserWeaknessProfileRepository
from pymongo.asynchronous.client_session import AsyncClientSession
from schemas.feedback import InterviewType, QuestionType
from schemas.user_weakness_profiles import (
    CSCategoryWeakness,
    CSSubcategoryWeakness,
    CSWeaknessDimensions,
    CSWeaknessProfile,
    PortfolioAspectWeakness,
    PortfolioTechAspectWeakness,
    PortfolioTechWeakness,
    PortfolioWeaknessDimensions,
    PortfolioWeaknessProfile,
    UserWeaknessProfilesDocument,
    WeaknessDimensionScore,
)

logger = get_logger(__name__)


class WeaknessBatchService:
    """interview_turn_analyses를 사용자 약점 프로파일로 증분 반영"""

    def __init__(
        self,
        turn_repo: InterviewTurnAnalysisRepository | None = None,
        profile_repo: UserWeaknessProfileRepository | None = None,
        *,
        use_transactions: bool = True,
    ):
        self._turn_repo = turn_repo or InterviewTurnAnalysisRepository()
        self._profile_repo = profile_repo or UserWeaknessProfileRepository()
        self._use_transactions = use_transactions

    async def run_once(self, *, batch_size: int = 500) -> dict[str, int]:
        """미처리 턴 분석을 한 번 배치 반영"""
        turns = await self._turn_repo.list_unprocessed_turns(limit=batch_size)
        if not turns:
            logger.info("weakness batch no-op | no unprocessed turns")
            return {
                "fetched": 0,
                "processed": 0,
                "skipped": 0,
                "users_updated": 0,
            }

        grouped_turns: dict[int, list[dict]] = defaultdict(list)
        for turn in turns:
            grouped_turns[turn["user_id"]].append(turn)

        processed = 0
        skipped = 0
        users_updated = 0

        for user_id, user_turns in grouped_turns.items():
            tx_result = await self._run_user_batch(
                user_id=user_id,
                user_turns=user_turns,
            )
            processed += tx_result["processed"]
            skipped += tx_result["skipped"]
            users_updated += tx_result["users_updated"]

        logger.info(
            "weakness batch completed | fetched=%s | processed=%s | skipped=%s | users_updated=%s",
            len(turns),
            processed,
            skipped,
            users_updated,
        )
        return {
            "fetched": len(turns),
            "processed": processed,
            "skipped": skipped,
            "users_updated": users_updated,
        }

    async def _load_profile(
        self,
        *,
        user_id: int,
        session: AsyncClientSession | None = None,
    ) -> UserWeaknessProfilesDocument:
        raw = await self._profile_repo.get_profile(
            user_id=user_id,
            session=session,
        )
        if raw is None:
            return UserWeaknessProfilesDocument(user_id=user_id)
        return UserWeaknessProfilesDocument.model_validate(raw)

    async def _run_user_batch(
        self,
        *,
        user_id: int,
        user_turns: list[dict],
    ) -> dict[str, int]:
        if not self._use_transactions:
            return await self._process_user_turns(
                user_id=user_id,
                user_turns=user_turns,
                session=None,
            )

        client = get_mongo_client()
        async with client.start_session() as session:
            return await session.with_transaction(
                lambda s: self._process_user_turns(
                    user_id=user_id,
                    user_turns=user_turns,
                    session=s,
                )
            )

    async def _process_user_turns(
        self,
        *,
        user_id: int,
        user_turns: list[dict],
        session: AsyncClientSession | None,
    ) -> dict[str, int]:
        profile = await self._load_profile(user_id=user_id, session=session)

        processed = 0
        skipped = 0
        for turn in user_turns:
            if self._apply_turn(profile, turn):
                processed += 1
            else:
                skipped += 1

        if user_turns:
            await self._profile_repo.upsert_profile(
                user_id=user_id,
                profile_data=profile.model_dump(),
                session=session,
            )

            for turn in user_turns:
                await self._turn_repo.mark_turn_processed(
                    session_id=turn["session_id"],
                    turn_order=turn["turn_order"],
                    session=session,
                )

        return {
            "processed": processed,
            "skipped": skipped,
            "users_updated": 1 if user_turns else 0,
        }

    def _apply_turn(
        self,
        profile: UserWeaknessProfilesDocument,
        turn: dict[str, Any],
    ) -> bool:
        analysis = turn.get("analysis")
        if not analysis:
            return False

        question_type = turn.get("question_type")
        if question_type == QuestionType.CS.value or question_type == QuestionType.CS:
            bucket = self._get_cs_bucket(
                profile=profile,
                interview_type=turn.get("interview_type"),
            )
            self._apply_cs_turn(bucket, turn)
            return True

        if (
            question_type == QuestionType.PORTFOLIO.value
            or question_type == QuestionType.PORTFOLIO
        ):
            if profile.real_portfolio_personalized is None:
                profile.real_portfolio_personalized = PortfolioWeaknessProfile()
            self._apply_portfolio_turn(
                profile.real_portfolio_personalized,
                turn,
            )
            return True

        return False

    def _get_cs_bucket(
        self,
        *,
        profile: UserWeaknessProfilesDocument,
        interview_type: str | InterviewType | None,
    ) -> CSWeaknessProfile:
        is_practice = (
            interview_type == InterviewType.PRACTICE_INTERVIEW
            or interview_type == InterviewType.PRACTICE_INTERVIEW.value
        )

        if is_practice:
            if profile.practice_cs is None:
                profile.practice_cs = CSWeaknessProfile()
            return profile.practice_cs

        if profile.real_cs is None:
            profile.real_cs = CSWeaknessProfile()
        return profile.real_cs

    def _apply_cs_turn(self, profile: CSWeaknessProfile, turn: dict[str, Any]) -> None:
        analysis = turn["analysis"]
        follow_up = turn.get("follow_up") or {}
        scores = {
            "correctness": 1.0 if analysis.get("has_error") else 0.0,
            "completeness": 1.0 if analysis.get("has_missing_concepts") else 0.0,
            "reasoning": 1.0 if follow_up.get("direction") == "reasoning" else 0.0,
            "depth": 1.0 if analysis.get("is_superficial") else 0.0,
            "delivery": 0.0 if analysis.get("is_well_structured") else 1.0,
        }

        category = turn.get("question_category")
        if not category:
            return

        category_bucket = self._get_or_create_cs_category(profile, category)
        self._update_attempt_metadata(category_bucket, turn)
        self._update_dimensions(category_bucket.dimensions, scores, turn)

        subcategory = turn.get("question_subcategory")
        if not subcategory:
            return

        subcategory_bucket = self._get_or_create_cs_subcategory(
            category_bucket,
            subcategory,
        )
        self._update_attempt_metadata(subcategory_bucket, turn)
        self._update_dimensions(subcategory_bucket.dimensions, scores, turn)

    def _apply_portfolio_turn(
        self,
        profile: PortfolioWeaknessProfile,
        turn: dict[str, Any],
    ) -> None:
        analysis = turn["analysis"]
        scores = {
            "evidence": 0.0 if analysis.get("has_evidence") else 1.0,
            "tradeoff": 0.0 if analysis.get("has_tradeoff") else 1.0,
            "problem_solving": 0.0 if analysis.get("has_problem_solving") else 1.0,
            "depth": (
                0.0
                if analysis.get("has_evidence") and analysis.get("has_problem_solving")
                else 1.0
            ),
            "delivery": 0.0 if analysis.get("is_well_structured") else 1.0,
        }

        pair_dicts = self._normalize_pairs(turn.get("tech_aspect_pairs", []))
        tech_tags = self._extract_unique_pair_values(
            pair_dicts,
            key="tech_tag",
        ) or self._normalize_str_list(turn.get("tech_tags", []))
        aspect_tags = self._extract_unique_pair_values(
            pair_dicts,
            key="aspect_tag",
        ) or self._normalize_str_list(turn.get("aspect_tags", []))

        for pair in pair_dicts:
            pair_bucket = self._get_or_create_pair(
                profile,
                tech_tag=pair["tech_tag"],
                aspect_tag=pair["aspect_tag"],
            )
            self._update_attempt_metadata(pair_bucket, turn)
            self._update_dimensions(pair_bucket.dimensions, scores, turn)

        for tech_tag in tech_tags:
            tech_bucket = self._get_or_create_tech(profile, tech_tag)
            self._update_attempt_metadata(tech_bucket, turn)
            self._update_dimensions(tech_bucket.dimensions, scores, turn)

        for aspect_tag in aspect_tags:
            aspect_bucket = self._get_or_create_aspect(profile, aspect_tag)
            self._update_attempt_metadata(aspect_bucket, turn)
            self._update_dimensions(aspect_bucket.dimensions, scores, turn)

    @staticmethod
    def _get_or_create_cs_category(
        profile: CSWeaknessProfile,
        category: str,
    ) -> CSCategoryWeakness:
        for item in profile.categories:
            if item.category == category:
                return item

        created = CSCategoryWeakness(category=category)
        profile.categories.append(created)
        return created

    @staticmethod
    def _get_or_create_cs_subcategory(
        category_bucket: CSCategoryWeakness,
        subcategory: str,
    ) -> CSSubcategoryWeakness:
        for item in category_bucket.subcategories:
            if item.subcategory == subcategory:
                return item

        created = CSSubcategoryWeakness(subcategory=subcategory)
        category_bucket.subcategories.append(created)
        return created

    @staticmethod
    def _get_or_create_tech(
        profile: PortfolioWeaknessProfile,
        tech_tag: str,
    ) -> PortfolioTechWeakness:
        for item in profile.tech_tags:
            if item.tech_tag == tech_tag:
                return item

        created = PortfolioTechWeakness(tech_tag=tech_tag)
        profile.tech_tags.append(created)
        return created

    @staticmethod
    def _get_or_create_aspect(
        profile: PortfolioWeaknessProfile,
        aspect_tag: str,
    ) -> PortfolioAspectWeakness:
        for item in profile.aspect_tags:
            if item.aspect_tag == aspect_tag:
                return item

        created = PortfolioAspectWeakness(aspect_tag=aspect_tag)
        profile.aspect_tags.append(created)
        return created

    @staticmethod
    def _get_or_create_pair(
        profile: PortfolioWeaknessProfile,
        *,
        tech_tag: str,
        aspect_tag: str,
    ) -> PortfolioTechAspectWeakness:
        for item in profile.tech_aspect_pairs:
            if item.tech_tag == tech_tag and item.aspect_tag == aspect_tag:
                return item

        created = PortfolioTechAspectWeakness(
            tech_tag=tech_tag,
            aspect_tag=aspect_tag,
        )
        profile.tech_aspect_pairs.append(created)
        return created

    @staticmethod
    def _update_attempt_metadata(entity: Any, turn: dict[str, Any]) -> None:
        entity.attempt_count += 1
        entity.last_session_id = turn.get("session_id")
        entity.last_question_id = WeaknessBatchService._stringify_question_id(
            turn.get("question_id")
        )
        entity.last_observed_at = WeaknessBatchService._extract_turn_timestamp(turn)

    @staticmethod
    def _update_dimensions(
        dimensions: CSWeaknessDimensions | PortfolioWeaknessDimensions,
        scores: dict[str, float],
        turn: dict[str, Any],
    ) -> None:
        for dimension_name, turn_score in scores.items():
            dimension = getattr(dimensions, dimension_name)
            WeaknessBatchService._apply_dimension_score(
                dimension=dimension,
                turn_score=turn_score,
                turn=turn,
            )

    @staticmethod
    def _apply_dimension_score(
        *,
        dimension: WeaknessDimensionScore,
        turn_score: float,
        turn: dict[str, Any],
    ) -> None:
        dimension.total_score_sum += turn_score
        dimension.attempt_count += 1
        dimension.score = (
            dimension.total_score_sum / dimension.attempt_count
            if dimension.attempt_count
            else 0.0
        )
        dimension.last_score = turn_score
        dimension.last_observed_at = WeaknessBatchService._extract_turn_timestamp(
            turn
        )
        dimension.last_session_id = turn.get("session_id")
        dimension.last_question_id = WeaknessBatchService._stringify_question_id(
            turn.get("question_id")
        )

    @staticmethod
    def _extract_turn_timestamp(turn: dict[str, Any]) -> datetime:
        return (
            turn.get("created_at")
            or turn.get("updated_at")
            or datetime.now(timezone.utc)
        )

    @staticmethod
    def _stringify_question_id(question_id: Any) -> str | None:
        return str(question_id) if question_id is not None else None

    @staticmethod
    def _normalize_pairs(raw_pairs: list[Any]) -> list[dict[str, str]]:
        seen: set[tuple[str, str]] = set()
        result: list[dict[str, str]] = []

        for pair in raw_pairs:
            tech_tag = getattr(pair, "tech_tag", None)
            aspect_tag = getattr(pair, "aspect_tag", None)
            if isinstance(pair, dict):
                tech_tag = pair.get("tech_tag", tech_tag)
                aspect_tag = pair.get("aspect_tag", aspect_tag)

            if not tech_tag or not aspect_tag:
                continue

            pair_key = (str(tech_tag), str(aspect_tag))
            if pair_key in seen:
                continue
            seen.add(pair_key)
            result.append(
                {
                    "tech_tag": str(tech_tag),
                    "aspect_tag": str(aspect_tag),
                }
            )

        return result

    @staticmethod
    def _extract_unique_pair_values(
        pairs: list[dict[str, str]],
        *,
        key: str,
    ) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []

        for pair in pairs:
            value = pair[key]
            if value in seen:
                continue
            seen.add(value)
            result.append(value)

        return result

    @staticmethod
    def _normalize_str_list(values: list[Any]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []

        for value in values:
            if value is None:
                continue
            normalized = str(value)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            result.append(normalized)

        return result
