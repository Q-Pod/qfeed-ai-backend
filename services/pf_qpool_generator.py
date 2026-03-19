from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from langfuse import observe

from core.dependencies import get_llm_provider
from core.logging import get_logger
from prompts.pf_question_pool import (
    QUESTION_POOL_SYSTEM_PROMPT,
    build_question_pool_prompt,
)
from schemas.pf_analysis_profiles import PortfolioAnalysisProfileDocument
from schemas.pf_question_pools import (
    TechAspectPair,
    PortfolioQuestionPoolDocument,
    PortfolioQuestionPoolItemOutput,
    PortfolioQuestionPoolLLMResponse,
)
from taxonomy.loader import normalize_tech_tag, validate_aspect_tag

logger = get_logger(__name__)


class PortfolioQuestionPoolGenerator:
    """포트폴리오 질문 풀 생성기"""

    @observe(name="generate_portfolio_question_pool")
    async def generate(
        self,
        *,
        user_id: int,
        portfolio_id: int,
        analysis_profile: PortfolioAnalysisProfileDocument,
    ) -> list[PortfolioQuestionPoolDocument]:
        llm_provider = get_llm_provider("gemini")

        prompt = build_question_pool_prompt(analysis_profile)

        llm_response = await llm_provider.generate_structured(
            prompt=prompt,
            system_prompt=QUESTION_POOL_SYSTEM_PROMPT,
            response_model=PortfolioQuestionPoolLLMResponse,
            temperature=0.4,
            max_tokens=8000,
        )

        question_pool = self._convert_to_documents(
            raw_items=llm_response.questions,
            user_id=user_id,
            portfolio_id=portfolio_id,
        )

        logger.info(
            "Portfolio question pool generated | user_id=%s | portfolio_id=%s | count=%s",
            user_id,
            portfolio_id,
            len(question_pool),
        )

        return question_pool

    def _convert_to_documents(
        self,
        *,
        raw_items: list[PortfolioQuestionPoolItemOutput],
        user_id: int,
        portfolio_id: int,
    ) -> list[PortfolioQuestionPoolDocument]:
        """LLM 출력을 MongoDB Document로 변환 + 태그 정규화"""

        documents: list[PortfolioQuestionPoolDocument] = []
        now = datetime.now(timezone.utc)

        for idx, item in enumerate(raw_items, start=5000):
            normalized_pairs, normalized_tech_tags, validated_aspect_tags = (
                self._normalize_pairs(item.tech_aspect_pairs)
            )

            if len(normalized_pairs) != len(item.tech_aspect_pairs):
                logger.warning(
                    "Invalid tech_aspect_pairs filtered | question=%s",
                    item.question_text[:50],
                )

            doc = PortfolioQuestionPoolDocument(
                user_id=user_id,
                portfolio_id=portfolio_id,
                question_id=idx,
                project_name=item.project_name,
                question_text=item.question_text,
                tech_tags=normalized_tech_tags,
                aspect_tags=validated_aspect_tags,
                tech_aspect_pairs=normalized_pairs,
                intent=item.intent,
                priority=item.priority,
                difficulty=item.difficulty,
                follow_up_hints=item.follow_up_hints,
                source_summary_snippets=item.source_summary_snippets,
                active=True,
                used_count=0,
                last_used_at=None,
                created_at=now,
                updated_at=now,
            )
            documents.append(doc)

        return documents

    @staticmethod
    def _normalize_pairs(
        raw_pairs: list[TechAspectPair],
    ) -> tuple[list[TechAspectPair], list[str], list[str]]:
        normalized_pairs: list[TechAspectPair] = []
        seen_pairs: set[tuple[str, str]] = set()

        for pair in raw_pairs:
            tech_tag = normalize_tech_tag(pair.tech_tag)
            aspect_tag = pair.aspect_tag

            if not aspect_tag or not validate_aspect_tag(aspect_tag):
                continue

            pair_key = (tech_tag, aspect_tag)
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)
            normalized_pairs.append(
                TechAspectPair(
                    tech_tag=tech_tag,
                    aspect_tag=aspect_tag,
                )
            )

        tech_tags = _dedupe([pair.tech_tag for pair in normalized_pairs])
        aspect_tags = _dedupe([pair.aspect_tag for pair in normalized_pairs])
        return normalized_pairs, tech_tags, aspect_tags


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []

    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)

    return result
