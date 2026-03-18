from typing import Literal, Optional
from pydantic import BaseModel, Field

from schemas.feedback import InterviewType, QuestionType


class SessionTopicSummaryDocument(BaseModel):
    user_id: int
    session_id: str
    interview_type: InterviewType
    question_type: QuestionType

    topic_id: int
    topic: str

    key_points: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    depth_reached: Literal["surface", "moderate", "deep"]
    technologies_mentioned: list[str] = Field(default_factory=list)

    turn_start_order: Optional[int] = None
    turn_end_order: Optional[int] = None

    source_question_id: Optional[int] = None

    schema_version: int = 1