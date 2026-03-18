# graphs/nodes/PF/new_topic_generator.py

"""포트폴리오 새 토픽 질문 선택 노드

topic_summarizer 이후 실행되어,
QuestionPoolSelector를 통해 DB의 질문 풀에서 다음 질문을 선택한다.

기존 버전과의 차이:
    - state["question_pool"] 직접 참조 제거
    - LLM 기반 풀 선택 제거
    - QuestionPoolSelector 기반으로 일관된 선택 로직 사용
"""

from langfuse import observe

from graphs.question.state import QuestionState
from schemas.question import GeneratedQuestion
from services.qpool_selector import QuestionPoolSelector
from core.logging import get_logger
from core.tracing import update_observation

logger = get_logger(__name__)


@observe(name="pf_new_topic_generator")
async def pf_new_topic_generator(state: QuestionState) -> dict:
    """질문 풀에서 다음 토픽 질문을 선택하는 노드

    흐름:
        1. interview_history에서 이미 사용한 question_id 추출
        2. QuestionPoolSelector로 다음 질문 선택
        3. 없으면 세션 종료
        4. 있으면 GeneratedQuestion 반환
    """

    user_id = state.get("user_id")
    session_id = state.get("session_id")
    portfolio_id = state.get("portfolio_id")
    current_topic_id = state.get("current_topic_id", 0)
    current_topic_count = state.get("current_topic_count", 0)
    interview_history = state.get("interview_history", [])
    topic_summaries = state.get("topic_summaries", [])

    if portfolio_id is None:
        raise ValueError("PF new topic generation requires portfolio_id")

    selector = QuestionPoolSelector()

    used_question_ids = selector.extract_used_ids(interview_history)

    preferred_aspect_tags = _extract_preferred_aspect_tags(topic_summaries)
    preferred_tech_tags = _extract_preferred_tech_tags(topic_summaries)

    selected = await selector.select_new_topic_question(
        user_id=user_id,
        portfolio_id=portfolio_id,
        used_question_ids=used_question_ids,
        preferred_aspect_tags=preferred_aspect_tags,
        preferred_tech_tags=preferred_tech_tags,
    )

    # 질문 풀이 다 소진된 경우
    if selected is None:
        logger.info(
            "session_id=%s | portfolio_id=%s | question pool exhausted",
            session_id,
            portfolio_id,
        )
        return {
            "generated_question": GeneratedQuestion(
                user_id=user_id,
                session_id=session_id,
                question_text="준비된 질문을 모두 진행했습니다. 수고하셨습니다.",
                category=None,
                topic_id=current_topic_id,
                turn_type="new_topic",
                is_session_ended=True,
                end_reason="질문 풀 소진",
                is_bad_case=False,
                bad_case_feedback=None,
                # GeneratedQuestion 스키마에 있으면 같이 넣기
                question_id=None,
            ),
        }

    new_topic_id = current_topic_id + 1

    generated_question = GeneratedQuestion(
        user_id=user_id,
        session_id=session_id,
        question_id=selected["question_id"],
        question_text=selected["question_text"],
        category=None,
        tech_tags=selected.get("tech_tags", []),
        aspect_tags=selected.get("aspect_tags", []),
        tech_aspect_pairs=selected.get("tech_aspect_pairs", []),
        topic_id=new_topic_id,
        turn_type="new_topic",
        is_session_ended=False,
        end_reason=None,
        is_bad_case=False,
        bad_case_feedback=None,
    )

    logger.info(
        "session_id=%s | new topic selected from pool | "
        "portfolio_id=%s | question_id=%s | topic_id=%s",
        session_id,
        portfolio_id,
        selected.get("question_id"),
        new_topic_id,
    )

    update_observation(
        output={
            "selected_question_id": selected.get("question_id"),
            "selected_question_preview": selected.get("question_text", "")[:80],
            "preferred_aspect_tags": preferred_aspect_tags,
            "preferred_tech_tags": preferred_tech_tags,
        }
    )

    return {
        "generated_question": generated_question,
        "current_topic_id": new_topic_id,
        "current_topic_count": current_topic_count + 1,
        "current_follow_up_count": 0,
    }


def _extract_preferred_aspect_tags(topic_summaries: list[dict]) -> list[str]:
    """topic summary에서 다음 질문 선호 aspect tag 추출

    현재는 보수적으로 빈 리스트 반환.
    나중에 gaps -> aspect_tags 매핑 규칙이 생기면 여기서 확장.
    """
    return []


def _extract_preferred_tech_tags(topic_summaries: list[dict]) -> list[str]:
    """topic summary에서 다음 질문 선호 tech tag 추출

    가장 최근 토픽에서 언급된 기술을 우선적으로 활용할 수도 있고,
    반대로 미언급 기술을 추천할 수도 있다.
    현재는 단순히 최근 summary의 technologies_mentioned를 사용.
    """
    if not topic_summaries:
        return []

    last_summary = topic_summaries[-1]
    techs = last_summary.get("technologies_mentioned", []) or []

    # 순서 유지 중복 제거
    seen = set()
    result = []
    for tech in techs:
        if tech not in seen:
            seen.add(tech)
            result.append(tech)

    return result
