"""
피드백 생성 그래프 State 정의

흐름: bad_case_filter → quick_eval → rubric_evaluator → feedback_generator

- 필수 필드: 그래프 시작 시 라우터에서 반드시 주입
- NotRequired 필드: 각 노드가 실행되면서 채움
"""
# from __future__ import annotations

from typing import TypedDict

from schemas.feedback import(
    InterviewType,
    QuestionType,
    QuestionCategory,
    QATurn,
    BadCaseResult,
    KeywordCheckResult,
    RubricEvaluationResult,
    TopicFeedback,
    OverallFeedback
)

class FeedbackGraphState(TypedDict):
    """
    LangGraph feedback 파이프라인 공유 상태 정의
    """

    #input
    user_id : int
    question_id: int
    session_id: str | None
    interview_type: InterviewType
    question_type: QuestionType
    category: QuestionCategory | None

    # 면접 히스토리
    interview_history: list[QATurn]

    keywords: list[str] | None
    # callback_url: str

    # BadCaseChecker 노드 출력
    bad_case_result: BadCaseResult | None

    # KeywordChecker 노드 출력
    keyword_result: KeywordCheckResult | None

    #RubricEvaluator 노드 출력
    rubric_result : RubricEvaluationResult | None

    #FeedbackGenerator 노드 출력
    topics_feedback : TopicFeedback | None

    overall_feedback : OverallFeedback | None

    # 현재 처리 단계(디버깅용)
    current_step: str

    # 에러 발생 시 정보
    error:str | None

    # Callback 전송 완료 여부
    callback_sent: bool


def create_initial_state(
    user_id: int,
    question_id: int,
    
    interview_history: list[QATurn],
    interview_type: InterviewType,
    question_type: QuestionType,
    session_id: str | None = None,
    category: QuestionCategory | None = None,
    keywords: list[str] | None = None,
) -> FeedbackGraphState:
    """FeedbackRequest로부터 초기 State 생성"""
    return FeedbackGraphState(
        # Input
        user_id=user_id,
        question_id=question_id,
        session_id=session_id,
        interview_type=interview_type,
        question_type=question_type,
        category=category,
        interview_history=interview_history,
        keywords=keywords,
        
        # Processing Results (초기값 None)
        bad_case_result=None,
        keyword_result=None,
        rubric_result=None,
        topics_feedback=None,
        overall_feedback=None,
        
        # Control Flow
        current_step="initialized",
        error=None,
        callback_sent=False,
    )

def get_all_answers_text(state: FeedbackGraphState) -> str:
    """
    전체 답변을 하나의 텍스트로 결합 (루브릭 평가용)
    """
    return "\n\n".join(
        f"Q: {turn.question}\nA: {turn.answer_text}"
        for turn in state["interview_history"]
    )

def get_topic_ids(state: FeedbackGraphState) -> list[int]:
    """
    고유한 토픽 ID 목록 추출
    """
    return list(set(turn.topic_id for turn in state["interview_history"]))


def get_turns_by_topic(state: FeedbackGraphState, topic_id: int) -> list[QATurn]:
    """
    특정 토픽의 Q&A 턴들만 추출
    """
    return [
        turn for turn in state["interview_history"]
        if turn.topic_id == topic_id
    ]