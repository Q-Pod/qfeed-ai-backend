# services/question_generate_service.py

"""질문 생성 서비스"""

from langfuse import observe

from schemas.feedback import QuestionType
from schemas.question import (
    QuestionGenerateRequest,
    QuestionGenerateResponse,
)
from exceptions.exceptions import AppException
from exceptions.error_messages import ErrorMessage
from services.bad_case_checker import get_bad_case_checker
from services.session_end_detector import is_user_requested_session_end
from graphs.question.state import create_initial_state
from graphs.question.question_graph import run_question_pipeline
from services.qpool_selector import QuestionPoolSelector
from repositories.pf_repo import PortfolioRepository
from repositories.interview_turn_analysis_repo import InterviewTurnAnalysisRepository
from services.turn_analysis_builder import TurnAnalysisBuilder
from services.topic_summary_builder import TopicSummaryBuilder
from repositories.session_topic_summary_repo import (
    SessionTopicSummaryRepository,
)

from core.logging import get_logger
from core.tracing import update_trace, update_observation

logger = get_logger(__name__)


class QuestionGenerateService:
    """질문 생성 서비스"""

    def __init__(self):
        self._portfolio_repo = PortfolioRepository()
        self._qpool_selector = QuestionPoolSelector(self._portfolio_repo)
        self._turn_analysis_repo = InterviewTurnAnalysisRepository()
        self._turn_analysis_builder = TurnAnalysisBuilder()
        self._topic_summary_builder = TopicSummaryBuilder()
        self._topic_summary_repo = SessionTopicSummaryRepository()

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
                "history_length": len(request.interview_history)
            },
        )
        # interview history가 비어있다면 -> 포토폴리오의 경우 질문 풀에서 꺼내서 보내줘야됨
        if request.question_type == QuestionType.PORTFOLIO and not request.interview_history:
            return await self._select_initial_portfolio_question(request)
        
        # Interview_history가 잇다면
        # Step 0: 사용자 면접 종료 요청 감지
        end_response = await self._detect_session_end(request)
        if end_response:
            return end_response
        
        # Step 1: Bad case 체크
        bad_case_response = await self._handle_bad_case(request)
        if bad_case_response:
            return bad_case_response
        
        # Step 2: 파이프라인 실행
        result = await self._run_pipeline(request)

        # step 3 : graph 결과 기반 턴 분석 + topic summary 저장
        await self._save_analysis_artifacts(request, result)

        logger.debug(
            f"question generate service completed | "
            f"route={result.get('route_decision')} | "
            f"question_type={request.question_type.value}"
        )

        return QuestionGenerateResponse.from_graph_result(result)
    
    # ================================================================
    # 포트폴리오 첫 질문 선택
    # ================================================================
 
    async def _select_initial_portfolio_question(
        self,
        request: QuestionGenerateRequest,
    ) -> QuestionGenerateResponse:
        """포트폴리오 첫 질문 — 질문 풀에서 우선순위 기반 선택"""
 
        selected = await self._qpool_selector.select_initial_question(
            user_id=request.user_id,
            portfolio_id=request.portfolio_id,
        )
 
        if not selected:
            logger.error(
                "Question pool empty | user_id=%s | portfolio_id=%s",
                request.user_id,
                request.portfolio_id,
            )
            raise AppException(ErrorMessage.QUESTION_POOL_EMPTY)
 
        return QuestionGenerateResponse.from_question_pool(
            user_id=request.user_id,
            session_id=request.session_id,
            selected_question=selected,
        )
    
    # ================================================================
    # 분석 결과 / 토픽 요약 저장
    # ================================================================

    async def _save_analysis_artifacts(
        self,
        request: QuestionGenerateRequest,
        result: dict,
    ) -> None:
        if not request.interview_history:
            return

        try:
            # 1) turn analysis 저장 (항상)
            turn_doc = self._turn_analysis_builder.build(request, result)
            await self._turn_analysis_repo.save_turn_analysis(
                turn_doc.model_dump()
            )
            logger.info(
                "turn analysis saved | session_id=%s | turn_order=%s",
                request.session_id,
                turn_doc.turn_order,
            )

            # 2) topic summary 저장 (new_topic일 때만)
            topic_doc = self._topic_summary_builder.build_if_needed(
                request, result
            )
            if topic_doc is not None:
                await self._topic_summary_repo.save_topic_summary(
                    topic_doc.model_dump()
                )
                logger.info(
                    "topic summary saved | session_id=%s | topic_id=%s",
                    request.session_id,
                    topic_doc.topic_id,
                )

        except Exception as e:
            logger.error(
                "analysis artifacts save failed | session_id=%s | %s: %s",
                request.session_id,
                type(e).__name__,
                e,
            )
            raise AppException(ErrorMessage.ANALYSIS_SAVE_FAILED)


    # ================================================================
    # 공통 전처리 - 면접 종료 감지 & Bad case 체크
    # ================================================================

    async def _detect_session_end(
        self,
        request: QuestionGenerateRequest,
    ) -> QuestionGenerateResponse | None:
        """사용자 면접 종료 요청 감지

        답변 내용에서 종료 의도가 감지되면 즉시 END_SESSION 응답을 반환하여
        bad_case_checker와 router를 모두 건너뛴다.
        """
        last_turn = request.interview_history[-1]
        end_result = await is_user_requested_session_end(
        last_question=last_turn.question,
        answer_text=last_turn.answer_text,
    )

        if end_result:
            # 수정 3: 로그 출력 시 end_result 객체의 reasoning 속성 사용
            # (이전 스텝에서 reasoning 문자열 안에 confidence를 포함해 두었으므로 로그에 잘 남습니다)
            logger.info(
                f"User requested session end | "
                f"session_id={request.session_id} | "
                f"reasoning={end_result.reasoning} | "
                f"answer_text_preview={last_turn.answer_text[:50]!r}..."
            )
            return QuestionGenerateResponse.from_user_requested_end(
                user_id=request.user_id,
                session_id=request.session_id,
                interview_history=request.interview_history,
            )

        return None
        

    async def _handle_bad_case( 
            self,
            request: QuestionGenerateRequest
        ) -> QuestionGenerateResponse | None:
        """Bad case 체크 및 응답 생성"""

        try:
            checker = get_bad_case_checker()
            last_turn = request.interview_history[-1]
            result = await checker.check(last_turn.question, last_turn.answer_text)
            update_observation(output={"is_bad_case": result.is_bad_case})

            if result.is_bad_case:
                logger.info(
                    f"Bad case detected | type={result.bad_case_feedback.type}"
                )
                return QuestionGenerateResponse.from_bad_case(
                    user_id=request.user_id,
                    session_id=request.session_id,
                    bad_case_result=result,
                    interview_history=request.interview_history,
                )

            return None
        
        except Exception as e:
            logger.error(f"Bad case check failed | {type(e).__name__}: {e}")
            raise AppException(ErrorMessage.BAD_CASE_CHECK_FAILED) from e


    # ================================================================
    # 파이프라인 실행
    # ================================================================

    async def _run_pipeline(self, request: QuestionGenerateRequest) -> dict:
        """question_type에 따라 적절한 그래프 파이프라인을 실행

        CS:
            - Java 백엔드가 첫 질문을 interview_history에 포함하여 전달.
            - interview_history가 항상 존재하므로 router → 분기 흐름을 탄다.

        PORTFOLIO:
            - 첫 질문부터 AI 서버 질문 풀에서 꺼내옴
            → topic_summarizer → new_topic_generator (풀에서 선택)
            → session_terminator
        """
        logger.info(
            f"question generate graph start | "
            f"question_type={request.question_type.value}"
        )

        initial_state = create_initial_state(
            user_id=request.user_id,
            session_id=request.session_id,
            portfolio_id=request.portfolio_id,
            question_type=request.question_type,
            interview_history=request.interview_history,
        )
 
        result = await run_question_pipeline(initial_state)
 
        logger.info("question generate graph completed")
        return result
    