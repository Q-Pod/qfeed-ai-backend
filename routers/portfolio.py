# routers/portfolio.py

"""포트폴리오 분석 API 라우터

포트폴리오를 입력받아 면접용 요약과 질문 풀을 생성한다.

엔드포인트:
    POST /ai/portfolio
        - 포트폴리오 텍스트 + 아키텍처 이미지 URL을 받아 분석
        - 면접용 요약(portfolio_summary)과 질문 풀(question_pool) 반환

호출 시점:
    - 사용자가 포트폴리오를 등록하거나 수정했을 때
    - Java 백엔드가 호출하여 결과를 DB에 저장
    - 면접 세션 시작 시 저장된 결과를 조회하여 AI 서버에 전달
"""

from fastapi import APIRouter

from schemas.portfolio import (
    PortfolioAnalysisRequest,
    PortfolioAnalysisResponse,
    PortfolioAnalysisAckData,
)
from services.portfolio_analysis_service import PortfolioAnalysisService
from core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()

@router.post("/portfolio",response_model=PortfolioAnalysisResponse)
async def analyze_portfolio(
    request: PortfolioAnalysisRequest,
) -> PortfolioAnalysisResponse:
    """포트폴리오 분석 엔드포인트

    Args:
        request: 포트폴리오 분석 요청 (user_id + 프로젝트 정보)

    Returns:
        portfolio_summary + question_pool (ID 포함)
    """

    logger.info("Portfolio analysis request")

    service = PortfolioAnalysisService()
    response = await service.analyze_portfolio(request)

    logger.info(
        "Portfolio analysis completed | user_id=%s | portfolio_id=%s",
        request.user_id,
        response.portfolio_id,
    )

    return PortfolioAnalysisResponse(
        message="pf_analysis_completed",
        data=PortfolioAnalysisAckData(
            user_id=request.user_id,
            portfolio_id=response.portfolio_id,
        ),
    )