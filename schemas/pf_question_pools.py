from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class TechAspectPair(BaseModel):
    tech_tag: str = Field(..., description="기술 태그 canonical_key")
    aspect_tag: str = Field(..., description="관점 태그 id")


# ══════════════════════════════════════
# LLM 출력 스키마 (질문 풀 생성용)
# ══════════════════════════════════════


class PortfolioQuestionPoolItemOutput(BaseModel):
    """LLM이 생성하는 개별 질문 항목"""

    project_name: Optional[str] = Field(
        default=None,
        description="관련 프로젝트명. 특정 프로젝트에 귀속되지 않는 질문이면 null",
    )
    question_text: str = Field(
        ...,
        description="실제 면접 질문 문장",
    )
    tech_aspect_pairs: list[TechAspectPair] = Field(
        default_factory=list,
        description=(
            "질문이 실제로 검증하려는 기술-관점 pair 목록. "
            "tech_tag는 canonical_key, aspect_tag는 aspect id를 사용"
        ),
    )
    intent: Optional[str] = Field(
        default=None,
        description="질문의 주된 의도. 예: 검증, 심화, 근거확인, 트러블슈팅 확인",
    )
    priority: int = Field(
        default=3,
        ge=1,
        le=5,
        description="질문의 중요도. 1~5 범위, 높을수록 우선순위 높음",
    )
    difficulty: Optional[str] = Field(
        default=None,
        description="질문 난이도. easy, medium, hard 중 선택",
    )
    follow_up_hints: list[str] = Field(
        default_factory=list,
        description="이 질문 이후 이어서 물을 수 있는 후속 질문 힌트",
    )
    source_summary_snippets: list[str] = Field(
        default_factory=list,
        description="이 질문이 어떤 분석 근거에서 나왔는지 보여주는 요약 스니펫",
    )


class PortfolioQuestionPoolLLMResponse(BaseModel):
    """LLM 응답 래퍼 — generate_structured의 response_model로 사용"""

    questions: list[PortfolioQuestionPoolItemOutput] = Field(
        ...,
        description="생성된 면접 질문 목록",
    )


# ══════════════════════════════════════
# MongoDB Document 스키마
# ══════════════════════════════════════


class PortfolioQuestionPoolDocument(BaseModel):
    """MongoDB에 저장되는 질문 풀 문서"""

    user_id: int
    portfolio_id: int

    question_id: int 
    project_name: Optional[str] = None

    question_text: str

    tech_tags: list[str] = Field(default_factory=list)
    aspect_tags: list[str] = Field(default_factory=list)
    tech_aspect_pairs: list[TechAspectPair] = Field(default_factory=list)

    intent: Optional[str] = None
    priority: int = 3
    difficulty: Optional[str] = None

    follow_up_hints: list[str] = Field(default_factory=list)
    source_summary_snippets: list[str] = Field(default_factory=list)

    # 운영 필드
    active: bool = True
    used_count: int = 0
    last_used_at: Optional[datetime] = None

    schema_version: int = 1
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
