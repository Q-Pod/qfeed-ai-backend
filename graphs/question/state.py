# graphs/question/state.py

"""질문 생성 그래프 상태 정의"""

from typing_extensions import TypedDict

from schemas.question import (
    QuestionType,
    QuestionCategory,
    RouteDecision,
    Portfolio,
    GeneratedQuestion,
)
from schemas.feedback import QATurn


class QuestionState(TypedDict, total=False):
    """질문 생성 그래프 상태
    
    Attributes:
        # 요청 정보 (입력)
        user_id: 사용자 ID
        session_id: 면접 세션 ID
        question_type: 질문 유형 (CS/SYSTEM_DESIGN/PORTFOLIO)
        first_category: 사용자가 고른 첫 질문 카테고리 (CS, SYSTEM DESIGN일 경우)
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
        
        # 출력
        generated_question: 생성된 질문
        error: 에러 메시지 (있을 경우)
    """
    
    # ============================================================
    # 요청 정보 (입력)
    # ============================================================
    user_id: int
    session_id: str
    question_type: QuestionType
    category: QuestionCategory | None
    interview_history: list[QATurn]
    portfolio: Portfolio | None
    
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
    
    # ============================================================
    # 출력
    # ============================================================
    generated_question: GeneratedQuestion
    error: str | None


def create_initial_state(
    user_id: int,
    session_id: str,
    question_type: QuestionType,
    category: QuestionCategory | None = None,
    interview_history: list[QATurn] | None = None,
    portfolio: Portfolio | None = None,
    max_topics: int = 3,
    max_follow_ups_per_topic: int = 2,
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
        # 현재 토픽 ID: 히스토리에서 가장 큰 topic_id
        current_topic_id = max(turn.topic_id for turn in history)
        
        # 진행된 토픽 수: 유니크한 topic_id 개수
        current_topic_count = len(set(turn.topic_id for turn in history))
        
        # 현재 토픽의 꼬리질문 수
        current_topic_turns = [t for t in history if t.topic_id == current_topic_id]
        current_follow_up_count = sum(
            1 for t in current_topic_turns if t.turn_type == "follow_up"
        )
    
    return QuestionState(
        # 요청 정보
        user_id=user_id,
        session_id=session_id,
        question_type=question_type,
        category=category,
        interview_history=history,
        portfolio=portfolio,
        
        # 세션 설정
        max_topics=max_topics,
        max_follow_ups_per_topic=max_follow_ups_per_topic,
        
        # 계산된 상태
        current_topic_id=current_topic_id,
        current_topic_count=current_topic_count,
        current_follow_up_count=current_follow_up_count,
        
        # 초기값
        error=None,
    )