from langgraph.graph import StateGraph, END


from .state import FeedbackGraphState
from project.qfeed.graphs.nodes.rubric_evaluator import rubric_evaluator
from graphs.nodes.keyword_checker import keyword_checker
from project.qfeed.graphs.nodes.CS.feedback_generator import feedback_generator
# from nodes.send_callback import send_callback # 추후 비동기 도입 시 사용

from exceptions.exceptions import AppException
from exceptions.error_messages import ErrorMessage
from core.logging import get_logger
from langfuse import observe 

logger = get_logger(__name__)

def build_feedback_graph():
    """피드백 생성 그래프 빌드"""
    graph = StateGraph(FeedbackGraphState)

    graph.add_node("keyword_checker", keyword_checker)
    graph.add_node("rubric_evaluator", rubric_evaluator)
    graph.add_node("feedback_generator", feedback_generator)

    # 엣지 연결 (순차 실행)
    graph.set_entry_point("keyword_checker")
    graph.add_edge("keyword_checker", "rubric_evaluator")
    graph.add_edge("rubric_evaluator", "feedback_generator")
    graph.add_edge("feedback_generator", END)

    return graph.compile()

_feedback_graph = None

def get_feedback_graph() -> StateGraph:
    """컴파일된 그래프 인스턴스 반환 (싱글톤)"""
    global _feedback_graph
    if _feedback_graph is None:
        _feedback_graph = build_feedback_graph()
    return _feedback_graph

@observe(name="feedback_graph", as_type="chain")
async def run_feedback_pipeline(initial_state: FeedbackGraphState) -> FeedbackGraphState:
    """피드백 파이프라인 실행"""
    graph = get_feedback_graph()

    try: 
        result = await graph.ainvoke(initial_state)
        return result
    except AppException:
        raise
    except Exception as e:
        logger.error(f"feedback graph failed | {type(e).__name__}: {e}")
        raise AppException(ErrorMessage.FEEDBACK_GENERATION_FAILED) from e