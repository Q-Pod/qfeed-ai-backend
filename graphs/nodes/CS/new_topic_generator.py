# graphs/nodes/cs_new_topic_generator.py

"""CS 새 토픽 질문 생성 노드

CS 실전모드에서 새로운 토픽의 메인 질문을 생성한다.

CS 특성:
    - 카테고리(OS, 네트워크, DB, 자료구조 등)가 존재한다.
    - 첫 질문: 백엔드가 지정한 initial_category로 강제 생성.
    - 이후 질문: LLM이 카테고리를 선택하여 생성.
    - router_analysis를 참고하여 이전 토픽과 다른 영역을 커버.
"""

from langfuse import observe

from schemas.question import QuestionOutput, GeneratedQuestion, QuestionType
from schemas.feedback_v2 import QuestionCategory, parse_category, get_valid_categories
from prompts.CS.new_topic import get_cs_new_topic_system_prompt, build_cs_new_topic_prompt
from graphs.question.state import QuestionState
from taxonomy.loader import validate_cs_category
from core.dependencies import get_llm_provider
from core.logging import get_logger
from core.tracing import update_observation

logger = get_logger(__name__)


@observe(name="cs_new_topic_generator")
async def cs_new_topic_generator(state: QuestionState) -> dict:
    """CS 새 토픽 질문 생성 노드"""

    session_id = state.get("session_id")
    current_topic_id = state.get("current_topic_id", 0)
    current_topic_count = state.get("current_topic_count", 0)
    new_topic_id = current_topic_id + 1
    # interview_history = state.get("interview_history", [])
    router_analysis = state.get("router_analysis")

    valid_categories = get_valid_categories(QuestionType.CS)

    question_output = await _generate_cs_new_topic_llm(
        state=state,
        available_categories=valid_categories,
        router_analysis=router_analysis,
    )

    category, subcategory = _normalize_cs_taxonomy_selection(
        question_output.category,
        question_output.subcategory,
    )

    combined_text = f"{question_output.cushion_text} {question_output.question_text}"

    generated_question = GeneratedQuestion(
        user_id=state.get("user_id"),
        session_id=session_id,
        question_text=combined_text,
        category=category,
        subcategory=subcategory,
        topic_id=new_topic_id,
        turn_type="new_topic",
        is_session_ended=False,
        end_reason=None,
        is_bad_case=False,
        bad_case_feedback=None,
    )

    logger.info(
        f"session_id : {session_id} | "
        f"CS 새 토픽 질문 생성 완료 | topic_id={new_topic_id} | "
        f"category={category.value if category else None} | "
        f"subcategory={subcategory}"
    )

    update_observation(
        output={
            "topic_id": new_topic_id,
            "category": category.value if category else None,
            "subcategory": subcategory,
            "question_preview": combined_text[:80],
        }
    )

    return {
        "generated_question": generated_question,
        "current_topic_id": new_topic_id,
        "current_topic_count": current_topic_count + 1,
        "current_follow_up_count": 0,
        "follow_up_direction": None,
        "direction_detail": None,
        # 직전 턴 분석 결과는 DB 저장/후처리를 위해 유지
        "router_analysis": router_analysis,
    }


@observe(name="cs_new_topic_llm")
async def _generate_cs_new_topic_llm(
    state: QuestionState,
    forced_category: QuestionCategory | None = None,
    forced_subcategory: str | None = None,
    available_categories: list[str] | None = None,
    router_analysis: dict | None = None,
) -> QuestionOutput:
    """LLM 호출하여 CS 새 토픽 질문 생성"""
 
    llm = get_llm_provider()
 
    system_prompt = get_cs_new_topic_system_prompt()
    user_prompt = build_cs_new_topic_prompt(
        interview_history=state.get("interview_history", []),
        forced_category=forced_category,
        forced_subcategory=forced_subcategory,
        available_categories=available_categories,
        router_analysis=router_analysis,
    )
 
    question_output = await llm.generate_structured(
        prompt=user_prompt,
        response_model=QuestionOutput,
        system_prompt=system_prompt,
        temperature=0.7,
    )
 
    return question_output


def _parse_llm_category(category_str: str | None) -> QuestionCategory | None:
    """LLM이 출력한 카테고리 문자열을 Enum으로 파싱"""
    if not category_str:
        return None

    try:
        return parse_category(QuestionType.CS, category_str)
    except ValueError:
        logger.warning(
            f"LLM generated invalid category: {category_str}, falling back to None"
        )
        return None


def _normalize_cs_taxonomy_selection(
    category_str: str | None,
    subcategory: str | None,
) -> tuple[QuestionCategory | None, str | None]:
    """LLM 출력 category/subcategory를 taxonomy 기준으로 정규화."""
    category = _parse_llm_category(category_str)
    if not category:
        return None, None

    if subcategory and validate_cs_category(category.value, subcategory):
        return category, subcategory

    if subcategory:
        logger.warning(
            "LLM generated invalid subcategory for category | "
            "category=%s | subcategory=%s",
            category.value,
            subcategory,
        )

    return category, None
