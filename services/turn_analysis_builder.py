# services/turn_analysis_builder.py

"""Graph 실행 결과 → InterviewTurnAnalysisDocument 변환기

역할:
  - question_generate_service의 graph result + request를
    MongoDB에 저장할 InterviewTurnAnalysisDocument로 매핑
  - question_type별 분기 처리 (CS / PORTFOLIO)

사용처:
  - question_generate_service._save_turn_analysis()
"""

from __future__ import annotations

from schemas.feedback_v2 import InterviewType, QuestionType
from schemas.feedback_v2 import FeedbackRequest, RouterAnalysisTurn
from schemas.question import QuestionGenerateRequest
from schemas.interview_turn_analyses import (
    InterviewTurnAnalysisDocument,
    CSAnalysisDocument,
    CSRubricDocument,
    PortfolioAnalysisDocument,
    CSFollowUpDocument,
    PortfolioFollowUpDocument,
    NewTopicDocument,
    EndSessionDocument,
)
from core.logging import get_logger

logger = get_logger(__name__)


class TurnAnalysisBuilder:
    """Graph 결과를 InterviewTurnAnalysisDocument로 변환"""

    def build_practice_feedback_analysis(
        self,
        request: FeedbackRequest,
        router_analysis: RouterAnalysisTurn,
        *,
        session_id: str,
        rubric_result=None,
    ) -> InterviewTurnAnalysisDocument:
        """연습모드 피드백 분석 결과를 저장용 문서로 변환"""

        last_turn = request.interview_history[-1]
        return InterviewTurnAnalysisDocument(
            user_id=request.user_id,
            session_id=session_id,
            interview_type=InterviewType.PRACTICE_INTERVIEW,
            question_type=request.question_type,
            turn_order=getattr(last_turn, "turn_order"),
            topic_id=getattr(last_turn, "topic_id"),
            route_decision=None,
            question_text=getattr(last_turn, "question", None),
            answer_text=getattr(last_turn, "answer_text", None),
            question_category=self._safe_str(
                getattr(last_turn, "category", None)
            ),
            question_subcategory=self._safe_str(
                getattr(last_turn, "subcategory", None)
            ),
            aspect_tags=self._extract_tags(
                getattr(last_turn, "aspect_tags", None),
                pair_field=getattr(last_turn, "tech_aspect_pairs", None),
                kind="aspect",
            ),
            tech_tags=self._extract_tags(
                getattr(last_turn, "tech_tags", None),
                pair_field=getattr(last_turn, "tech_aspect_pairs", None),
                kind="tech",
            ),
            tech_aspect_pairs=self._extract_pair_dicts(
                getattr(last_turn, "tech_aspect_pairs", None)
            ),
            portfolio_id=None,
            question_id=request.question_id or getattr(last_turn, "question_id", None),
            analysis=self._build_analysis_from_router_turn(
                request.question_type,
                router_analysis,
            ),
            rubric=self._build_rubric_document(rubric_result),
            follow_up=None,
            new_topic=None,
            end_session=None,
            schema_version=1,
        )

    def build(
        self,
        request: QuestionGenerateRequest,
        result: dict,
    ) -> InterviewTurnAnalysisDocument:
        """request + graph result → InterviewTurnAnalysisDocument

        Args:
            request: 원본 질문 생성 요청 (interview_history 포함)
            result: LangGraph 파이프라인 실행 결과 dict

        Returns:
            MongoDB에 저장할 턴 분석 문서
        """
        last_turn = request.interview_history[-1]

        return InterviewTurnAnalysisDocument(
            # ── 세션 메타 ──
            user_id=request.user_id,
            session_id=request.session_id,
            interview_type=InterviewType.REAL_INTERVIEW,
            question_type=request.question_type,
            turn_order=getattr(last_turn, "turn_order"),
            topic_id=getattr(last_turn, "topic_id"),
            route_decision=result.get("route_decision"),

            # ── 질문/답변 원문 ──
            question_text=getattr(last_turn, "question", None),
            answer_text=getattr(last_turn, "answer_text", None),

            # ── 카테고리 (CS용) ──
            question_category=self._safe_str(
                getattr(last_turn, "category", None)
            ),
            question_subcategory=self._safe_str(
                getattr(last_turn, "subcategory", None)
            ),
            aspect_tags=self._extract_tags(
                getattr(last_turn, "aspect_tags", None),
                pair_field=getattr(last_turn, "tech_aspect_pairs", None),
                kind="aspect",
            ),
            tech_tags=self._extract_tags(
                getattr(last_turn, "tech_tags", None),
                pair_field=getattr(last_turn, "tech_aspect_pairs", None),
                kind="tech",
            ),
            tech_aspect_pairs=self._extract_pair_dicts(
                getattr(last_turn, "tech_aspect_pairs", None)
            ),

            # ── ID 필드 ──
            portfolio_id=request.portfolio_id,
            question_id=getattr(last_turn, "question_id", None),
            # question_pool_id=self._extract_question_pool_id(
            #     request.question_type, last_turn
            # ),

            # ── 분석 결과 (route별 분기) ──
            analysis=self._build_analysis(
                request.question_type,
                result.get("router_analysis"),
            ),
            follow_up=self._build_follow_up(
                request.question_type,
                result,
            ),
            new_topic=self._build_new_topic(result),
            end_session=self._build_end_session(result),

            # ── 메타 ──
            schema_version=1,
        )

    # ================================================================
    # Analysis 빌더 (router_analysis → typed document)
    # ================================================================

    def _build_analysis(
        self,
        question_type: QuestionType,
        router_analysis: dict | None,
    ) -> CSAnalysisDocument | PortfolioAnalysisDocument | None:
        """router_analysis dict → question_type별 analysis document"""

        if not router_analysis:
            return None

        if question_type == QuestionType.CS:
            return CSAnalysisDocument(
                correctness=router_analysis["correctness"],
                has_error=router_analysis["has_error"],
                completeness=router_analysis["completeness"],
                has_missing_concepts=router_analysis["has_missing_concepts"],
                depth=router_analysis["depth"],
                is_superficial=router_analysis["is_superficial"],
                is_well_structured=router_analysis["is_well_structured"],
            )

        if question_type == QuestionType.PORTFOLIO:
            return PortfolioAnalysisDocument(
                completeness=router_analysis["completeness"],
                has_evidence=router_analysis["has_evidence"],
                has_tradeoff=router_analysis["has_tradeoff"],
                has_problem_solving=router_analysis["has_problem_solving"],
                is_well_structured=router_analysis["is_well_structured"],
            )

        return None

    def _build_analysis_from_router_turn(
        self,
        question_type: QuestionType,
        router_analysis: RouterAnalysisTurn,
    ) -> CSAnalysisDocument | PortfolioAnalysisDocument | None:
        """Feedback router_analyses 스키마를 저장용 analysis 문서로 변환"""

        if question_type == QuestionType.CS:
            return CSAnalysisDocument(
                correctness=router_analysis.correctness_detail or "",
                has_error=bool(router_analysis.has_error),
                completeness=router_analysis.completeness_cs_detail or "",
                has_missing_concepts=bool(router_analysis.has_missing_concepts),
                depth=router_analysis.depth_detail or "",
                is_superficial=bool(router_analysis.is_superficial),
                is_well_structured=bool(router_analysis.is_well_structured),
            )

        if question_type == QuestionType.PORTFOLIO:
            return PortfolioAnalysisDocument(
                completeness=router_analysis.completeness_detail or "",
                has_evidence=bool(router_analysis.has_evidence),
                has_tradeoff=bool(router_analysis.has_tradeoff),
                has_problem_solving=bool(router_analysis.has_problem_solving),
                is_well_structured=bool(router_analysis.is_well_structured),
            )

        return None

    @staticmethod
    def _build_rubric_document(rubric_result) -> CSRubricDocument | None:
        if rubric_result is None:
            return None

        return CSRubricDocument(
            correctness=rubric_result.correctness,
            correctness_reason=getattr(rubric_result, "correctness_reason", None),
            completeness=rubric_result.completeness,
            completeness_reason=getattr(rubric_result, "completeness_reason", None),
            reasoning=rubric_result.reasoning,
            reasoning_reason=getattr(rubric_result, "reasoning_reason", None),
            depth=rubric_result.depth,
            depth_reason=getattr(rubric_result, "depth_reason", None),
            delivery=rubric_result.delivery,
            delivery_reason=getattr(rubric_result, "delivery_reason", None),
        )

    # ================================================================
    # Follow-up 빌더
    # ================================================================

    def _build_follow_up(
        self,
        question_type: QuestionType,
        result: dict,
    ) -> CSFollowUpDocument | PortfolioFollowUpDocument | None:
        """result → question_type별 follow_up document"""

        if result.get("route_decision") != "follow_up":
            return None

        if question_type == QuestionType.CS:
            return CSFollowUpDocument(
                direction=result["follow_up_direction"],
                direction_detail=result["direction_detail"],
                reasoning=result["route_reasoning"],
            )

        if question_type == QuestionType.PORTFOLIO:
            return PortfolioFollowUpDocument(
                direction=result["follow_up_direction"],
                direction_detail=result["direction_detail"],
                reasoning=result["route_reasoning"],
            )

        return None

    # ================================================================
    # New Topic / End Session 빌더
    # ================================================================

    def _build_new_topic(
        self,
        result: dict,
    ) -> NewTopicDocument | None:
        """result → new_topic document"""

        if result.get("route_decision") != "new_topic":
            return None

        return NewTopicDocument(
            topic_transition_reason=result.get("topic_transition_reason", ""),
            reasoning=result.get("route_reasoning", ""),
        )

    def _build_end_session(
        self,
        result: dict,
    ) -> EndSessionDocument | None:
        """result → end_session document"""

        if result.get("route_decision") != "end_session":
            return None

        return EndSessionDocument(
            reasoning=result.get("route_reasoning", ""),
        )

    # ================================================================
    # 유틸리티
    # ================================================================

    @staticmethod
    def _safe_str(value) -> str | None:
        """None이 아니면 str로 변환, None이면 None 반환"""
        return str(value) if value is not None else None

    @staticmethod
    def _extract_tags(
        value,
        *,
        pair_field=None,
        kind: str,
    ) -> list[str]:
        """pair 우선, 없으면 legacy 단일 태그를 사용"""
        pair_tags = TurnAnalysisBuilder._extract_tags_from_pairs(
            pair_field,
            kind=kind,
        )
        if pair_tags:
            return pair_tags

        if not value:
            return []

        seen: set[str] = set()
        result: list[str] = []
        for tag in value:
            if not tag or tag in seen:
                continue
            seen.add(tag)
            result.append(str(tag))
        return result

    @staticmethod
    def _extract_tags_from_pairs(
        pair_field,
        *,
        kind: str,
    ) -> list[str]:
        if not pair_field:
            return []

        key = "tech_tag" if kind == "tech" else "aspect_tag"
        seen: set[str] = set()
        result: list[str] = []

        for pair in pair_field:
            value = getattr(pair, key, None)
            if value is None and isinstance(pair, dict):
                value = pair.get(key)
            if not value or value in seen:
                continue
            seen.add(str(value))
            result.append(str(value))

        return result

    @staticmethod
    def _extract_pair_dicts(pair_field) -> list[dict]:
        if not pair_field:
            return []

        seen: set[tuple[str, str]] = set()
        result: list[dict] = []
        for pair in pair_field:
            tech_tag = getattr(pair, "tech_tag", None)
            aspect_tag = getattr(pair, "aspect_tag", None)
            if isinstance(pair, dict):
                tech_tag = pair.get("tech_tag", tech_tag)
                aspect_tag = pair.get("aspect_tag", aspect_tag)
            if not tech_tag or not aspect_tag:
                continue
            pair_key = (str(tech_tag), str(aspect_tag))
            if pair_key in seen:
                continue
            seen.add(pair_key)
            result.append(
                {"tech_tag": str(tech_tag), "aspect_tag": str(aspect_tag)}
            )
        return result

    @staticmethod
    def _extract_question_pool_id(
        question_type: QuestionType,
        last_turn,
    ) -> int | None:
        """포트폴리오인 경우 question_id에서 question_pool_id를 추출"""

        if question_type != QuestionType.PORTFOLIO:
            return None

        question_id = getattr(last_turn, "question_id", None)
        if question_id is None:
            return None

        try:
            return int(question_id)
        except (ValueError, TypeError):
            logger.warning(
                "question_pool_id 변환 실패 | question_id=%s",
                question_id,
            )
            return None
