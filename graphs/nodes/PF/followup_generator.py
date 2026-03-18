# graphs/nodes/PF/follow_up_generator.py

"""포트폴리오 꼬리질문 생성 노드

pf_question_router가 state에 남긴 follow_up_direction과 direction_detail을
활용하여, 방향에 맞는 포트폴리오 꼬리질문을 생성한다.

포트폴리오 direction별 질문 성격:
    - depth_probe: 구체적 구현, 동작 방식, 설정 값을 파고듦
    - why_probe: 기술 선택의 근거, 의사결정 과정을 파고듦
    - tradeoff_probe: 장단점, 대안 비교, 한계 인식을 파고듦
    - problem_probe: 어려웠던 점, 실패 경험, 예상 못한 이슈를 파고듦
    - scale_probe: 확장 시나리오, 설계의 한계를 파고듦
    - connect_probe: 이전 토픽과 연결되는 포인트를 파고듦

CS 꼬리질문과의 차이:
    - 포트폴리오 요약(portfolio_summary)을 참조하여 프로젝트 맥락 유지
    - direction 종류가 6가지로 더 세분화됨 (CS는 4가지)
    - 지원자의 실제 경험에 기반한 질문을 생성해야 함
"""

from langfuse import observe

from schemas.question import PortfolioFollowUpOutput, GeneratedQuestion
from graphs.question.state import QuestionState
from core.dependencies import get_llm_provider
from core.logging import get_logger
from core.tracing import update_observation
from taxonomy.loader import normalize_tech_tag, validate_aspect_tag
from prompts.PF.follow_up import (
    PF_FOLLOW_UP_SYSTEM_PROMPT,
    build_pf_follow_up_user_prompt,
)

logger = get_logger(__name__)


# ============================================================
# Node
# ============================================================

@observe(name="pf_follow_up_generator")
async def pf_follow_up_generator(state: QuestionState) -> dict:
    """포트폴리오 꼬리질문 생성 노드

    pf_question_router가 결정한 direction에 맞는 꼬리질문을 생성한다.
    router가 분석과 방향을 이미 결정했으므로, 이 노드는 질문 문장만 생성한다.

    Returns:
        dict: generated_question, current_follow_up_count 업데이트
    """

    session_id = state.get("session_id")
    current_topic_id = state.get("current_topic_id", 1)
    current_follow_up_count = state.get("current_follow_up_count", 0)
    interview_history = state.get("interview_history", [])
    follow_up_direction = state.get("follow_up_direction", "depth_probe")
    direction_detail = state.get("direction_detail", "")

    # 현재 토픽의 턴 추출
    current_topic_turns = [
        t for t in interview_history if t.topic_id == current_topic_id
    ]
    if not current_topic_turns:
        raise ValueError(f"No history found for topic_id={current_topic_id}")

    # 현재 토픽의 카테고리 추출 (메인질문 기준)
    main_turn = next(
        (t for t in current_topic_turns if t.turn_type == "new_topic"),
        current_topic_turns[0],
    )
    current_category = main_turn.category

    try:
        follow_up_output = await _generate_pf_follow_up_llm(
            state=state,
            current_topic_turns=current_topic_turns,
            follow_up_direction=follow_up_direction,
            direction_detail=direction_detail,
        )
        tech_aspect_pairs, tech_tags, aspect_tags = _normalize_pf_follow_up_pairs(
            raw_pairs=follow_up_output.tech_aspect_pairs,
        )

        generated_question = GeneratedQuestion(
            user_id=state.get("user_id"),
            session_id=session_id,
            question_text=f"{follow_up_output.cushion_text} {follow_up_output.question_text}",
            category=current_category,
            tech_tags=tech_tags,
            aspect_tags=aspect_tags,
            tech_aspect_pairs=tech_aspect_pairs,
            topic_id=current_topic_id,
            turn_type="follow_up",
            is_session_ended=False,
            end_reason=None,
            is_bad_case=False,
            bad_case_feedback=None,
        )

        logger.info(
            f"session_id={session_id} | "
            f"PF 꼬리질문 생성 완료 | "
            f"topic_id={current_topic_id} | "
            f"direction={follow_up_direction}"
        )

        update_observation(
            output={
                "direction": follow_up_direction,
                "question_preview": follow_up_output.question_text[:80],
            }
        )

        return {
            "generated_question": generated_question,
            "current_follow_up_count": current_follow_up_count + 1,
        }

    except Exception as e:
        logger.error(
            f"session_id={session_id} | "
            f"PF follow-up generation failed | {type(e).__name__}: {e}"
        )
        raise

# ============================================================
# LLM 호출
# ============================================================

async def _generate_pf_follow_up_llm(
    state: QuestionState,
    current_topic_turns: list,
    follow_up_direction: str,
    direction_detail: str,
) -> PortfolioFollowUpOutput:
    """Gemini Flash를 호출하여 포트폴리오 꼬리질문 생성"""

    last_turn = current_topic_turns[-1]

    user_prompt = build_pf_follow_up_user_prompt(
        portfolio_summary=state.get("portfolio_summary", "포트폴리오 정보 없음"),
        current_topic_turns=current_topic_turns,
        follow_up_direction=follow_up_direction,
        direction_detail=direction_detail,
        last_question=last_turn.question,
        last_answer=last_turn.answer_text,
    )

    llm_provider = get_llm_provider("gemini_lite")

    follow_up_output = await llm_provider.generate_structured(
        prompt=user_prompt,
        system_prompt=PF_FOLLOW_UP_SYSTEM_PROMPT,
        response_model=PortfolioFollowUpOutput,
        temperature=0.7,
    )

    return follow_up_output


def _normalize_pf_follow_up_pairs(
    *,
    raw_pairs: list,
) -> tuple[list[dict], list[str], list[str]]:
    normalized_pairs: list[dict] = []
    seen_pairs: set[tuple[str, str]] = set()

    for pair in raw_pairs:
        tech_tag = getattr(pair, "tech_tag", None)
        aspect_tag = getattr(pair, "aspect_tag", None)
        if isinstance(pair, dict):
            tech_tag = pair.get("tech_tag", tech_tag)
            aspect_tag = pair.get("aspect_tag", aspect_tag)

        tech_tag = normalize_tech_tag(tech_tag or "")
        aspect_tag = aspect_tag or ""

        if not tech_tag or not aspect_tag or not validate_aspect_tag(aspect_tag):
            continue

        pair_key = (tech_tag, aspect_tag)
        if pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)
        normalized_pairs.append(
            {"tech_tag": tech_tag, "aspect_tag": aspect_tag}
        )

    tech_tags = _dedupe_tags([pair["tech_tag"] for pair in normalized_pairs])
    aspect_tags = _dedupe_tags([pair["aspect_tag"] for pair in normalized_pairs])
    return normalized_pairs, tech_tags, aspect_tags


def _dedupe_tags(tags: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []

    for tag in tags:
        if not tag or tag in seen:
            continue
        seen.add(tag)
        result.append(tag)

    return result
