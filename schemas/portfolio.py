# ============================================================
# Portfolio 관련 스키마
# ============================================================
from pydantic import BaseModel, Field
from schemas.common import BaseResponse 

class PortfolioProject(BaseModel):
    """포트폴리오 프로젝트 정보"""
    project_name: str = Field(..., description="프로젝트 이름")
    tech_stack: str = Field(..., description="사용 기술 스택")
    arch_image_url: str | None = Field(None, description="아키텍처 이미지 URL")
    content: str = Field(..., description="프로젝트 설명")   
    role: str | None = Field(None, description="담당 역할")


class Portfolio(BaseModel):
    """포트폴리오 정보"""
    projects: list[PortfolioProject] = Field(
        default_factory=list, 
        description="포트폴리오 프로젝트 목록"
    )

class PortfolioAnalysisRequest(BaseModel):
    """포트폴리오 분석 요청 - Java 백엔드 → AI 서버"""
    user_id: int = Field(..., description="사용자 ID")
    portfolio_id: int = Field(..., description="포트폴리오 ID")
    portfolio: Portfolio = Field(..., description="포트폴리오 정보")


class PortfolioProjectSummary(BaseModel):
    project_name: str = Field(..., description="프로젝트명")
    one_line_summary: str = Field(..., description="프로젝트 한 줄 요약")
    tech_tags: list[str] = Field(
        default_factory=list,
        description=(
            "프로젝트 핵심 기술 태그. "
            "반드시 taxonomy의 canonical_key를 사용"
        ),
    )
    likely_aspect_tags: list[str] = Field(
        default_factory=list,
        description=(
            "면접에서 검증할 가능성이 높은 관점 태그. "
            "반드시 taxonomy의 aspect id를 사용"
        ),
    )
    key_points: list[str] = Field(
        default_factory=list,
        description="이 프로젝트에서 핵심적으로 짚어야 할 포인트",
    )
    risky_points: list[str] = Field(
        default_factory=list,
        description="근거 검증이 필요하거나 깊게 확인할 리스크 포인트",
    )


# ============================================================
# LLM 출력 스키마 (질문 풀 생성용)
# ============================================================

class PortfolioAnalysisProfileOutput(BaseModel):
    portfolio_summary: str = Field(
        ...,
        description="포트폴리오 전체를 면접관 관점에서 요약한 설명",
    )
    overall_tech_tags: list[str] = Field(
        default_factory=list,
        description=(
            "포트폴리오 전반에서 드러나는 주요 기술 태그. "
            "반드시 taxonomy의 canonical_key를 사용 (예: spring_boot, redis). "
            "목록에 없는 기술은 _unknown_ 접두사를 붙여 제안 (예: _unknown_supabase)"
        ),
    )
    overall_aspect_tags: list[str] = Field(
        default_factory=list,
        description=(
            "포트폴리오 전반에서 드러나는 주요 평가 관점 태그. "
            "반드시 taxonomy의 aspect id를 사용 "
            "(예: design_intent, tradeoff, optimization)"
        ),
    )
    project_summaries: list[PortfolioProjectSummary] = Field(
        default_factory=list,
        description="프로젝트별 요약 정보",
    )
    strong_points: list[str] = Field(
        default_factory=list,
        description="포트폴리오 전체에서 강점으로 보이는 점",
    )
    risky_points: list[str] = Field(
        default_factory=list,
        description="포트폴리오 전체에서 추가 검증이 필요하거나 약점이 될 수 있는 점",
    )
    recommended_question_focuses: list[str] = Field(
        default_factory=list,
        description="면접 질문 설계 시 우선적으로 파고들어야 할 포커스",
    )


# ============================================================
# 응답 스키마 (AI 서버 → Java 백엔드)
# ============================================================

class PortfolioAnalysisAckData(BaseModel):
    user_id: int = Field(..., description="사용자 ID")
    portfolio_id: int = Field(..., description="포트폴리오 ID")

PortfolioAnalysisResponse = BaseResponse[PortfolioAnalysisAckData]
