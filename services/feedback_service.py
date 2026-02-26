# services/feedback_service.py
import asyncio
from schemas.feedback import (
    FeedbackRequest, 
    FeedbackResponse, 
    BadCaseResult,
    InterviewType,
)
from exceptions.exceptions import AppException
from exceptions.error_messages import ErrorMessage
from services.bad_case_checker import get_bad_case_checker
from graphs.feedback.state import create_initial_state
from graphs.nodes.rubric_evaluator import rubric_evaluator
from graphs.nodes.keyword_checker import keyword_checker
from graphs.nodes.feedback_generator import feedback_generator
# from graphs.feedback.feedback_graph import run_feedback_pipeline

from core.logging import get_logger
from core.tracing import update_trace, update_observation
from langfuse import observe

logger = get_logger(__name__)

class FeedbackService:
    """피드백 생성 서비스"""

    @observe(name="generate_feedback_service")
    async def generate_feedback(self, request: FeedbackRequest) -> FeedbackResponse:
        """피드백 생성 메인 로직"""

        update_trace(
            user_id=str(request.user_id),
            session_id=request.session_id or f"practice-{request.user_id}-{request.question_id}",
            metadata={
                "interview_type": request.interview_type,
                "question_type": request.question_type,
            }
        )

        # Step 1: bad case 체크(연습모드에서만) - bad case로 필터링 되면 bad case 응답 
        bad_case_result = self._check_bad_case(request)
        if bad_case_result:
            logger.info(f"Bad case detected | type={bad_case_result.bad_case_feedback.type}")
            return FeedbackResponse.from_bad_case(
                user_id=request.user_id,
                question_id=request.question_id,
                session_id=request.session_id,
                bad_case_result=bad_case_result,
            )

        result = await self._run_pipeline(request)

        # Step 3: 응답 변환 - 정상 피드백 응답
        logger.info(f"Feedback graph pipeline completed | steps={result.get('current_step')}")
        
        return FeedbackResponse.from_evaluation(
            user_id=result["user_id"],
            question_id=result["question_id"],
            session_id=result["session_id"],
            rubric_result=result["rubric_result"],
            keyword_result=result["keyword_result"],
            topics_feedback=result["topics_feedback"],
            overall_feedback=result["overall_feedback"]
        )
    
    @observe(name="check bad case", as_type="tool")
    def _check_bad_case(self, request: FeedbackRequest) -> BadCaseResult | None:
        """Bad case 체크, 해당 시 응답 반환"""
        # 연습모드가 아니면 스킵
        if request.interview_type != InterviewType.PRACTICE_INTERVIEW:
            update_observation(metadata={"skipped": True, "interview_type": request.interview_type})
            return None

        try:
            checker = get_bad_case_checker()
            last_turn = request.interview_history[0]
            result = checker.check(last_turn.question, last_turn.answer_text)
            update_observation(output={"is_bad_case": result.is_bad_case})
            
            return result if result.is_bad_case else None
            
        except Exception as e:
            logger.error(f"Bad case check failed | {type(e).__name__}: {e}")
            raise AppException(ErrorMessage.BAD_CASE_CHECK_FAILED) from e
    
    async def _run_pipeline(self, request: FeedbackRequest) -> dict:
        """그래프 파이프라인 실행"""
        logger.info("feedback pipeline start")

        state = create_initial_state(
            user_id=request.user_id,
            question_id=request.question_id,
            interview_history=request.interview_history,
            interview_type=request.interview_type,
            question_type=request.question_type,
            session_id=request.session_id,
            keywords=request.keywords,
        )
        # Step 1: 병렬로 처리
        keyword_result, rubric_result, feedback_result = await asyncio.gather(
            keyword_checker(state),
            rubric_evaluator(state),
            feedback_generator(state)
        )
        
        # 결과 병합
        state.update(keyword_result)
        state.update(rubric_result)
        state.update(feedback_result)

        logger.info("feedback pipeline completed")
        return state
    
