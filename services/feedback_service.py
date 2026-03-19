# services/feedback_service.py

"""피드백 생성 서비스 v2

연습모드와 실전모드를 분리하여 각각 최적화된 파이프라인을 실행한다.

연습모드:
    bad_case_checker → 병렬(keyword_checker + practice_answer_analyzer)
    → 병렬(rubric_evaluator_llm + feedback_generator_llm)
    - LLM 호출 3회 (analysis, rubric, feedback)
    - feedback는 keyword/analyzer 결과를 프롬프트 근거로 활용
    - 질문 유형별(CS/시스템디자인) 프롬프트 분리

실전모드:
    rubric_scorer(rule-based) → feedback_generator_realmode(LLM)
    - LLM 호출 1회 (feedback만)
    - 질문 유형별(CS/포트폴리오) 루브릭 scorer 분리
    - 질문 생성 파이프라인의 분석 데이터 활용
"""

import asyncio
from uuid import uuid4
from schemas.feedback_v2 import (
    FeedbackRequest,
    FeedbackResponse,
)
from schemas.feedback_v2 import (
    InterviewType,
    QuestionType,
    BadCaseResult,
    QATurn,
    RouterAnalysisTurn,
    PortfolioTopicSummaryData,
    CSTopicSummaryData,
)

from services.rubric_scorer import score_portfolio_rubric, score_cs_rubric
from services.bad_case_checker import get_bad_case_checker
from services.turn_analysis_builder import TurnAnalysisBuilder
from graphs.feedback.state import create_initial_state
from graphs.nodes.rubric_evaluator import rubric_evaluator
from graphs.nodes.keyword_checker import keyword_checker
from graphs.nodes.CS.feedback_generator import feedback_generator
from graphs.nodes.practice_answer_analyzer import practice_answer_analyzer
from graphs.nodes.realmode_feedback_generator import feedback_generator_realmode
from repositories.interview_turn_analysis_repo import InterviewTurnAnalysisRepository
from repositories.session_topic_summary_repo import SessionTopicSummaryRepository

from exceptions.exceptions import AppException
from exceptions.error_messages import ErrorMessage
from core.logging import get_logger
from core.tracing import update_trace, update_observation
from langfuse import observe

logger = get_logger(__name__)

class FeedbackService:
    """피드백 생성 서비스"""

    def __init__(
        self,
        turn_analysis_repo: InterviewTurnAnalysisRepository | None = None,
        topic_summary_repo: SessionTopicSummaryRepository | None = None,
        turn_analysis_builder: TurnAnalysisBuilder | None = None,
        **_kwargs,
    ):
        self._turn_analysis_repo = turn_analysis_repo or InterviewTurnAnalysisRepository()
        self._topic_summary_repo = topic_summary_repo or SessionTopicSummaryRepository()
        self._turn_analysis_builder = turn_analysis_builder or TurnAnalysisBuilder()

    @observe(name="generate_feedback_service")
    async def generate_feedback(self, request: FeedbackRequest) -> FeedbackResponse:
        """피드백 생성 메인 — interview_type으로 분기"""

        if (
            request.interview_type == InterviewType.PRACTICE_INTERVIEW
            and not request.session_id
        ):
            request = request.model_copy(
                update={"session_id": f"practice-{uuid4()}"}
            )

        update_trace(
            user_id=str(request.user_id),
            session_id=request.session_id,
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
        """연습모드: bad_case → 병렬(keyword + analysis) → 병렬(rubric + feedback)"""

        # Step 1: bad case 체크 - bad case로 필터링 되면 bad case 응답
        bad_case_result = await self._check_bad_case(request)
        if bad_case_result:
            logger.info(f"Bad case detected | type={bad_case_result.bad_case_feedback.type}")
            return FeedbackResponse.from_bad_case(
                user_id=request.user_id,
                question_id=request.question_id,
                session_id=None,
                question_type=request.question_type,
                bad_case_result=bad_case_result,
            )
            
        # Step 2: keyword + analysis 병렬 실행
        state = create_initial_state(
            user_id=request.user_id,
            question_id=request.question_id,
            interview_history=request.interview_history,
            interview_type=request.interview_type,
            question_type=request.question_type,
            category=request.category,
            subcategory=request.subcategory,
            keywords=request.keywords,
        )

        keyword_result, analysis_result = await asyncio.gather(
            keyword_checker(state),
            practice_answer_analyzer(state),
        )

        # 1차 결과 병합
        state.update(keyword_result)
        state.update(analysis_result)

        # Step 3: rubric + feedback 병렬 실행
        rubric_result, feedback_result = await asyncio.gather(
            rubric_evaluator(state),
            feedback_generator(state),
        )

        # 2차 결과 병합
        state.update(rubric_result)
        state.update(feedback_result)
        await self._save_practice_turn_analysis(request, state)

        logger.info("Practice mode feedback completed")

        # Step 4: 응답 조립
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

        if not request.session_id:
            raise AppException(ErrorMessage.FEEDBACK_GENERATION_FAILED)

        router_analyses, topic_summaries = await self._load_realmode_artifacts(
            request
        )
        
        # Step 1:question_type에 따라 router_analyses로 rule-based 루브릭 산출
        if request.question_type == QuestionType.PORTFOLIO:
            rubric_scores = score_portfolio_rubric(
                router_analyses=router_analyses,
            )
        elif request.question_type == QuestionType.CS:
            rubric_scores = score_cs_rubric(
                router_analyses=router_analyses,
            )
        else:
            logger.warning(
                f"Unsupported question_type={request.question_type} "
                f"for realmode feedback, falling back to CS"
            )
            rubric_scores = score_cs_rubric(
                router_analyses=router_analyses,
            )
            topic_summaries = []
        
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

    async def _load_realmode_artifacts(
        self,
        request: FeedbackRequest,
    ) -> tuple[
        list[RouterAnalysisTurn],
        list[PortfolioTopicSummaryData] | list[CSTopicSummaryData],
    ]:
        """실전모드 피드백에 필요한 분석/요약 데이터를 DB에서 로드"""

        turn_docs = await self._turn_analysis_repo.list_session_turn_analyses(
            user_id=request.user_id,
            session_id=request.session_id,
            question_type=request.question_type,
        )
        topic_docs = await self._topic_summary_repo.list_session_topic_summaries(
            user_id=request.user_id,
            session_id=request.session_id,
            question_type=request.question_type,
        )

        router_analyses = self._map_turn_docs_to_router_analyses(
            turn_docs=turn_docs,
            question_type=request.question_type,
            interview_history=request.interview_history,
        )
        topic_summaries = self._map_topic_docs_to_summaries(
            topic_docs=topic_docs,
            question_type=request.question_type,
        )

        logger.info(
            "Loaded realmode artifacts | session_id=%s | analyses=%s | summaries=%s",
            request.session_id,
            len(router_analyses),
            len(topic_summaries),
        )

        return router_analyses, topic_summaries

    @staticmethod
    def _map_turn_docs_to_router_analyses(
        *,
        turn_docs: list[dict],
        question_type: QuestionType,
        interview_history: list[QATurn],
    ) -> list[RouterAnalysisTurn]:
        turn_type_by_order = {
            turn.turn_order: turn.turn_type for turn in interview_history
        }
        analyses: list[RouterAnalysisTurn] = []

        for doc in turn_docs:
            analysis = doc.get("analysis") or {}
            follow_up = doc.get("follow_up") or {}

            common_fields = {
                "topic_id": doc["topic_id"],
                "turn_order": doc["turn_order"],
                "turn_type": turn_type_by_order.get(doc["turn_order"], "new_topic"),
                "is_well_structured": analysis.get("is_well_structured"),
                "follow_up_direction": follow_up.get("direction"),
            }

            if question_type == QuestionType.PORTFOLIO:
                analyses.append(
                    RouterAnalysisTurn(
                        **common_fields,
                        completeness_detail=analysis.get("completeness"),
                        has_evidence=analysis.get("has_evidence"),
                        has_tradeoff=analysis.get("has_tradeoff"),
                        has_problem_solving=analysis.get("has_problem_solving"),
                    )
                )
            else:
                analyses.append(
                    RouterAnalysisTurn(
                        **common_fields,
                        correctness_detail=analysis.get("correctness"),
                        has_error=analysis.get("has_error"),
                        completeness_cs_detail=analysis.get("completeness"),
                        has_missing_concepts=analysis.get("has_missing_concepts"),
                        depth_detail=analysis.get("depth"),
                        is_superficial=analysis.get("is_superficial"),
                    )
                )

        return analyses

    @staticmethod
    def _map_topic_docs_to_summaries(
        *,
        topic_docs: list[dict],
        question_type: QuestionType,
    ) -> list[PortfolioTopicSummaryData] | list[CSTopicSummaryData]:
        if question_type == QuestionType.PORTFOLIO:
            return [
                PortfolioTopicSummaryData(
                    topic_id=doc["topic_id"],
                    topic=doc["topic"],
                    key_points=doc.get("key_points", []),
                    gaps=doc.get("gaps", []),
                    depth_reached=doc["depth_reached"],
                    technologies_mentioned=doc.get("technologies_mentioned", []),
                )
                for doc in topic_docs
            ]

        return [
            CSTopicSummaryData(
                topic_id=doc["topic_id"],
                topic=doc["topic"],
                key_points=doc.get("key_points", []),
                gaps=doc.get("gaps", []),
                depth_reached=doc["depth_reached"],
            )
            for doc in topic_docs
        ]
    
    # ============================================================
    # 공통
    # ============================================================

    async def _save_practice_turn_analysis(
        self,
        request: FeedbackRequest,
        state: dict,
    ) -> None:
        """연습모드 answer analysis를 interview_turn_analyses에 저장"""
        router_analyses = state.get("router_analyses") or []
        if not router_analyses:
            logger.info(
                "practice turn analysis save skipped | user_id=%s | question_id=%s",
                request.user_id,
                request.question_id,
            )
            return

        session_id = request.session_id or f"practice-{uuid4()}"

        try:
            turn_doc = self._turn_analysis_builder.build_practice_feedback_analysis(
                request,
                router_analyses[-1],
                session_id=session_id,
                rubric_result=state.get("rubric_result"),
            )
            await self._turn_analysis_repo.save_turn_analysis(
                turn_doc.model_dump()
            )
            logger.info(
                "practice turn analysis saved | session_id=%s | turn_order=%s",
                session_id,
                turn_doc.turn_order,
            )
        except Exception as e:
            logger.error(
                "practice turn analysis save failed | session_id=%s | %s: %s",
                session_id,
                type(e).__name__,
                e,
            )
            raise AppException(ErrorMessage.ANALYSIS_SAVE_FAILED) from e

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
    
