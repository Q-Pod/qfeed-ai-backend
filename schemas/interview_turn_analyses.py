from typing import Optional, Union
from datetime import datetime
from pydantic import BaseModel, Field
from schemas.feedback import InterviewType, QuestionType
from schemas.question import CSFollowUpDirection, PortfolioFollowUpDirection, RouteDecision


class CSAnalysisDocument(BaseModel):
    type: QuestionType = QuestionType.CS
    correctness: str
    has_error: bool
    completeness: str
    has_missing_concepts: bool
    depth: str
    is_superficial: bool
    is_well_structured: bool


class PortfolioAnalysisDocument(BaseModel):
    type: QuestionType = QuestionType.PORTFOLIO
    completeness: str
    has_evidence: bool
    has_tradeoff: bool
    has_problem_solving: bool
    is_well_structured: bool


class CSFollowUpDocument(BaseModel):
    type: QuestionType = QuestionType.CS
    direction: CSFollowUpDirection
    direction_detail: str
    reasoning: str


class PortfolioFollowUpDocument(BaseModel):
    type: QuestionType = QuestionType.PORTFOLIO
    direction: PortfolioFollowUpDirection
    direction_detail: str
    reasoning: str


class NewTopicDocument(BaseModel):
    topic_transition_reason: str
    reasoning: str


class EndSessionDocument(BaseModel):
    reasoning: str


class InterviewTurnAnalysisDocument(BaseModel):
    user_id: int
    session_id: str
    interview_type: InterviewType
    question_type: QuestionType
    turn_order: int
    topic_id: int
    route_decision: RouteDecision

    question_text: Optional[str] = None
    answer_text: Optional[str] = None

    question_category: Optional[str] = None
    question_subcategory: Optional[str] = None

    aspect_tags: list[str] = Field(default_factory=list)
    tech_tags: list[str] = Field(default_factory=list)
    tech_aspect_pairs: list[dict] = Field(default_factory=list)

    portfolio_id: Optional[int] = None # Only applicable for portfolio questions
    question_id: Optional[int] = None 

    analysis: Optional[Union[CSAnalysisDocument, PortfolioAnalysisDocument]] = None
    follow_up: Optional[Union[CSFollowUpDocument, PortfolioFollowUpDocument]] = None
    new_topic: Optional[NewTopicDocument] = None
    end_session: Optional[EndSessionDocument] = None

    schema_version: int = 1
    weakness_processed: bool = False
    weakness_processed_at: datetime | None = None
