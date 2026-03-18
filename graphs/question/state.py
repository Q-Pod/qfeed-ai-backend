# ============================================================
# graphs/question/state.py (수정안 - 추가 필드만 표시)
# ============================================================

"""
기존 QuestionState에 추가할 필드:

    # 토픽 요약 (topic_summarizer 출력)
    topic_summaries: list[dict]  # 완료된 토픽별 요약 리스트
    topic_transition_reason: str | None  # 토픽 전환 사유 (router에서 설정)
"""

# 아래는 state.py 전체 수정본입니다.
# 기존 코드에서 변경된 부분에 [NEW] 주석을 달았습니다.

from typing import Any
from typing_extensions import TypedDict

from schemas.question import (
    QuestionType,
    QuestionCategory,
    RouteDecision,
    GeneratedQuestion,
)
from schemas.feedback import QATurn


class TopicSummary(TypedDict):
    """완료된 토픽 요약 구조

    topic_summarizer 노드가 생성하여 topic_summaries에 추가한다.

    Attributes:
        topic_id: 토픽 ID
        topic: 토픽명 (예: "Redis 캐시 설계")
        key_points: 지원자가 명확히 설명한 핵심 포인트 (최대 3개)
        gaps: 답변에서 부족하거나 빠진 부분 (최대 3개)
        depth_reached: 답변 깊이 ("surface" | "moderate" | "deep")
        technologies_mentioned: 지원자가 언급한 기술 목록
        transition_reason: 토픽 전환 사유
    """

    topic_id: int
    topic: str
    key_points: list[str]
    gaps: list[str]
    depth_reached: str
    technologies_mentioned: list[str]
    transition_reason: str


class QuestionState(TypedDict, total=False):
    """질문 생성 그래프 상태

    Attributes:
        # 요청 정보 (입력)
        user_id: 사용자 ID
        session_id: 면접 세션 ID
        question_type: 질문 유형 (CS/SYSTEM_DESIGN/PORTFOLIO)
        category: 사용자가 고른 첫 질문 카테고리 (CS, SYSTEM DESIGN일 경우)
        interview_history: 면접 Q&A 히스토리
        portfolio: 포트폴리오 정보 (PORTFOLIO 타입일 경우)

        # 세션 설정
        max_topics: 최대 토픽 수
        max_follow_ups_per_topic: 토픽당 최대 꼬리질문 수

        # 계산된 상태
        current_topic_id: 현재 토픽 ID
        current_topic_count: 진행된 토픽 수
        current_follow_up_count: 현재 토픽의 꼬리질문 수

        # 라우터 결정
        route_decision: 라우터 노드의 분기 결정
        route_reasoning: 분기 결정 이유
        follow_up_direction: 꼬리질문 방향 (follow_up 분기 시)
        direction_detail: 꼬리질문 방향의 구체적 설명 (follow_up 분기 시)
        router_analysis: 라우터의 답변 분석 결과 (카테고리별 스키마 dict)

        # [NEW] 토픽 요약
        topic_summaries: 완료된 토픽별 요약 리스트
        topic_transition_reason: 토픽 전환 사유 (router → summarizer 전달용)

        # 출력
        generated_question: 생성된 질문
        error: 에러 메시지 (있을 경우)
    """

    # ============================================================
    # 요청 정보 (입력)
    # ============================================================
    user_id: int
    session_id: str
    portfolio_id : int | None
    question_type: QuestionType
    category: QuestionCategory | None
    interview_history: list[QATurn]
    portfolio_summary: str | None

    # ============================================================
    # 세션 설정
    # ============================================================
    max_topics: int
    max_follow_ups_per_topic: int

    # ============================================================
    # 계산된 상태 (노드에서 업데이트)
    # ============================================================
    current_topic_id: int
    current_topic_count: int
    current_follow_up_count: int

    # ============================================================
    # 라우터 결정
    # ============================================================
    route_decision: RouteDecision
    route_reasoning: str
    follow_up_direction: str | None
    direction_detail: str | None
    router_analysis: dict[str, Any] | None

    # ============================================================
    # 토픽 요약
    # ============================================================
    topic_summaries: list[TopicSummary]
    topic_transition_reason: str | None

    # ============================================================
    # 출력
    # ============================================================
    generated_question: GeneratedQuestion
    error: str | None


def create_initial_state(
    user_id: int,
    session_id: str,
    question_type: QuestionType,
    portfolio_id: int | None = None,
    category: QuestionCategory | None = None,
    interview_history: list[QATurn] | None = None,
    portfolio_summary: str | None = None,
    max_topics: int = 3,
    max_follow_ups_per_topic: int = 5,
) -> QuestionState:
    """초기 상태 생성

    interview_history를 분석하여 현재 토픽 정보를 계산합니다.
    """
    history = interview_history or []

    # 토픽 정보 계산
    if not history:
        current_topic_id = 0
        current_topic_count = 0
        current_follow_up_count = 0
    else:
        current_topic_id = max(turn.topic_id for turn in history)
        current_topic_count = len(set(turn.topic_id for turn in history))
        current_topic_turns = [t for t in history if t.topic_id == current_topic_id]
        current_follow_up_count = sum(
            1 for t in current_topic_turns if t.turn_type == "follow_up"
        )

    return QuestionState(
        # 요청 정보
        user_id=user_id,
        session_id=session_id,
        portfolio_id=portfolio_id,
        question_type=question_type,
        category=category,
        interview_history=history,
        portfolio_summary=portfolio_summary,
        # 세션 설정
        max_topics=max_topics,
        max_follow_ups_per_topic=max_follow_ups_per_topic,
        # 계산된 상태
        current_topic_id=current_topic_id,
        current_topic_count=current_topic_count,
        current_follow_up_count=current_follow_up_count,
        # 라우터 결정 (초기값)
        follow_up_direction=None,
        direction_detail=None,
        router_analysis=None,
        # [NEW] 토픽 요약 (초기값)
        topic_summaries=[],
        topic_transition_reason=None,
        # 출력
        error=None,
    )