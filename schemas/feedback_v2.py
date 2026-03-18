# schemas/feedback_v2.py

"""
피드백 생성 v2 스키마

핵심 설계:
    - 루브릭 산출: router_analyses (매 턴 bool 집계) → rule-based 점수
    - topic_summaries: 피드백 텍스트 생성에서만 사용 (맥락 요약)
    - router_analyses의 str 분석 내용: 피드백 텍스트의 상세 근거
"""

from typing import Literal
from enum import Enum
from pydantic import BaseModel, Field

from schemas.feedback import (
    # 기존 스키마 재사용
    InterviewType,
    QuestionType,
    QuestionCategory,
    QATurn,
    BadCaseFeedback,
    BadCaseResult,
    KeywordCheckResult,
)
from schemas.common import BaseResponse


# ============================================================
# 분석 데이터 스키마 (질문 생성에서 누적 → 백엔드 저장 → 피드백 요청 시 전달)
# 용도 : 피드백 텍스트 생성의 상세 근거 + 변화 과정 추적
# ============================================================

class RouterAnalysisTurn(BaseModel):
    """매 턴의 라우터 분석 결과

    질문 생성 파이프라인에서 router가 매 턴 생성한 분석 데이터.
    백엔드가 저장 후 피드백 요청 시 전달한다.

    CS와 포트폴리오의 분석 필드가 다르므로 모두 optional.
    question_type에 따라 rubric_scorer가 필요한 필드만 읽는다.
    """
    topic_id: int = Field(..., description="토픽 ID")
    turn_order: int = Field(..., description="턴 순서")
    turn_type: Literal["new_topic", "follow_up"] = Field(..., description="턴 유형")

    # ── 포트폴리오 분석 필드 ──
    completeness_detail: str | None = Field(None, description="답변 완성도 평가 (1-2문장)")
    has_evidence: bool | None = Field(None, description="구체적 수치/경험/사례 포함 여부")
    has_tradeoff: bool | None = Field(None, description="기술 선택의 장단점/대안 비교 포함 여부")
    has_problem_solving: bool | None = Field(None, description="문제 상황과 해결 과정 설명 포함 여부")

    # ── CS 분석 필드 ──
    correctness_detail: str | None = Field(None, description="정확성 평가 (1-2문장)")
    has_error: bool | None = Field(None, description="사실적 오류 포함 여부")
    completeness_cs_detail: str | None = Field(None, description="완성도 평가 (1-2문장)")
    has_missing_concepts: bool | None = Field(None, description="핵심 개념 누락 여부")
    depth_detail: str | None = Field(None, description="깊이 평가 (1-2문장)")
    is_superficial: bool | None = Field(None, description="표면적 정의에 그쳤는지 여부")

    # ── 공통 ──
    is_well_structured: bool | None = Field(None, description="논리적 구조로 전달되었는가")
    follow_up_direction: str | None = Field(None, description="꼬리질문 방향")


class PortfolioTopicSummaryData(BaseModel):
    """포트폴리오 토픽 요약

    토픽 전체 Q&A를 종합한 피드백 생성.
    꼬리질문에서 보완한 내용도 반영된다.
    """
    topic_id: int = Field(..., description="토픽 ID")
    topic: str = Field(..., description="토픽 핵심 주제")
    key_points: list[str] = Field(default_factory=list, description="지원자가 설명한 핵심 포인트")
    gaps: list[str] = Field(default_factory=list, description="부족하거나 빠진 부분")
    depth_reached: Literal["surface", "moderate", "deep"] = Field(..., description="답변 깊이")
    technologies_mentioned: list[str] = Field(default_factory=list, description="언급된 기술 목록")

class CSTopicSummaryData(BaseModel):
    """CS 토픽 요약

    토픽 전체 Q&A를 종합한 피드백 생성.
    """
    topic_id: int = Field(..., description="토픽 ID")
    topic: str = Field(..., description="토픽 핵심 주제")
    key_points: list[str] = Field(default_factory=list, description="지원자가 설명한 핵심 포인트")
    gaps: list[str] = Field(default_factory=list, description="부족하거나 빠진 부분")
    depth_reached: Literal["surface", "moderate", "deep"] = Field(..., description="답변 깊이")




# ============================================================
# 루브릭 점수 스키마 (질문 유형별 분리)
# ============================================================

class PortfolioRubricScores(BaseModel):
    """포트폴리오 루브릭 점수 (5개 지표)

    실전모드: rule-based scorer가 router_analyses + topic_summaries로 산출
    """
    evidence: int = Field(..., ge=1, le=5, description="근거 제시력")
    tradeoff: int = Field(..., ge=1, le=5, description="트레이드오프 인식")
    problem_solving: int = Field(..., ge=1, le=5, description="문제해결 과정")
    depth: int = Field(..., ge=1, le=5, description="기술적 깊이")
    delivery: int = Field(..., ge=1, le=5, description="전달력")

    def to_metrics_list(self) -> list[dict]:
        return [
            {"name": "근거 제시력", "score": self.evidence},
            {"name": "트레이드오프 인식", "score": self.tradeoff},
            {"name": "문제해결 과정", "score": self.problem_solving},
            {"name": "기술적 깊이", "score": self.depth},
            {"name": "전달력", "score": self.delivery},
        ]


class CSRubricScores(BaseModel):
    """CS 루브릭 점수 (5개 지표)

    실전모드: rule-based scorer가 router_analyses로 산출
    연습모드: LLM structured output으로 직접 산출
    """
    correctness: int = Field(..., ge=1, le=5, description="정확성")
    completeness: int = Field(..., ge=1, le=5, description="완성도")
    reasoning: int = Field(..., ge=1, le=5, description="논리적 추론")
    depth: int = Field(..., ge=1, le=5, description="깊이")
    delivery: int = Field(..., ge=1, le=5, description="전달력")

    def to_metrics_list(self) -> list[dict]:
        return [
            {"name": "정확성", "score": self.correctness},
            {"name": "완성도", "score": self.completeness},
            {"name": "논리적 추론", "score": self.reasoning},
            {"name": "깊이", "score": self.depth},
            {"name": "전달력", "score": self.delivery},
        ]


# class SystemDesignRubricScores(BaseModel):
#     """시스템디자인 루브릭 점수 (5개 지표)

#     연습모드: LLM structured output으로 직접 산출
#     """
#     requirements: int = Field(..., ge=1, le=5, description="요구사항 파악")
#     architecture: int = Field(..., ge=1, le=5, description="아키텍처 설계 논리")
#     scalability: int = Field(..., ge=1, le=5, description="확장성 고려")
#     tradeoff: int = Field(..., ge=1, le=5, description="트레이드오프 인식")
#     delivery: int = Field(..., ge=1, le=5, description="전달력")

#     def to_metrics_list(self) -> list[dict]:
#         return [
#             {"name": "요구사항 파악", "score": self.requirements},
#             {"name": "설계 논리", "score": self.architecture},
#             {"name": "확장성", "score": self.scalability},
#             {"name": "트레이드오프", "score": self.tradeoff},
#             {"name": "전달력", "score": self.delivery},
#         ]


# ============================================================
# 피드백 요청 스키마
# ============================================================

class FeedbackRequest(BaseModel):
    """피드백 생성 요청 v2 — 통합 스키마

    연습모드와 실전모드가 같은 엔드포인트를 사용하되,
    interview_type에 따라 필요한 필드가 다르다.

    연습모드 필수: question_id, keywords
    실전모드 필수: session_id, router_analyses
    실전모드 포트폴리오: topic_summaries 추가
    """
    user_id: int = Field(..., description="사용자 ID")
    interview_type: InterviewType = Field(..., description="면접 유형")
    question_type: QuestionType = Field(..., description="질문 유형")
    interview_history: list[QATurn] = Field(..., description="면접 Q&A 히스토리")

    # 연습모드 전용
    question_id: int | None = Field(None, description="문제 ID (연습모드)")
    keywords: list[str] | None = Field(None, description="필수 키워드 목록 (연습모드)")
    category: QuestionCategory | None = Field(None, description="문제 카테고리 (연습모드)")

    # 실전모드 전용
    session_id: str | None = Field(None, description="면접 세션 ID (실전모드)")
    router_analyses: list[RouterAnalysisTurn] | None = Field(
        None, description="매 턴의 라우터 분석 결과 (실전모드)"
    )
    # 유형별 TopicSummary — 둘 중 하나만 존재
    portfolio_topic_summaries: list[PortfolioTopicSummaryData] | None = Field(
        None, description="포트폴리오 토픽별 요약 (루브릭 산출 + 피드백 생성)"
    )
    cs_topic_summaries: list[CSTopicSummaryData] | None = Field(
        None, description="CS 토픽별 요약 (루브릭 산출 + 피드백 생성)"
    )


# ============================================================
# 피드백 출력 스키마
# ============================================================

class TopicFeedback(BaseModel):
    """개별 토픽 피드백 v2"""
    topic_id: int = Field(..., description="토픽 ID")
    topic_name: str = Field(..., description="토픽명")
    strengths: str = Field(..., description="해당 토픽에서 잘한 점 (150-800자)")
    improvements: str = Field(..., description="해당 토픽에서 개선할 점 (150-800자)")
    action_items: list[str] = Field(
        ..., description="구체적 개선 행동 (최대 3개)"
    )


class OverallFeedback(BaseModel):
    """종합 피드백 v2"""
    strengths: str = Field(..., description="전체적으로 잘한 점 (150-800자)")
    improvements: str = Field(..., description="전체적으로 개선할 점 (150-800자)")
    action_items: list[str] = Field(
        ..., description="구체적 개선 행동 (최대 3개)"
    )


class RealModeFeedback(BaseModel):
    """실전모드 피드백 LLM 출력: 토픽별 + 종합"""
    topics_feedback: list[TopicFeedback]
    overall_feedback: OverallFeedback


# ============================================================
# 피드백 응답 스키마
# ============================================================

class RubricMetric(BaseModel):
    """루브릭 지표 하나"""
    name: str = Field(..., description="지표명")
    score: int = Field(..., ge=1, le=5, description="점수")


class FeedbackData(BaseModel):
    """피드백 응답 데이터 v2"""
    user_id: int
    question_id: int | None = None
    session_id: str | None = None
    question_type: QuestionType

    # Bad case
    bad_case_feedback: BadCaseFeedback | None = None

    # 루브릭 (질문 유형에 따라 지표명이 다름)
    metrics: list[RubricMetric] | None = None

    # 키워드 체크 (연습모드만)
    keyword_result: KeywordCheckResult | None = None

    # 피드백 텍스트
    topics_feedback: list[TopicFeedback] | None = None
    overall_feedback: OverallFeedback | None = None


class FeedbackResponse(BaseResponse[FeedbackData]):
    """피드백 API 응답 v2"""
    message: Literal[
        "feedback_generated",
        "bad_case_detected",
    ] = "feedback_generated"
    data: FeedbackData

    @classmethod
    def from_bad_case(
        cls,
        user_id: int,
        question_id: int | None,
        session_id: str | None,
        question_type: QuestionType,
        bad_case_result: BadCaseResult,
    ) -> "FeedbackResponse":
        return cls(
            message="bad_case_detected",
            data=FeedbackData(
                user_id=user_id,
                question_id=question_id,
                session_id=session_id,
                question_type=question_type,
                bad_case_feedback=bad_case_result.bad_case_feedback,
            ),
        )

    @classmethod
    def from_practice_evaluation(
        cls,
        user_id: int,
        question_id: int,
        question_type: QuestionType,
        rubric_scores: CSRubricScores,
        keyword_result: KeywordCheckResult | None,
        overall_feedback: OverallFeedback,
    ) -> "FeedbackResponse":
        return cls(
            message="feedback_generated",
            data=FeedbackData(
                user_id=user_id,
                question_id=question_id,
                question_type=question_type,
                metrics=[RubricMetric(**m) for m in rubric_scores.to_metrics_list()],
                keyword_result=keyword_result,
                overall_feedback=overall_feedback,
            ),
        )

    @classmethod
    def from_realmode_evaluation(
        cls,
        user_id: int,
        session_id: str,
        question_type: QuestionType,
        rubric_scores: PortfolioRubricScores | CSRubricScores,
        topics_feedback: list[TopicFeedback],
        overall_feedback: OverallFeedback,
    ) -> "FeedbackResponse":
        return cls(
            message="feedback_generated",
            data=FeedbackData(
                user_id=user_id,
                session_id=session_id,
                question_type=question_type,
                metrics=[RubricMetric(**m) for m in rubric_scores.to_metrics_list()],
                topics_feedback=topics_feedback,
                overall_feedback=overall_feedback,
            ),
        )