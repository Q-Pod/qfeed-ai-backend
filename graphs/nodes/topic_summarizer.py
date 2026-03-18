# graphs/nodes/common/topic_summarizer.py

"""공통 토픽 요약 노드

new_topic으로 분기될 때 실행되어, 완료된 토픽의 Q&A를 압축 요약한다.
CS / 포트폴리오 모두 동일한 로직을 사용한다.

요약 결과는 topic_summaries에 누적되어:
    - 질문 생성: 이전 토픽 참조 (중복 방지, connect_probe)
    - 피드백 생성: 토픽별 피드백의 맥락 제공
    - 백엔드 응답: GeneratedQuestion.topic_summary로 전달
"""

from langfuse import observe

from graphs.question.state import QuestionState, TopicSummary
from schemas.question import TopicSummaryOutput
from prompts.topic_summarizer import (
    TOPIC_SUMMARIZER_SYSTEM_PROMPT,
    build_topic_summarizer_prompt,
)
from core.dependencies import get_llm_provider
from core.logging import get_logger
from core.tracing import update_observation

logger = get_logger(__name__)


@observe(name="topic_summarizer")
async def topic_summarizer(state: QuestionState) -> dict:
    """완료된 토픽을 요약하여 topic_summaries에 추가

    question_router가 new_topic을 결정한 후 실행된다.
    현재 토픽의 Q&A 전체를 LLM으로 요약하고, topic_summaries에 누적한다.

    CS / 포트폴리오 공통으로 사용.

    Returns:
        dict: topic_summaries 업데이트 (기존 리스트 + 새 요약)
    """

    session_id = state.get("session_id")
    current_topic_id = state.get("current_topic_id", 1)
    interview_history = state.get("interview_history", [])
    topic_transition_reason = state.get(
        "topic_transition_reason", "토픽 전환"
    )
    existing_summaries = state.get("topic_summaries", [])

    # 현재 토픽의 Q&A 추출
    current_topic_turns = [
        t for t in interview_history if t.topic_id == current_topic_id
    ]

    if not current_topic_turns:
        logger.warning(
            f"session_id={session_id} | "
            f"No turns found for topic_id={current_topic_id}, skipping summarization"
        )
        return {"topic_summaries": existing_summaries}

    # 토픽명 추출 (메인질문 기준)
    main_turn = next(
        (t for t in current_topic_turns if t.turn_type == "new_topic"),
        current_topic_turns[0],
    )

    try:
        summary_output = await _invoke_summarizer_llm(
            current_topic_turns=current_topic_turns,
            topic_transition_reason=topic_transition_reason,
        )

        new_summary: TopicSummary = {
            "topic_id": current_topic_id,
            "topic": summary_output.topic,
            "key_points": summary_output.key_points,
            "gaps": summary_output.gaps,
            "depth_reached": summary_output.depth_reached,
            "technologies_mentioned": summary_output.technologies_mentioned,
            "transition_reason": topic_transition_reason,
        }

        updated_summaries = existing_summaries + [new_summary]

        logger.info(
            f"session_id={session_id} | "
            f"Topic summarized | "
            f"topic_id={current_topic_id} | "
            f"topic={summary_output.topic} | "
            f"depth={summary_output.depth_reached} | "
            f"total_summaries={len(updated_summaries)}"
        )

        update_observation(
            output={
                "topic": summary_output.topic,
                "depth": summary_output.depth_reached,
                "key_points_count": len(summary_output.key_points),
                "gaps_count": len(summary_output.gaps),
            }
        )

        return {"topic_summaries": updated_summaries}

    except Exception as e:
        logger.error(
            f"session_id={session_id} | "
            f"Topic summarization failed | {type(e).__name__}: {e}"
        )
        fallback_summary: TopicSummary = {
            "topic_id": current_topic_id,
            "topic": main_turn.question[:50],
            "key_points": [],
            "gaps": [],
            "depth_reached": "unknown",
            "technologies_mentioned": [],
            "transition_reason": topic_transition_reason,
        }
        return {"topic_summaries": existing_summaries + [fallback_summary]}


async def _invoke_summarizer_llm(
    current_topic_turns: list,
    topic_transition_reason: str,
) -> TopicSummaryOutput:
    """Gemini를 호출하여 토픽 요약 생성"""

    user_prompt = build_topic_summarizer_prompt(
        topic_turns=current_topic_turns,
        topic_transition_reason=topic_transition_reason,
    )

    llm_provider = get_llm_provider("gemini")

    summary_output = await llm_provider.generate_structured(
        prompt=user_prompt,
        system_prompt=TOPIC_SUMMARIZER_SYSTEM_PROMPT,
        response_model=TopicSummaryOutput,
        temperature=0.1,
    )

    return summary_output