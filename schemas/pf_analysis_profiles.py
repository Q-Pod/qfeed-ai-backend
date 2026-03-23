from datetime import datetime
from pydantic import BaseModel, Field
from schemas.portfolio import PortfolioProjectSummary


class PortfolioAnalysisProfileDocument(BaseModel):
    user_id: int
    portfolio_id: int

    raw_portfolio_text: str

    portfolio_summary: str
    overall_tech_tags: list[str] = Field(default_factory=list)
    overall_aspect_tags: list[str] = Field(default_factory=list)

    project_summaries: list[PortfolioProjectSummary] = Field(default_factory=list)

    strong_points: list[str] = Field(default_factory=list)
    risky_points: list[str] = Field(default_factory=list)

    recommended_question_focuses: list[str] = Field(default_factory=list)

    schema_version: int = 1
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)