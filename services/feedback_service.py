# services/feedback_service.py

"""피드백 생성 서비스 v2

연습모드와 실전모드를 분리하여 각각 최적화된 파이프라인을 실행한다.

연습모드:
    bad_case_checker → 병렬(keyword_checker + rubric_evaluator_llm + feedback_generator_llm)
    - LLM 호출 2회 (rubric + feedback, 병렬)
    - 질문 유형별(CS/시스템디자인) 프롬프트 분리

실전모드:
    rubric_scorer(rule-based) → feedback_generator_realmode(LLM)
    - LLM 호출 1회 (feedback만)
    - 질문 유형별(CS/포트폴리오) 루브릭 scorer 분리
    - 질문 생성 파이프라인의 분석 데이터 활용
"""

import asyncio
from schemas.feedback_v2 import (
    FeedbackRequest,
    FeedbackResponse,
)
from schemas.feedback import (
    InterviewType,
    QuestionType,
    BadCaseResult,
)

from services.rubric_scorer import score_portfolio_rubric, score_cs_rubric
from services.bad_case_checker import get_bad_case_checker
from graphs.feedback.state import create_initial_state
from graphs.nodes.rubric_evaluator import rubric_evaluator
from graphs.nodes.keyword_checker import keyword_checker
from graphs.nodes.CS.feedback_generator import feedback_generator
from graphs.nodes.practice_answer_analyzer import practice_answer_analyzer
from graphs.nodes.realmode_feedback_generator import feedback_generator_realmode

from exceptions.exceptions import AppException
from exceptions.error_messages import ErrorMessage
from core.logging import get_logger
from core.tracing import update_trace, update_observation
from langfuse import observe

logger = get_logger(__name__)

class FeedbackService:
    """피드백 생성 서비스"""

    @observe(name="generate_feedback_service")
    async def generate_feedback(self, request: FeedbackRequest) -> FeedbackResponse:
        """피드백 생성 메인 — interview_type으로 분기"""

        update_trace(
            user_id=str(request.user_id),
            session_id=request.session_id or f"practice-{request.user_id}-{request.question_id}",
            metadata={
                "interview_type": request.interview_type.value,
                "question_type": request.question_type.value,
            },
        )

        if request.interview_type == InterviewType.PRACTICE_INTERVIEW:
            return await self._practice_feedback(request)
        else:
            return await self._realmode_feedback(request)
        

    # ============================================================
    # 연습모드
    # ============================================================

    async def _practice_feedback(self, request: FeedbackRequest) -> FeedbackResponse:
        """연습모드: bad_case → 병렬(keyword + rubric_llm + feedback_llm)"""

        # Step 1: bad case 체크 - bad case로 필터링 되면 bad case 응답
        bad_case_result = await self._check_bad_case(request)
        if bad_case_result:
            logger.info(f"Bad case detected | type={bad_case_result.bad_case_feedback.type}")
            return FeedbackResponse.from_bad_case(
                user_id=request.user_id,
                question_id=request.question_id,
                session_id=request.session_id,
                bad_case_result=bad_case_result,
            )
            
        # Step 2: 병렬 파이프라인 실행
        state = create_initial_state(
            user_id=request.user_id,
            question_id=request.question_id,
            interview_history=request.interview_history,
            interview_type=request.interview_type,
            question_type=request.question_type,
            category=request.category,
            keywords=request.keywords,
        )

        (
            keyword_result,
            rubric_result,
            feedback_result,
            analysis_result,
        ) = await asyncio.gather(
            keyword_checker(state),
            rubric_evaluator(state),
            feedback_generator(state),
            practice_answer_analyzer(state),
        )

        # 결과 병합
        state.update(keyword_result)
        state.update(rubric_result)
        state.update(feedback_result)
        state.update(analysis_result)

        logger.info("Practice mode feedback completed")

        # Step 3: 응답 조립
        return FeedbackResponse.from_practice_evaluation(
            user_id=request.user_id,
            question_id=request.question_id,
            question_type=request.question_type,
            rubric_scores=state["rubric_result"],
            keyword_result=state.get("keyword_result"),
            overall_feedback=state["overall_feedback"],
        )
    
    async def _realmode_feedback(self, request: FeedbackRequest) -> FeedbackResponse:
        """실전모드: rule-based rubric → feedback_llm"""

        router_analyses = request.router_analyses or []
        
        # Step 1:question_type에 따라 router_analyses로 rule-based 루브릭 산출
        if request.question_type == QuestionType.PORTFOLIO:
            rubric_scores = score_portfolio_rubric(
                router_analyses=router_analyses,
            )
            topic_summaries = request.portfolio_topic_summaries
        elif request.question_type == QuestionType.CS:
            rubric_scores = score_cs_rubric(
                router_analyses=router_analyses,
            )
            topic_summaries = request.cs_topic_summaries
        else:
            logger.warning(
                f"Unsupported question_type={request.question_type} "
                f"for realmode feedback, falling back to CS"
            )
            rubric_scores = score_cs_rubric(
                router_analyses=router_analyses,
            )
        
        logger.info(
            f"Rubric scored (rule-based) | "
            f"question_type={request.question_type.value} | "
            f"scores={rubric_scores}"
        )

        # Step 2: feedback_generator 실행 (LLM 1회)
        feedback_result = await feedback_generator_realmode(
            interview_history=request.interview_history,
            question_type=request.question_type,
            rubric_scores=rubric_scores,
            router_analyses=router_analyses,
            topic_summaries=topic_summaries,
        )

        logger.info("Realmode feedback completed")

        # Step 3: 응답 조립
        return FeedbackResponse.from_realmode_evaluation(
            user_id=request.user_id,
            session_id=request.session_id,
            question_type=request.question_type,
            rubric_scores=rubric_scores,
            topics_feedback=feedback_result["topics_feedback"],
            overall_feedback=feedback_result["overall_feedback"],
        )
    
    # ============================================================
    # 공통
    # ============================================================

    @observe(name="check bad case", as_type="tool")
    async def _check_bad_case(self, request: FeedbackRequest) -> BadCaseResult | None:
        """Bad case 체크, 해당 시 응답 반환"""
        # 연습모드가 아니면 스킵
        if request.interview_type != InterviewType.PRACTICE_INTERVIEW:
            update_observation(metadata={"skipped": True, "interview_type": request.interview_type})
            return None

        try:
            checker = get_bad_case_checker()
            last_turn = request.interview_history[0]
            result = await checker.check(last_turn.question, last_turn.answer_text)
            update_observation(output={"is_bad_case": result.is_bad_case})
            
            return result if result.is_bad_case else None
            
        except Exception as e:
            logger.error(f"Bad case check failed | {type(e).__name__}: {e}")
            raise AppException(ErrorMessage.BAD_CASE_CHECK_FAILED) from e
    
