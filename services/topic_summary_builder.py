# services/topic_summary_builder.py

from __future__ import annotations

from core.logging import get_logger
from schemas.feedback_v2 import InterviewType
from schemas.question import QuestionGenerateRequest
from schemas.seesion_topic_summaries import SessionTopicSummaryDocument

logger = get_logger(__name__)


class TopicSummaryBuilder:
    """Graph 결과의 topic_summaries -> SessionTopicSummaryDocument 변환"""

    def build_if_needed(
        self,
        request: QuestionGenerateRequest,
        result: dict,
    ) -> SessionTopicSummaryDocument | None:
        """
        new_topic 분기에서만 마지막 topic summary를 저장 문서로 변환한다.
        """

        if not request.interview_history:
            return None

        if result.get("route_decision") != "new_topic":
            return None

        topic_summaries = result.get("topic_summaries") or []
        if not topic_summaries:
            return None

        last_summary = topic_summaries[-1]

        turn_start_order, turn_end_order = self._find_topic_turn_range(
            interview_history=request.interview_history,
            topic_id=last_summary["topic_id"],
        )

        source_question_id = self._find_source_question_id(
            interview_history=request.interview_history,
            topic_id=last_summary["topic_id"],
        )

        return SessionTopicSummaryDocument(
            user_id=request.user_id,
            session_id=request.session_id,
            interview_type=InterviewType.REAL_INTERVIEW,
            question_type=request.question_type,
            topic_id=last_summary["topic_id"],
            topic=last_summary["topic"],
            key_points=last_summary.get("key_points", []),
            gaps=last_summary.get("gaps", []),
            depth_reached=last_summary["depth_reached"],
            technologies_mentioned=last_summary.get(
                "technologies_mentioned", []
            ),
            turn_start_order=turn_start_order,
            turn_end_order=turn_end_order,
            source_question_id=source_question_id,
            schema_version=1,
        )

    def _find_topic_turn_range(
        self,
        *,
        interview_history: list,
        topic_id: int,
    ) -> tuple[int | None, int | None]:
        topic_turns = [
            turn for turn in interview_history
            if getattr(turn, "topic_id", None) == topic_id
        ]
        if not topic_turns:
            return None, None

        turn_orders = [
            getattr(turn, "turn_order")
            for turn in topic_turns
            if getattr(turn, "turn_order", None) is not None
        ]
        if not turn_orders:
            return None, None

        return min(turn_orders), max(turn_orders)

    def _find_source_question_id(
        self,
        *,
        interview_history: list,
        topic_id: int,
    ) -> int | None:
        """
        해당 topic의 메인 질문(new_topic)의 canonical question_id를 찾는다.
        follow-up만 있는 경우는 None.
        """
        main_turn = next(
            (
                turn for turn in interview_history
                if getattr(turn, "topic_id", None) == topic_id
                and getattr(turn, "turn_type", None) == "new_topic"
            ),
            None,
        )
        if not main_turn:
            return None

        return getattr(main_turn, "question_id", None)