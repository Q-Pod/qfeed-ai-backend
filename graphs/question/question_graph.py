# graphs/question/question_graph.py

"""질문 생성 그래프 팩토리

question_type에 따라 적절한 카테고리별 그래프를 선택하여 실행한다.
각 카테고리별 그래프는 별도 모듈에서 정의한다.

- CS:           cs_question_graph.py
- PORTFOLIO:    portfolio_question_graph.py  (TODO)
- SYSTEM_DESIGN: system_design_question_graph.py  (TODO)
"""

from langfuse import observe

from graphs.question.state import QuestionState
from graphs.question.cs_question_graph import get_cs_question_graph
from graphs.question.pf_question_graph import get_pf_question_graph
from schemas.feedback import QuestionType
from exceptions.exceptions import AppException
from exceptions.error_messages import ErrorMessage
from core.logging import get_logger

logger = get_logger(__name__)

def _get_graph_for_question_type(question_type: QuestionType):
    """question_type에 맞는 컴파일된 그래프를 반환한다."""

    if question_type == QuestionType.CS:
        return get_cs_question_graph()

    elif question_type == QuestionType.PORTFOLIO:
        return get_pf_question_graph()

    # TODO: 시스템 디자인 그래프 구현 후 활성화
    # elif question_type == QuestionType.SYSTEM_DESIGN:
    #     return get_system_design_question_graph()

    else:
        # 아직 구현되지 않은 question_type은 기존 범용 그래프로 fallback
        # 기존 범용 그래프도 없으면 CS 그래프를 사용 (임시)
        logger.warning(
            f"No dedicated graph for question_type={question_type.value}, "
            f"falling back to CS graph"
        )
        return get_cs_question_graph()


@observe(name="question_pipeline")
async def run_question_pipeline(initial_state: QuestionState) -> dict:
    """질문 생성 파이프라인 실행

    question_type에 따라 적절한 그래프를 선택하고 실행한다.
    서비스 레이어는 이 함수만 호출하면 된다.
    """
    question_type = initial_state["question_type"]
    graph = _get_graph_for_question_type(question_type)

    logger.info(
        f"Running question pipeline | "
        f"question_type={question_type.value} | "
        f"graph={type(graph).__name__}"
    )

    try:
        result = await graph.ainvoke(initial_state)
        return result
    except AppException:
        raise
    except Exception as e:
        logger.error(f"question generate graph failed | {type(e).__name__}: {e}")
        raise AppException(ErrorMessage.QUESTION_GENERATION_FAILED) from e






