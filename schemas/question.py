from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field

from schemas.common import BaseResponse
from schemas.feedback import (
    QATurn, 
    QuestionType, 
    QuestionCategory,
    BadCaseFeedback, 
    BadCaseResult
)


class RouteDecision(str, Enum):
    """라우터 노드의 분기 결정"""
    FOLLOW_UP = "follow_up"          # 꼬리질문 생성
    NEW_TOPIC = "new_topic"          # 새 토픽 질문 생성
    END_SESSION = "end_session"      # 면접 세션 종료


# ============================================================
# Portfolio 관련 스키마
# ============================================================

class PortfolioProject(BaseModel):
    """포트폴리오 프로젝트 정보"""
    project_name: str = Field(..., description="프로젝트 이름")
    tech_stack: list[str] = Field(default_factory=list, description="사용 기술 스택")
    problem_solved: str | None = Field(None, description="해결한 문제")
    achievements: str | None = Field(None, description="성과 및 결과")
    role: str | None = Field(None, description="담당 역할")
    duration: str | None = Field(None, description="프로젝트 기간")


class Portfolio(BaseModel):
    """포트폴리오 정보"""
    projects: list[PortfolioProject] = Field(
        default_factory=list, 
        description="포트폴리오 프로젝트 목록"
    )
    summary: str | None = Field(None, description="포트폴리오 요약")


# ============================================================
# Request 스키마
# ============================================================

class QuestionGenerateRequest(BaseModel):
    """질문 생성 요청 - Java 백엔드 → AI 서버"""
    user_id: int = Field(..., description="사용자 ID")
    session_id: str = Field(..., description="면접 세션 ID")
    question_type: QuestionType = Field(..., description="질문 유형 (CS/SYSTEM_DESIGN/PORTFOLIO)")
    initial_category: QuestionCategory | None = Field(None, description="사용자가 선택한 초기 질문 카테고리")
    interview_history: list[QATurn] = Field(
        default_factory=list, 
        description="면접 Q&A 히스토리"
    )
    # V3때 도입
    # portfolio: Portfolio | None = Field(
    #     None, 
    #     description="포트폴리오 정보 (question_type이 PORTFOLIO일 경우 필수)"
    # )

# ============================================================
# Response 스키마
# ============================================================

class GeneratedQuestion(BaseModel):
    """생성된 질문"""
    user_id: int
    session_id: str
    question_text: str | None = Field(
        None, 
        description="질문 텍스트 (세션 종료 시 None)"
    )
    category: QuestionCategory | None = Field(None, description="문제 카테고리")
    topic_id: int = Field(..., description="토픽 ID")
    turn_type: Literal["new_topic", "follow_up"] = Field(..., description="질문 유형")
    
    # 세션 종료 플래그
    is_session_ended: bool = Field(
        default=False, 
        description="면접 세션 종료 여부"
    )
    end_reason: str | None = Field(
        None, 
        description="종료 사유 (is_session_ended=True일 때)"
    )

    # Bad case 관련
    is_bad_case: bool = Field(
        default=False,
        description="Bad case 여부"
    )
    bad_case_feedback: BadCaseFeedback | None = Field(
        None,
        description="Bad case 피드백 (is_bad_case=True일 때)"
    )


class QuestionGenerateResponse(BaseResponse[GeneratedQuestion]):
    """질문 생성 응답"""
    message: Literal[
        "question_generated",
        "bad_case_detected",
        "session_ended",
    ] = "question_generated"
    data: GeneratedQuestion

    @classmethod
    def from_graph_result(cls, result: dict) -> "QuestionGenerateResponse":
        """그래프 실행 결과로부터 응답 생성"""

        generated_question = result.get("generated_question")
        
        # message 결정
        if generated_question.is_session_ended:
            message = "session_ended"
        else:
            message = "question_generated"

        return cls(
            message=message,
            data=generated_question,
        )

    @classmethod
    def from_bad_case(
        cls,
        user_id: int,
        session_id: str,
        bad_case_result: BadCaseResult,
        interview_history: list[QATurn],
    ) -> "QuestionGenerateResponse":
        """Bad case 결과로부터 응답 생성
        """
        # 현재 토픽 ID 계산
        current_topic_id = 1
        if interview_history:
            current_topic_id = max(t.topic_id for t in interview_history)
        
        generated = GeneratedQuestion(
            user_id = user_id,
            session_id = session_id,
            question_text=None,
            topic_id=current_topic_id,
            turn_type="follow_up",
            is_session_ended=False,
            end_reason=None,
            is_bad_case=True,
            bad_case_feedback=bad_case_result.bad_case_feedback,
        )
        
        return cls(
            message="bad_case_detected",
            data=generated,
        )

    @classmethod
    def from_user_requested_end(
        cls,
        user_id: int,
        session_id: str,
        interview_history: list[QATurn],
    ) -> "QuestionGenerateResponse":
        """사용자 요청(면접 종료 발화)으로 세션 종료 시 응답 생성"""
        current_topic_id = 1
        last_turn_type: Literal["new_topic", "follow_up"] = "new_topic"
        last_category = None
        if interview_history:
            current_topic_id = max(t.topic_id for t in interview_history)
            last_turn = interview_history[-1]
            last_turn_type = last_turn.turn_type
            last_category = last_turn.category

        generated = GeneratedQuestion(
            user_id=user_id,
            session_id=session_id,
            question_text="수고하셨습니다. 면접을 종료합니다.",
            category=last_category,
            topic_id=current_topic_id,
            turn_type=last_turn_type,
            is_session_ended=True,
            end_reason="사용자 요청으로 면접 종료",
            is_bad_case=False,
            bad_case_feedback=None,
        )
        return cls(message="session_ended", data=generated)


# ============================================================
# LLM 구조화 출력용 스키마
# ============================================================

class RouterOutput(BaseModel):
    """라우터 노드 LLM 출력"""
    decision: RouteDecision = Field(..., description="분기 결정")
    reasoning: str = Field(..., description="결정 이유")


class SessionEndIntentOutput(BaseModel):
    """사용자 발화가 면접 종료 요청인지 분류 결과"""

    should_end: bool = Field(..., description="사용자가 지금 면접 종료를 요청하는지 여부")
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="판단 confidence (0.0~1.0). 보수적으로 높을 때만 종료.",
    )


class QuestionOutput(BaseModel):
    """질문 생성 노드 LLM 출력"""
    question_text: str = Field(..., description="생성된 질문")
    category: str = Field(..., description="선택한 카테고리 (new_topic일 경우)")
    cushion_text: str = Field(
        description="이전 주제를 마무리하고 화제를 전환하거나, 면접의 시작을 알리는 1~2문장의 호응어"
    )


class FollowUpOutput(BaseModel):
    cushion_text: str = Field(
        description="지원자의 직전 답변에 대한 공감, 요약, 긍정적 수용, 또는 부드러운 화제 전환을 위한 1~2문장의 호응어"
    )
    question_text: str = Field(
        description="지원자의 역량을 검증하기 위해 던지는 구체적이고 명확한 핵심 꼬리질문 (호응어 제외)"
    )