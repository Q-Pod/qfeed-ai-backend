# services/question_generate_service.py

"""질문 생성 서비스"""

from langfuse import observe

from schemas.question import (
    QuestionGenerateRequest,
    QuestionGenerateResponse,
)
from schemas.feedback import BadCaseResult
from exceptions.exceptions import AppException
from exceptions.error_messages import ErrorMessage
from services.bad_case_checker import get_bad_case_checker
from services.session_end_detector import is_user_requested_session_end
from graphs.question.state import create_initial_state
from graphs.question.question_graph import run_question_pipeline

from core.logging import get_logger
from core.tracing import update_trace, update_observation

logger = get_logger(__name__)


class QuestionGenerateService:
    """질문 생성 서비스"""

    @observe(name="generate_question_service")
    async def generate_question(
        self, 
        request: QuestionGenerateRequest,
    ) -> QuestionGenerateResponse:
        """질문 생성 메인 로직"""

        update_trace(
            user_id=str(request.user_id),
            session_id=request.session_id,
            metadata={
                "question_type": request.question_type,
                "initial_category": request.initial_category.value if request.initial_category else None,
            },
        )

        # Step 0: 사용자 면접 종료 요청 감지 → 즉시 END_SESSION 응답 (badcase/라우터 생략)
        if request.interview_history:
            last_turn = request.interview_history[-1]
            should_end, confidence, reason = await is_user_requested_session_end(
                last_question=last_turn.question,
                answer_text=last_turn.answer_text,
            )
            if should_end:
                logger.info(
                    f"User requested session end | session_id={request.session_id} | "
                    f"confidence={confidence:.2f} | reason={reason} | "
                    f"answer_text_preview={last_turn.answer_text[:50]!r}..."
                )
                return QuestionGenerateResponse.from_user_requested_end(
                    user_id=request.user_id,
                    session_id=request.session_id,
                    interview_history=request.interview_history,
                )

        # Step 1: Bad case 체크 (히스토리가 있을 때만)
        if request.interview_history:
            bad_case_result = await self._check_bad_case(request)
            if bad_case_result:
                logger.info(f"Bad case detected | type={bad_case_result.bad_case_feedback.type}")
                return QuestionGenerateResponse.from_bad_case(
                    user_id=request.user_id,
                    session_id=request.session_id,
                    bad_case_result=bad_case_result,
                    interview_history=request.interview_history,
                )

        # Step 2: 그래프 실행
        result = await self._run_pipeline(request)

        # Step 3: 응답 변환
        logger.debug(f"question generate service completed | route={result.get('route_decision')}")
        
        return QuestionGenerateResponse.from_graph_result(result)

    @observe(name="check_bad_case", as_type="tool")
    async def _check_bad_case(
        self, 
        request: QuestionGenerateRequest,
    ) -> BadCaseResult | None:
        """Bad case 체크, 해당 시 응답 반환"""
        
        if not request.interview_history:
            update_observation(metadata={"skipped": True, "reason": "no_history"})
            return None

        try:
            checker = get_bad_case_checker()
            last_turn = request.interview_history[-1]
            result = await checker.check(last_turn.question, last_turn.answer_text)
            update_observation(output={"is_bad_case": result.is_bad_case})
            
            if result.is_bad_case:
                return result
            return None
            
        except Exception as e:
            logger.error(f"Bad case check failed | {type(e).__name__}: {e}")
            raise AppException(ErrorMessage.BAD_CASE_CHECK_FAILED) from e

    async def _run_pipeline(self, request: QuestionGenerateRequest) -> dict:
        """그래프 파이프라인 실행"""
        logger.info("question generate graph start")

        initial_state = create_initial_state(
            user_id=request.user_id,
            session_id=request.session_id,
            question_type=request.question_type,
            category=request.initial_category,
            interview_history=request.interview_history,
        )
        
        result = await run_question_pipeline(initial_state)
        
        logger.info("question generate graph completed")
        return result