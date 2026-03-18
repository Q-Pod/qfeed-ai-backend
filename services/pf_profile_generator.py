from __future__ import annotations

import base64

from google.genai import types
from langfuse import observe

from core.dependencies import get_llm_provider
from core.logging import get_logger
from prompts.pf_analysis import (
    PORTFOLIO_ANALYSIS_SYSTEM_PROMPT,
    build_portfolio_analysis_prompt,
)
from schemas.portfolio import Portfolio, PortfolioAnalysisProfileOutput
from schemas.pf_analysis_profiles import PortfolioAnalysisProfileDocument
from utils.img_loader import download_image

logger = get_logger(__name__)


class PortfolioProfileGenerator:
    """포트폴리오 분석 프로필 생성기"""

    @observe(name="generate_portfolio_analysis_profile")
    async def pf_analyze(
        self,
        *,
        user_id: int,
        portfolio_id: int,
        portfolio: Portfolio,
    ) -> PortfolioAnalysisProfileDocument:
        contents = await self._build_multimodal_contents(portfolio)

        llm_provider = get_llm_provider("gemini")

        output = await llm_provider.generate_multimodal_structured(
            contents=contents,
            response_model=PortfolioAnalysisProfileOutput,
            temperature=0.3,
            max_tokens=7000,
        )

        raw_portfolio_text = self._build_raw_portfolio_text(portfolio)

        profile = PortfolioAnalysisProfileDocument(
            user_id=user_id,
            portfolio_id=portfolio_id,
            raw_portfolio_text=raw_portfolio_text,
            portfolio_summary=output.portfolio_summary,
            overall_tech_tags=output.overall_tech_tags,
            overall_aspect_tags=output.overall_aspect_tags,
            project_summaries=output.project_summaries,
            strong_points=output.strong_points,
            risky_points=output.risky_points,
            recommended_question_focuses=output.recommended_question_focuses,
        )

        return profile
    

    async def _build_multimodal_contents(
        self,
        portfolio: Portfolio,
    ) -> list[types.Part]:
        parts: list[types.Part] = []

        text_prompt = build_portfolio_analysis_prompt(portfolio)
        parts.append(
            types.Part.from_text(
                text=f"{PORTFOLIO_ANALYSIS_SYSTEM_PROMPT}\n\n{text_prompt}"
            )
        )

        for project in portfolio.projects:
            if not project.arch_image_url:
                continue

            image_result = await download_image(project.arch_image_url)
            if image_result is None:
                logger.warning(
                    "Skipping architecture image | project=%s | url=%s",
                    project.project_name,
                    project.arch_image_url,
                )
                continue

            base64_data, mime_type = image_result

            parts.append(
                types.Part.from_text(
                    text=f"\n[{project.project_name}의 아키텍처 다이어그램]"
                )
            )
            parts.append(
                types.Part.from_bytes(
                    data=base64.b64decode(base64_data),
                    mime_type=mime_type,
                )
            )

        return parts

    def _build_raw_portfolio_text(self, portfolio: Portfolio) -> str:
        project_sections: list[str] = []

        for i, project in enumerate(portfolio.projects, 1):
            lines = [f"### 프로젝트 {i}: {project.project_name}"]

            if project.role:
                lines.append(f"- 역할: {project.role}")

            if project.tech_stack:
                lines.append(f"- 기술 스택: {', '.join(project.tech_stack)}")

            if project.content:
                lines.append(f"- 프로젝트 설명: {project.content}")

            project_sections.append("\n".join(lines))

        return "\n\n".join(project_sections)