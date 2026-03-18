# services/qpool_selector.py

"""포트폴리오 질문 풀 셀렉터

역할:
  - MongoDB 질문 풀에서 조건에 맞는 질문을 선택
  - 사용 이력, 우선순위, 태그 기반 필터링

사용처:
  - question_generate_service: 포트폴리오 첫 질문 선택
  - new_topic_generator: 토픽 전환 시 다음 질문 선택
  - (향후) weakness_recommender: 취약점 기반 질문 추천
"""

from __future__ import annotations

from repositories.pf_repo import PortfolioRepository
from core.logging import get_logger

logger = get_logger(__name__)


class QuestionPoolSelector:
    """포트폴리오 질문 풀에서 질문을 선택하는 셀렉터"""

    def __init__(self, portfolio_repo: PortfolioRepository | None = None):
        self._repo = portfolio_repo or PortfolioRepository()

    async def select_initial_question(
        self,
        *,
        user_id: int,
        portfolio_id: int,
    ) -> dict | None:
        """첫 질문 선택 — 우선순위 높고 사용 이력 없는 질문

        선택 기준:
            1. active=True
            2. priority 높은 순
            3. used_count 낮은 순
            4. created_at 오름차순
        """
        questions = await self._repo.get_question_pool(
            user_id=user_id,
            portfolio_id=portfolio_id,
            active_only=True,
        )

        if not questions:
            logger.warning(
                "Question pool empty | user_id=%s | portfolio_id=%s",
                user_id,
                portfolio_id,
            )
            return None

        selected = questions[0]

        await self._repo.increment_question_used(
            user_id=user_id,
            portfolio_id=portfolio_id,
            question_id=selected["question_id"],
        )

        logger.info(
            "Initial question selected | "
            "user_id=%s | pool_id=%s | priority=%s | "
            "question=%s",
            user_id,
            selected["question_id"],
            selected.get("priority"),
            selected["question_text"][:60],
        )

        return selected

    async def select_new_topic_question(
        self,
        *,
        user_id: int,
        portfolio_id: int,
        used_question_ids: list[int],
        preferred_aspect_tags: list[str] | None = None,
        preferred_tech_tags: list[str] | None = None,
    ) -> dict | None:
        """새 토픽 질문 선택 — 이미 사용한 질문을 제외하고 선택

        Args:
            user_id: 사용자 ID
            portfolio_id: 포트폴리오 ID
            used_question_ids: 현재 세션에서 이미 사용한 질문 ID 목록
            preferred_aspect_tags: 선호 관점 태그 (취약점 기반 추천 시 활용)
            preferred_tech_tags: 선호 기술 태그 (취약점 기반 추천 시 활용)

        Returns:
            선택된 질문 dict, 없으면 None
        """
        questions = await self._repo.get_question_pool(
            user_id=user_id,
            portfolio_id=portfolio_id,
            active_only=True,
        )

        if not questions:
            logger.warning(
                "Question pool empty for new topic | "
                "user_id=%s | portfolio_id=%s",
                user_id,
                portfolio_id,
            )
            return None

        # 이미 사용한 질문 제외
        used_ids_set = set(used_question_ids)
        candidates = [
            q for q in questions
            if q["question_id"] not in used_ids_set
        ]

        if not candidates:
            logger.info(
                "All questions used in session | "
                "user_id=%s | total=%s | used=%s",
                user_id,
                len(questions),
                len(used_ids_set),
            )
            return None

        # 선호 태그가 있으면 매칭 점수로 재정렬
        if preferred_aspect_tags or preferred_tech_tags:
            candidates = self._rank_by_preference(
                candidates,
                preferred_aspect_tags=preferred_aspect_tags or [],
                preferred_tech_tags=preferred_tech_tags or [],
            )

        selected = candidates[0]

        await self._repo.increment_question_used(
            user_id=user_id,
            portfolio_id=portfolio_id,
            question_id=selected["question_id"],
        )

        logger.info(
            "New topic question selected | "
            "user_id=%s | pool_id=%s | "
            "remaining=%s | question=%s",
            user_id,
            selected["question_id"],
            len(candidates) - 1,
            selected["question_text"][:60],
        )

        return selected

    async def get_remaining_count(
        self,
        *,
        user_id: int,
        portfolio_id: int,
        used_question_ids: list[int],
    ) -> int:
        """사용 가능한 남은 질문 수 반환"""
        questions = await self._repo.get_question_pool(
            user_id=user_id,
            portfolio_id=portfolio_id,
            active_only=True,
        )

        used_ids_set = set(used_question_ids)
        remaining = [
            q for q in questions
            if q["question_id"] not in used_ids_set
        ]

        return len(remaining)

    # ── 내부 유틸리티 ──

    @staticmethod
    def _rank_by_preference(
        candidates: list[dict],
        preferred_aspect_tags: list[str],
        preferred_tech_tags: list[str],
    ) -> list[dict]:
        """선호 태그 매칭 점수로 후보를 재정렬

        매칭 점수가 높을수록 앞에 오고,
        같은 점수면 기존 정렬(priority 높은 순, used_count 낮은 순) 유지.
        """
        preferred_aspects = set(preferred_aspect_tags)
        preferred_techs = set(preferred_tech_tags)

        def match_score(q: dict) -> float:
            q_aspects = set(q.get("aspect_tags", []))
            q_techs = set(q.get("tech_tags", []))

            aspect_matches = len(q_aspects & preferred_aspects)
            tech_matches = len(q_techs & preferred_techs)

            # aspect 매칭에 더 높은 가중치 (관점이 더 중요)
            return aspect_matches * 2.0 + tech_matches * 1.0

        # match_score 내림차순 정렬 (같으면 기존 순서 유지 — stable sort)
        candidates.sort(key=match_score, reverse=True)

        return candidates

    @staticmethod
    def extract_used_ids(interview_history: list) -> list[int]:
        """interview_history에서 사용된 question_id 목록 추출"""
        used_ids = []
        for turn in interview_history:
            question_id = getattr(turn, "question_id", None)
            if question_id is not None:
                used_ids.append(question_id)
        return used_ids