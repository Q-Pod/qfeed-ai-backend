from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ============================================================
# 공통 차원 점수 구조
# ============================================================

class WeaknessDimensionScore(BaseModel):
    """
    특정 차원(correctness, evidence 등)에 대한 누적 약점 점수.

    - score: 현재 대표 점수 (초기에는 average와 동일하게 운영 가능)
    - total_score_sum: 누적 점수 합
    - attempt_count: 이 차원이 관측된 총 횟수
    - last_score: 가장 최근 턴에서 반영된 점수
    """
    score: float = 0.0
    total_score_sum: float = 0.0
    attempt_count: int = 0

    last_score: float = 0.0
    last_observed_at: Optional[datetime] = None
    last_session_id: Optional[str] = None
    last_question_id: Optional[str] = None


# ============================================================
# CS weakness 구조
# ============================================================

class CSWeaknessDimensions(BaseModel):
    correctness: WeaknessDimensionScore = Field(default_factory=WeaknessDimensionScore)
    completeness: WeaknessDimensionScore = Field(default_factory=WeaknessDimensionScore)
    reasoning: WeaknessDimensionScore = Field(default_factory=WeaknessDimensionScore)
    depth: WeaknessDimensionScore = Field(default_factory=WeaknessDimensionScore)
    delivery: WeaknessDimensionScore = Field(default_factory=WeaknessDimensionScore)


class CSSubcategoryWeakness(BaseModel):
    subcategory: str
    attempt_count: int = 0
    dimensions: CSWeaknessDimensions = Field(default_factory=CSWeaknessDimensions)

    last_session_id: Optional[str] = None
    last_question_id: Optional[str] = None
    last_observed_at: Optional[datetime] = None


class CSCategoryWeakness(BaseModel):
    category: str
    attempt_count: int = 0
    dimensions: CSWeaknessDimensions = Field(default_factory=CSWeaknessDimensions)
    subcategories: list[CSSubcategoryWeakness] = Field(default_factory=list)

    last_session_id: Optional[str] = None
    last_question_id: Optional[str] = None
    last_observed_at: Optional[datetime] = None


class CSWeaknessProfile(BaseModel):
    categories: list[CSCategoryWeakness] = Field(default_factory=list)


# ============================================================
# Portfolio weakness 구조
# ============================================================

class PortfolioWeaknessDimensions(BaseModel):
    evidence: WeaknessDimensionScore = Field(default_factory=WeaknessDimensionScore)
    tradeoff: WeaknessDimensionScore = Field(default_factory=WeaknessDimensionScore)
    problem_solving: WeaknessDimensionScore = Field(default_factory=WeaknessDimensionScore)
    depth: WeaknessDimensionScore = Field(default_factory=WeaknessDimensionScore)
    delivery: WeaknessDimensionScore = Field(default_factory=WeaknessDimensionScore)


class PortfolioTechWeakness(BaseModel):
    tech_tag: str
    attempt_count: int = 0
    dimensions: PortfolioWeaknessDimensions = Field(default_factory=PortfolioWeaknessDimensions)

    last_session_id: Optional[str] = None
    last_question_id: Optional[str] = None
    last_observed_at: Optional[datetime] = None


class PortfolioAspectWeakness(BaseModel):
    aspect_tag: str
    attempt_count: int = 0
    dimensions: PortfolioWeaknessDimensions = Field(default_factory=PortfolioWeaknessDimensions)

    last_session_id: Optional[str] = None
    last_question_id: Optional[str] = None
    last_observed_at: Optional[datetime] = None


class PortfolioTechAspectWeakness(BaseModel):
    tech_tag: str
    aspect_tag: str
    attempt_count: int = 0
    dimensions: PortfolioWeaknessDimensions = Field(default_factory=PortfolioWeaknessDimensions)

    last_session_id: Optional[str] = None
    last_question_id: Optional[str] = None
    last_observed_at: Optional[datetime] = None


class PortfolioWeaknessProfile(BaseModel):
    tech_tags: list[PortfolioTechWeakness] = Field(default_factory=list)
    aspect_tags: list[PortfolioAspectWeakness] = Field(default_factory=list)
    tech_aspect_pairs: list[PortfolioTechAspectWeakness] = Field(default_factory=list)


# ============================================================
# 최종 문서
# ============================================================

class UserWeaknessProfilesDocument(BaseModel):
    user_id: int

    practice_cs: Optional[CSWeaknessProfile] = None
    real_cs: Optional[CSWeaknessProfile] = None
    real_portfolio_personalized: Optional[PortfolioWeaknessProfile] = None

    schema_version: int = 1
