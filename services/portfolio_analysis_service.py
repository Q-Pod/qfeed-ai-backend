# services/portfolio_analysis_service.py

"""포트폴리오 분석 및 질문 풀 생성 서비스

포트폴리오를 입력받아 면접용 요약과 질문 풀을 생성한다.

흐름:
    1. 포트폴리오 텍스트 정보 구성
    2. 아키텍처 이미지 다운로드 (있는 경우)
    3. Gemini 멀티모달 호출: 텍스트 + 이미지 → 요약 + 질문 풀
    4. question_id 부여 후 응답 반환
"""

import base64

from google.genai import types

from langfuse import observe
from core.logging import get_logger

from services.pf_profile_generator import PortfolioProfileGenerator
from services.pf_qpool_generator import PortfolioQuestionPoolGenerator
from repositories.pf_repo import PortfolioRepository
from schemas.portfolio import (
    PortfolioAnalysisRequest,
    PortfolioAnalysisAckData,
)

logger = get_logger(__name__)


class PortfolioAnalysisService:
    """포트폴리오 분석 및 질문 풀 생성 서비스"""

    def __init__(self):
        self._profile_generator = PortfolioProfileGenerator()
        self._qpool_generator = PortfolioQuestionPoolGenerator()
        self._portfolio_repo = PortfolioRepository()

    @observe(name="portfolio_analysis")
    async def analyze_portfolio(
        self, request: PortfolioAnalysisRequest
    ) -> PortfolioAnalysisAckData:
        """포트폴리오를 분석하여 요약 + 질문 풀 생성 후 MongoDB에 저장
 
        Args:
            request: 포트폴리오 분석 요청
 
        Returns:
            포트폴리오 분석 완료 확인 데이터
        """
        user_id = request.user_id
        portfolio_id = request.portfolio_id
        portfolio = request.portfolio
 
        logger.info(
            "Portfolio analysis started | "
            "user_id=%s | portfolio_id=%s | projects=%s",
            user_id,
            portfolio_id,
            len(portfolio.projects),
        )
 
        # ── Step 1: 포트폴리오 분석 프로필 생성 ──
        analysis_profile = await self._profile_generator.pf_analyze(
            user_id=user_id,
            portfolio_id=portfolio_id,
            portfolio=portfolio,
        )
 
        logger.info(
            "Analysis profile generated | "
            "user_id=%s | portfolio_id=%s | "
            "tech_tags=%s | aspect_tags=%s",
            user_id,
            portfolio_id,
            analysis_profile.overall_tech_tags,
            analysis_profile.overall_aspect_tags,
        )
 
        # ── Step 2: 분석 프로필 MongoDB 저장 ──
        await self._portfolio_repo.save_analysis_profile(
            analysis_profile.model_dump()
        )
 
        # ── Step 3: 질문 풀 생성 ──
        question_pool = await self._qpool_generator.generate(
            user_id=user_id,
            portfolio_id=portfolio_id,
            analysis_profile=analysis_profile,
        )
 
        logger.info(
            "Question pool generated | "
            "user_id=%s | portfolio_id=%s | count=%s",
            user_id,
            portfolio_id,
            len(question_pool),
        )
 
        # ── Step 4: 질문 풀 MongoDB 저장 ──
        saved_count = await self._portfolio_repo.save_question_pool(
            [q.model_dump() for q in question_pool]
        )
 
        logger.info(
            "Portfolio analysis completed | "
            "user_id=%s | portfolio_id=%s | "
            "questions_saved=%s",
            user_id,
            portfolio_id,
            saved_count,
        )
 
        return PortfolioAnalysisAckData(
            user_id=user_id,
            portfolio_id=portfolio_id,
        )