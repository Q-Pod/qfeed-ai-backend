from pydantic import BaseModel, Field
from enum import Enum
from typing import Literal, Union
from schemas.common import BaseResponse

class InterviewType(str, Enum):
    PRACTICE_INTERVIEW = "PRACTICE_INTERVIEW" # 연습모드
    REAL_INTERVIEW = "REAL_INTERVIEW" # 실전모드

class QuestionType(str, Enum):
    CS = "CS"
    SYSTEM_DESIGN = "SYSTEM_DESIGN"
    PORTFOLIO = "PORTFOLIO"

class CSCategory(str, Enum):
    OS = "OS"
    NETWORK = "NETWORK"
    DB = "DB"
    DATA_STRUCTURE_ALGORITHM = "DATA_STRUCTURE_ALGORITHM"
    COMPUTER_ARCHITECTURE = "COMPUTER_ARCHITECTURE"


class SystemDesignCategory(str, Enum):
    SOCIAL = "SOCIAL"
    MESSAGING = "MESSAGING"
    NOTIFICATION = "NOTIFICATION"
    SEARCH = "SEARCH"
    MEDIA = "MEDIA"
    STORAGE = "STORAGE"
    PLATFORM = "PLATFORM"
    TRANSACTION = "TRANSACTION"


# Union 타입 (필요한 곳에서 사용)
QuestionCategory = Union[CSCategory, SystemDesignCategory]

# 헬퍼 함수
def get_category_enum(question_type: QuestionType) -> type[CSCategory] | type[SystemDesignCategory] | None:
    """QuestionType에 해당하는 Category Enum 클래스 반환"""
    mapping = {
        QuestionType.CS: CSCategory,
        QuestionType.SYSTEM_DESIGN: SystemDesignCategory,
        QuestionType.PORTFOLIO: None,
    }
    return mapping.get(question_type)


def get_valid_categories(question_type: QuestionType) -> list[str]:
    """QuestionType에 유효한 카테고리 값 목록 반환"""
    category_enum = get_category_enum(question_type)
    if category_enum is None:
        return []
    return [c.value for c in category_enum]

def validate_category(question_type: QuestionType, category: QuestionCategory | None) -> bool:
    """카테고리가 QuestionType에 맞는지 검증"""
    category_enum = get_category_enum(question_type)
    
    # PORTFOLIO는 카테고리 없어야 함
    if category_enum is None:
        return category is None
    
    # CS/SYSTEM_DESIGN은 해당 Enum 타입이어야 함
    return isinstance(category, category_enum)

def parse_category(question_type: QuestionType, category_value: str) -> QuestionCategory | None:
    """문자열을 적절한 Category Enum으로 파싱"""
    if not category_value:
        return None
        
    category_enum = get_category_enum(question_type)
    if category_enum is None:
        return None
    
    try:
        return category_enum(category_value)
    except ValueError:
        valid = get_valid_categories(question_type)
        raise ValueError(
            f"Invalid category '{category_value}' for {question_type.value}. "
            f"Valid options: {valid}"
        )


## BAD CASE 관련 Schema

class BadCaseType(str, Enum):
    '''Bad Case 유형'''
    INSUFFICIENT = "INSUFFICIENT" # 너무 짧거나 의미 없는 답변, 반복적인 패턴 감지
    INAPPROPRIATE = "INAPPROPRIATE" # 비속어 감지
    OFF_TOPIC = "OFF_TOPIC" # 질문과 무관한 답변 - 코사인 유사도로 감지      

BAD_CASE_MESSAGES = {
    BadCaseType.INSUFFICIENT: {
        "message": "답변의 내용이 부족하거나 반복적입니다.",
        "guidance": "답변이 너무 짧거나 의미 없는 패턴이 반복되고 있습니다."
    },
    BadCaseType.INAPPROPRIATE: {
        "message": "부적절한 표현이 감지되었습니다.",
        "guidance": "답변 내용 중 비속어나 정중하지 못한 표현이 포함되어 있습니다."
    },
    BadCaseType.OFF_TOPIC: {
        "message": "질문과 연관성이 낮은 답변입니다.",
        "guidance": "입력하신 답변이 질문의 의도와 다소 벗어난 것 같습니다."
    }
}

class BadCaseFeedback(BaseModel):
    """Bad Case 전용 피드백 - rule based"""
    type: BadCaseType = Field(..., description="Bad case 유형")
    message: str = Field(..., description="Bad case 메시지")
    guidance: str = Field(..., description="재답변 가이드")
    
    @classmethod
    def from_type(cls, bad_case_type: BadCaseType) -> "BadCaseFeedback":
        """Bad case 타입으로부터 피드백 생성"""
        info = BAD_CASE_MESSAGES[bad_case_type]
        return cls(
            type=bad_case_type,
            message=info["message"],
            guidance=info["guidance"]
        )
    
class BadCaseResult(BaseModel):
    '''bad case checker 출력 스키마'''
    is_bad_case : bool = Field(None, description="Bad case 유형 (해당시)")
    bad_case_feedback: BadCaseFeedback | None = Field(None, description="Bad case 피드백 (해당시)")

    @classmethod
    def normal(cls) -> "BadCaseResult":
        """정상 답변"""
        return cls(is_bad_case=False)

    @classmethod
    def bad(cls, bad_type: BadCaseType) -> "BadCaseResult":
        """Bad case 답변"""
        return cls(
            is_bad_case=True,
            bad_case_type=bad_type,
            bad_case_feedback=BadCaseFeedback.from_type(bad_type)
        )

   
class KeywordCheckResult(BaseModel):
    """KeywordChecker 노드 출력 - 유사도 기반 키워드 매칭"""
    covered_keywords: list[str] = Field(default_factory=list, description="포함된 키워드")
    missing_keywords: list[str] = Field(default_factory=list, description="누락된 키워드")
    coverage_ratio: float = Field(..., ge=0.0, le=1.0, description="키워드 커버리지 비율")


class RubricScore(BaseModel):
    '''개별 루브릭 항목 점수'''
    name : str
    score: int = Field(..., description="루브릭 점수 (1-5)")

class RubricEvaluationResult(BaseModel):
    """Rubric Evaluator 내부 출력 - LLM structured output"""
    accuracy: int = Field(..., ge=1, le=5, description="정확도")
    logic: int = Field(..., ge=1, le=5, description="논리력")
    specificity: int = Field(..., ge=1, le=5, description="구체성")
    completeness: int = Field(..., ge=1, le=5, description="완성도")
    delivery: int = Field(..., ge=1, le=5, description="전달력")
    
    def to_metrics_list(self) -> list[RubricScore]:
        """API 응답용 metrics 리스트로 변환"""
        return [
            RubricScore(name="정확도", score=self.accuracy),
            RubricScore(name="논리력", score=self.logic),
            RubricScore(name="구체성", score=self.specificity),
            RubricScore(name="완성도", score=self.completeness),
            RubricScore(name="전달력", score=self.delivery),
        ]

class QATurn(BaseModel):
    question: str = Field(..., description="질문 텍스트")
    category: QuestionCategory = Field(..., description="문제 카테고리")
    answer_text: str = Field(..., description="답변 텍스트")
    turn_type: Literal["new_topic", "follow_up"] = Field(..., description="질문 유형")
    turn_order: int = Field(..., description="전체 세션 내 순서 (0부터)")
    topic_id: int = Field(..., description="토픽 그룹 ID")

class FeedbackRequest(BaseModel):
    user_id: int = Field(..., description="사용자 ID")
    question_id: int | None = Field(None, description="문제 ID")
    session_id: str | None = Field(None, description="면접 세션 ID")
    interview_type : InterviewType = Field(
        default=InterviewType.PRACTICE_INTERVIEW,
        description="면접 유형"
    )
    question_type: QuestionType = Field(
        default=QuestionType.CS,
        description="질문 유형"
    )
    interview_history: list[QATurn]
    keywords: list[str] | None = Field(None, description="필수 키워드 목록")

class TopicFeedback(BaseModel):
    """개별 토픽 피드백"""
    topic_id: int = Field(..., description="토픽 그룹 ID")
    main_question: str = Field(..., description="메인 질문 텍스트")
    strengths: str = Field(..., description="해당 토픽에서 잘한 점 (150-800자)")
    improvements: str = Field(..., description="해당 토픽에서 개선할 점 (150-800자)")


class OverallFeedback(BaseModel):
    """종합 피드백 : 연습모드는 종합 피드백만 Required"""
    strengths: str = Field(..., description="전체적으로 잘한 점 (300-800자)")
    improvements: str = Field(..., description="전체적으로 개선할 점 (300-800자)")

class RealModeFeedback(BaseModel):
    """실전모드: 토픽별 + 종합 모두 Required"""
    topics_feedback: list[TopicFeedback]
    overall_feedback: OverallFeedback
     
class FeedbackData(BaseModel):
    """피드백 응답 데이터"""
    user_id: int 
    question_id: int | None = None
    session_id: str | None = None
    
    # Bad case 결과
    bad_case_feedback: BadCaseFeedback | None = None
    
    # 정상 평가 결과
    metrics: list[RubricScore] | None = None  # 종합 루브릭
    keyword_result: KeywordCheckResult | None = None
    topics_feedback: list[TopicFeedback] | None = None  # 토픽별 피드백
    overall_feedback: OverallFeedback | None = None  # 종합 피드백


class FeedbackResponse(BaseResponse[FeedbackData]):
    """피드백 API 응답"""
    
    @classmethod
    def from_bad_case(
        cls,
        user_id: int,
        question_id: int,
        bad_case_result: BadCaseResult,
        session_id: str | None = None,
    ) -> "FeedbackResponse":
        return cls(
            message="bad_case_detected",
            data=FeedbackData(
                user_id=user_id,
                question_id=question_id,
                session_id=session_id,
                bad_case_feedback=bad_case_result.bad_case_feedback,
            ),
        )

    @classmethod
    def from_evaluation(
        cls,
        user_id: int,
        rubric_result: RubricEvaluationResult,
        overall_feedback: OverallFeedback,
        question_id: int | None = None,
        keyword_result: KeywordCheckResult | None = None,
        topics_feedback: list[TopicFeedback] | None = None,
        session_id: str | None = None,
    ) -> "FeedbackResponse":
        return cls(
            message="generate_feedback_success",
            data=FeedbackData(
                user_id=user_id,
                question_id=question_id,
                session_id=session_id,
                metrics=rubric_result.to_metrics_list(),
                keyword_result=keyword_result,
                topics_feedback = topics_feedback,
                overall_feedback = overall_feedback
            ),
        )

# V2 비동기 처리 도입 시 사용

# class FeedbackAcceptedResponse(BaseResponse):
#     """V2 즉시 응답 - 비동기 처리 시작 알림

#     /ai/interview/feedback/request 호출 시 즉시 반환
#     """
#     message: Literal["feedback_generate"] = "feedback_generate"
#     data: None = None

# Callback Payload
# class FeedbackCallbackPayload(BaseModel):
#     """
#     V2 Callback 페이로드 - AI 서버 → Java 백엔드
    
#     POST /ai/interview/feedback/generate 로 전송
    
#     - Bad case인 경우: bad_case_feedback만 포함, metrics/feedback은 None
#     - 정상인 경우: metrics, feedback 포함, bad_case_feedback은 None
#     """
    

#     @classmethod
#     def from_bad_case(
#         cls,
#         user_id: int,
#         question_id: int,
#         bad_case_result: BadCaseResult
#     ) -> "FeedbackCallbackPayload":
#         """Bad case 결과로부터 Callback 페이로드 생성"""
#         return cls(
#             user_id=user_id,
#             question_id=question_id,
#             bad_case_feedback=bad_case_result.bad_case_feedback
#         )

#     @classmethod
#     def from_evaluation(
#         cls,
#         user_id: int,
#         question_id: int,
#         rubric_result: RubricEvaluationResult,
#         keyword_result: KeywordCheckResult,
#         feedback: list[FeedbackContent]
#     ) -> "FeedbackCallbackPayload":
#         """정상 평가 결과로부터 Callback 페이로드 생성"""
#         return cls(
#             user_id=user_id,
#             question_id=question_id,
#             metrics=rubric_result.to_metrics_list(),
#             keyword_result=keyword_result,
#             feedback=feedback
#         )


