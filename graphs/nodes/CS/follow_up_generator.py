# graphs/nodes/cs_follow_up_generator.py

"""CS 기초 꼬리질문 생성 노드

cs_question_router가 state에 남긴 follow_up_direction과 direction_detail을
활용하여, 방향에 맞는 CS 꼬리질문을 생성한다.

direction별 질문 성격:
    - depth: 핵심 구성요소가 빠졌을 때, 같은 개념을 더 구체적으로 파고듦
    - reasoning: 정의는 맞지만 '왜'를 설명 못할 때, 원리/이유를 요구
    - correction: 사실적 오류가 있을 때, 틀린 부분을 짚어 재답변 유도
    - lateral: 현재 개념은 충분히 다뤘고, 연관된 인접 개념으로 확장
"""

from langfuse import observe

from schemas.question import FollowUpOutput, GeneratedQuestion
from graphs.question.state import QuestionState
from taxonomy.loader import validate_cs_category
from core.dependencies import get_llm_provider
from core.logging import get_logger
from core.tracing import update_observation
from prompts.CS.follow_up import (
    CS_FOLLOW_UP_SYSTEM_PROMPT,
    build_cs_follow_up_user_prompt,
)

logger = get_logger(__name__)

# ============================================================
# Node
# ============================================================

@observe(name="cs_follow_up_generator")
async def cs_follow_up_generator(state: QuestionState) -> dict:
    """CS 꼬리질문 생성 노드

    cs_question_router가 결정한 direction에 맞는 꼬리질문을 생성한다.

    Returns:
        dict: generated_question, current_follow_up_count 업데이트
    """

    session_id = state.get("session_id")
    current_topic_id = state.get("current_topic_id", 1)
    current_follow_up_count = state.get("current_follow_up_count", 0)
    interview_history = state.get("interview_history", [])
    follow_up_direction = state.get("follow_up_direction", "depth")
    direction_detail = state.get("direction_detail", "")

    # 현재 토픽의 카테고리 추출
    current_topic_turns = [
        t for t in interview_history if t.topic_id == current_topic_id
    ]
    if not current_topic_turns:
        raise ValueError(f"No history found for topic_id={current_topic_id}")

    main_turn = next(
        (t for t in current_topic_turns if t.turn_type == "new_topic"),
        current_topic_turns[0],
    )
    current_category = main_turn.category
    current_subcategory = main_turn.subcategory

    try:
        follow_up_output = await _generate_cs_follow_up_llm(
            state=state,
            current_topic_turns=current_topic_turns,
            follow_up_direction=follow_up_direction,
            direction_detail=direction_detail,
        )
        normalized_subcategory = _normalize_follow_up_subcategory(
            current_category=current_category,
            generated_subcategory=follow_up_output.subcategory,
            current_subcategory=current_subcategory,
        )

        generated_question = GeneratedQuestion(
            user_id=state.get("user_id"),
            session_id=session_id,
            question_text=f"{follow_up_output.cushion_text} {follow_up_output.question_text}",
            category=current_category,
            subcategory=normalized_subcategory,
            topic_id=current_topic_id,
            turn_type="follow_up",
            is_session_ended=False,
            end_reason=None,
            is_bad_case=False,
            bad_case_feedback=None,
        )

        logger.info(
            f"session_id : {session_id} | "
            f"CS 꼬리질문 생성 완료 | "
            f"topic_id={current_topic_id} | "
            f"direction={follow_up_direction}"
        )

        update_observation(
            output={
                "direction": follow_up_direction,
                "subcategory": normalized_subcategory,
                "question_preview": follow_up_output.question_text[:80],
            }
        )

        return {
            "generated_question": generated_question,
            "current_follow_up_count": current_follow_up_count + 1,
        }

    except Exception as e:
        logger.error(
            f"session_id : {session_id} | "
            f"CS follow-up generation failed | {type(e).__name__}: {e}"
        )
        return {
            "error": f"CS 꼬리질문 생성 실패: {str(e)}",
        }


async def _generate_cs_follow_up_llm(
    state: QuestionState,
    current_topic_turns: list,
    follow_up_direction: str,
    direction_detail: str,
) -> FollowUpOutput:
    """LLM을 호출하여 CS 꼬리질문 생성"""

    last_turn = current_topic_turns[-1]

    user_prompt = build_cs_follow_up_user_prompt(
        current_topic_turns=current_topic_turns,
        follow_up_direction=follow_up_direction,
        direction_detail=direction_detail,
        last_question=last_turn.question,
        last_answer=last_turn.answer_text,
        category=last_turn.category,
        current_subcategory=last_turn.subcategory,
    )

    llm_provider = get_llm_provider("gemini")

    follow_up_output = await llm_provider.generate_structured(
        prompt=user_prompt,
        system_prompt=CS_FOLLOW_UP_SYSTEM_PROMPT,
        response_model=FollowUpOutput,
        temperature=0.7,
    )

    return follow_up_output


def _normalize_follow_up_subcategory(
    current_category,
    generated_subcategory: str | None,
    current_subcategory: str | None,
) -> str | None:
    """Follow-up subcategory를 현재 category 기준 taxonomy로 정규화."""
    if current_category is None:
        return None

    category_value = (
        current_category.value
        if hasattr(current_category, "value")
        else str(current_category)
    )

    if generated_subcategory and validate_cs_category(
        category_value,
        generated_subcategory,
    ):
        return generated_subcategory

    if generated_subcategory:
        logger.warning(
            "LLM generated invalid follow-up subcategory | "
            "category=%s | subcategory=%s | fallback=%s",
            category_value,
            generated_subcategory,
            current_subcategory,
        )

    if current_subcategory and validate_cs_category(
        category_value,
        current_subcategory,
    ):
        return current_subcategory

    return None
