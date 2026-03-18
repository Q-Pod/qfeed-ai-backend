from enum import Enum
from typing import Literal, Union, TypeVar, Generic
from pydantic import BaseModel, Field

from schemas.common import BaseResponse
from schemas.pf_question_pools import TechAspectPair
from schemas.feedback import (
    QATurn, 
    QuestionType, 
    QuestionCategory,
    BadCaseFeedback, 
    BadCaseResult
)

# ============================================================
# 공통
# ============================================================

class RouteDecision(str, Enum):
    """라우터 노드의 분기 결정"""
    FOLLOW_UP = "follow_up"          # 꼬리질문 생성
    NEW_TOPIC = "new_topic"          # 새 토픽 질문 생성
    END_SESSION = "end_session"      # 면접 세션 종료

# ============================================================
# 제네릭 Router Result (공통 구조)
# ============================================================

TAnalysis = TypeVar("TAnalysis", bound=BaseModel)
TDirection = TypeVar("TDirection", bound=str)


class FollowUpRouterResult(BaseModel, Generic[TAnalysis, TDirection]):
    """꼬리질문으로 분기 (제네릭)"""
    decision: Literal["follow_up"] = Field(
        "follow_up", description="라우팅 결정"
    )
    analysis: TAnalysis = Field(
        ..., description="답변 분석 결과"
    )
    follow_up_direction: TDirection = Field(
        ..., description="꼬리질문 방향"
    )
    direction_detail: str = Field(
        ..., description="구체적으로 어떤 방향으로 질문할지 설명"
    )
    reasoning: str = Field(
        ..., description="이 방향을 선택한 이유"
    )


class NewTopicRouterResult(BaseModel, Generic[TAnalysis]):
    """새 토픽으로 분기 (제네릭)"""
    decision: Literal["new_topic"] = Field(
        "new_topic", description="라우팅 결정"
    )
    analysis: TAnalysis = Field(
        ..., description="답변 분석 결과"
    )
    topic_transition_reason: str = Field(
        ..., description="토픽을 전환하는 이유 (현재 토픽을 충분히 다룬 근거)"
    )
    reasoning: str = Field(
        ..., description="결정 이유"
    )


class EndSessionRouterResult(BaseModel):
    """면접 종료 (카테고리 공통)"""
    decision: Literal["end_session"] = Field(
        "end_session", description="라우팅 결정"
    )
    analysis: TAnalysis = Field(
        ..., description="답변 분석 결과"
    )
    reasoning: str = Field(
        ..., description="면접을 종료하는 이유"
    )

class SessionEndIntentOutput(BaseModel):
    """LLM이 면접 종료 의도를 내부적으로 판별하기 위한 스키마"""
    is_end_intent: bool = Field(..., description="사용자의 발화가 면접 종료 의도인지 여부")
    confidence: float = Field(..., description="판단에 대한 확신도 (0.0 ~ 1.0)")
    reasoning: str = Field(..., description="판단 근거")



# ============================================================
# Topic Summarizer 출력 스키마
# ============================================================

class TopicSummaryOutput(BaseModel):
    """topic_summarizer 노드의 LLM 출력"""
    topic: str = Field(
        ..., description="토픽 핵심 주제 (예: 'Redis 캐시 전략 설계')"
    )
    key_points: list[str] = Field(
        ..., description="지원자가 명확히 설명한 핵심 포인트 (최대 3개)"
    )
    gaps: list[str] = Field(
        ..., description="답변에서 부족하거나 빠진 부분 (최대 3개)"
    )
    depth_reached: Literal["surface", "moderate", "deep"] = Field(
        ..., description="답변 깊이"
    )
    technologies_mentioned: list[str] = Field(
        ..., description="지원자가 언급한 기술/도구 목록"
    )

# ============================================================
# Portfolio Analysis & Direction 
# ============================================================

class PortfolioFollowUpDirection(str, Enum):
    """포트폴리오 꼬리질문 방향"""
    DEPTH_PROBE = "depth_probe"           # 구체적 구현/동작 방식
    WHY_PROBE = "why_probe"               # 기술 선택 근거
    TRADEOFF_PROBE = "tradeoff_probe"     # 장단점, 대안 비교
    PROBLEM_PROBE = "problem_probe"       # 문제 상황, 실패 경험
    SCALE_PROBE = "scale_probe"           # 확장 시나리오
    CONNECT_PROBE = "connect_probe"       # 이전 토픽과 연결

class PortfolioAnswerAnalysis(BaseModel):
    """포트폴리오 답변 분석"""
    completeness: str = Field(
        ..., description="답변 완성도 평가 (1-2문장)"
    )
    has_evidence: bool = Field(
        ..., description="구체적 수치, 경험, 사례 포함 여부"
    )
    has_tradeoff: bool = Field(
        ..., description="기술 선택의 장단점/대안 비교 포함 여부"
    )
    has_problem_solving: bool = Field(
        ..., description="문제 상황과 해결 과정 설명 포함 여부"
    )
    is_well_structured: bool = Field(
        ..., description="답변이 논리적 순서로 구조화되어 전달되었는가"
    )

# class NewTopicSelectionOutput(BaseModel):
#     """pf_new_topic_generator 노드의 LLM 출력 - 질문 풀에서 선택"""
#     selected_question_id: int = Field(
#         ..., description="선택한 질문의 ID (question_pool에 있는 question_id)"
#     )
#     reasoning: str = Field(
#         ..., description="이 질문을 선택한 이유"
#     )

# Portfolio 타입 별칭
PortfolioFollowUpResult = FollowUpRouterResult[PortfolioAnswerAnalysis, PortfolioFollowUpDirection]
PortfolioNewTopicResult = NewTopicRouterResult[PortfolioAnswerAnalysis]

PortfolioRouterOutput = Union[
    PortfolioFollowUpResult,
    PortfolioNewTopicResult,
    EndSessionRouterResult,
]

# ============================================================
# CS: Analysis & Direction
# ============================================================

class CSFollowUpDirection(str, Enum):
    """CS 꼬리질문 방향
    
    - depth: 같은 개념을 더 구체적으로 파고들기
        예) "TCP 3-way handshake" → "각 단계에서 SYN, ACK 플래그의 역할은?"
    - reasoning: 정의는 맞지만 '왜'를 설명하지 못했을 때
        예) "스레드가 가볍다" → "왜 프로세스보다 컨텍스트 스위칭이 빠른가요?"
    - correction: 개념 설명에 오류가 있을 때 교정 유도
        예) "프로세스끼리 메모리를 공유한다" → "정말 프로세스 간 메모리 공유가 되나요?"
    - lateral: 현재 개념은 충분히 다뤘고, 연관된 인접 개념으로 확장
        예) "TCP handshake 충분" → "그러면 UDP는 왜 handshake 없이 동작할 수 있나요?"
    """
    DEPTH = "depth"               # 같은 개념 심화
    REASONING = "reasoning"       # 원리/이유 요구
    CORRECTION = "correction"     # 오개념 교정 유도
    LATERAL = "lateral"           # 인접 개념 확장


class CSAnswerAnalysis(BaseModel):
    """CS 답변 분석
    
    CS 기초 질문은 명확한 정답이 존재하는 영역이므로,
    정확성/완성도/깊이 세 축으로 답변 품질을 평가한다.
    """
    correctness: str = Field(
        ..., description="개념 설명의 정확성 평가 — 사실적 오류 여부 (1-2문장)"
    )
    has_error: bool = Field(
        ..., description="명백한 사실적 오류 포함 여부 (예: 프로세스가 메모리를 공유한다 등)"
    )
    completeness: str = Field(
        ..., description="핵심 구성요소 누락 여부 평가 (1-2문장)"
    )
    has_missing_concepts: bool = Field(
        ..., description="반드시 언급해야 할 핵심 개념이 빠져있는지 여부"
    )
    depth: str = Field(
        ..., description="표면적 정의에 그쳤는지, 동작 원리/이유까지 설명했는지 평가 (1-2문장)"
    )
    is_superficial: bool = Field(
        ..., description="정의만 나열하고 원리나 이유 설명이 없는지 여부"
    )
    is_well_structured: bool = Field(
    ..., description="답변이 논리적 순서로 구조화되어 전달되었는가"
)


# CS 타입 별칭
CSFollowUpResult = FollowUpRouterResult[CSAnswerAnalysis, CSFollowUpDirection]
CSNewTopicResult = NewTopicRouterResult[CSAnswerAnalysis]

CSRouterOutput = Union[
    CSFollowUpResult,
    CSNewTopicResult,
    EndSessionRouterResult,
]


# ============================================================
# Question Generate Request 스키마
# ============================================================

class QuestionGenerateRequest(BaseModel):
    """질문 생성 요청 - Java 백엔드 → AI 서버"""
    user_id: int = Field(..., description="사용자 ID")
    session_id: str = Field(..., description="면접 세션 ID")
    portfolio_id: int | None = Field(None, description="포토폴리오 ID")
    question_type: QuestionType = Field(..., description="질문 유형 (CS/SYSTEM_DESIGN/PORTFOLIO)")
    interview_history: list[QATurn] = Field(
        default_factory=list, 
        description="면접 Q&A 히스토리"
    )



# ============================================================
# Response 스키마
# ============================================================

class GeneratedQuestion(BaseModel):
    """생성된 질문"""
    user_id: int
    session_id: str
    question_id: int | None = None
    question_text: str | None = Field(
        None,
        description="질문 텍스트 (세션 종료 시 None)"
    )
    category: QuestionCategory | None = Field(None, description="문제 카테고리")
    subcategory: str | None = Field(
        None,
        description="문제 소분류 ID (CS taxonomy subcategory)"
    )
    tech_tags: list[str] = Field(
        default_factory=list,
        description="포트폴리오 질문의 기술 태그",
    )
    aspect_tags: list[str] = Field(
        default_factory=list,
        description="포트폴리오 질문의 관점 태그",
    )
    tech_aspect_pairs: list[TechAspectPair] = Field(
        default_factory=list,
        description="포트폴리오 질문의 기술-관점 pair",
    )
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
    def from_question_pool(
        cls,
        user_id: int,
        session_id: str,
        selected_question: dict,
    ) -> "QuestionGenerateResponse":
        """질문 풀에서 선택된 첫 포트폴리오 질문으로부터 응답 생성"""
        generated = GeneratedQuestion(
            user_id=user_id,
            session_id=session_id,
            question_id=selected_question["question_id"],
            question_text=selected_question["question_text"],
            category=selected_question.get("category"),
            subcategory=selected_question.get("subcategory"),
            tech_tags=selected_question.get("tech_tags", []),
            aspect_tags=selected_question.get("aspect_tags", []),
            tech_aspect_pairs=selected_question.get("tech_aspect_pairs", []),
            topic_id=1,
            turn_type="new_topic",
            is_session_ended=False,
            end_reason=None,
            is_bad_case=False,
            bad_case_feedback=None,
        )

        return cls(
            message="question_generated",
            data=generated,
        )

    @classmethod
    def from_bad_case(
        cls,
        user_id: int,
        session_id: str,
        bad_case_result: BadCaseResult,
        interview_history: list[QATurn],
    ) -> "QuestionGenerateResponse":
        """Bad case 결과로부터 응답 생성"""
        current_topic_id = 1
        if interview_history:
            current_topic_id = max(t.topic_id for t in interview_history)

        generated = GeneratedQuestion(
            user_id=user_id,
            session_id=session_id,
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
        """사용자 요청으로 세션 종료 시 응답 생성"""
        current_topic_id = 1
        last_turn_type: Literal["new_topic", "follow_up"] = "new_topic"
        last_category = None
        last_subcategory = None
        last_tech_tags: list[str] = []
        last_aspect_tags: list[str] = []
        last_tech_aspect_pairs: list[TechAspectPair] = []
        if interview_history:
            current_topic_id = max(t.topic_id for t in interview_history)
            last_turn = interview_history[-1]
            last_turn_type = last_turn.turn_type
            last_category = last_turn.category
            last_subcategory = last_turn.subcategory
            last_tech_tags = list(getattr(last_turn, "tech_tags", []) or [])
            last_aspect_tags = list(getattr(last_turn, "aspect_tags", []) or [])
            last_tech_aspect_pairs = list(
                getattr(last_turn, "tech_aspect_pairs", []) or []
            )

        generated = GeneratedQuestion(
            user_id=user_id,
            session_id=session_id,
            question_text="수고하셨습니다. 면접을 종료합니다.",
            category=last_category,
            subcategory=last_subcategory,
            tech_tags=last_tech_tags,
            aspect_tags=last_aspect_tags,
            tech_aspect_pairs=last_tech_aspect_pairs,
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

class QuestionOutput(BaseModel):
    """질문 생성 노드 LLM 출력"""
    question_text: str = Field(..., description="생성된 질문")
    category: str = Field(..., description="선택한 카테고리 (new_topic일 경우)")
    subcategory: str = Field(..., description="문제 소분류 ID (CS taxonomy subcategory)")
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
    subcategory: str = Field(..., description="문제 소분류 ID (CS taxonomy subcategory)")


class PortfolioFollowUpOutput(BaseModel):
    cushion_text: str = Field(
        description="지원자의 직전 답변에 대한 공감, 요약, 긍정적 수용, 또는 부드러운 화제 전환을 위한 1~2문장의 호응어"
    )
    question_text: str = Field(
        description="지원자의 역량을 검증하기 위해 던지는 구체적이고 명확한 핵심 꼬리질문 (호응어 제외)"
    )
    tech_aspect_pairs: list[TechAspectPair] = Field(
        default_factory=list,
        description="질문과 직접 관련된 기술-관점 pair 목록",
    )
