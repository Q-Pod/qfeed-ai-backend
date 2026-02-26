# graphs/question/question_graph.py

"""질문 생성 그래프 정의"""
from langgraph.graph import StateGraph, END
from langfuse import observe

from graphs.question.state import QuestionState
from graphs.nodes.question_router import question_router, get_route_decision
from graphs.nodes.follow_up_generator import follow_up_generator
from graphs.nodes.new_topic_generator import new_topic_generator
from graphs.nodes.session_terminator import session_terminator
from schemas.question import RouteDecision

from exceptions.exceptions import AppException
from exceptions.error_messages import ErrorMessage
from core.logging import get_logger

logger = get_logger(__name__)


def build_question_graph() -> StateGraph:
    """질문 생성 그래프 빌드"""
    
    graph = StateGraph(QuestionState)
    
    # 노드 등록
    graph.add_node("router", question_router)
    graph.add_node("follow_up_generator", follow_up_generator)
    graph.add_node("new_topic_generator", new_topic_generator)
    graph.add_node("session_terminator", session_terminator)

    # 엣지 연결
    graph.set_entry_point("router")
    
    graph.add_conditional_edges(
        "router",
        get_route_decision,
        {
            RouteDecision.FOLLOW_UP.value: "follow_up_generator",
            RouteDecision.NEW_TOPIC.value: "new_topic_generator",
            RouteDecision.END_SESSION.value: "session_terminator",
        },
    )
    
    graph.add_edge("follow_up_generator", END)
    graph.add_edge("new_topic_generator", END)
    graph.add_edge("session_terminator", END)
    
    compiled_graph = graph.compile()
    
    logger.info("Question generation graph compiled successfully")
    
    return compiled_graph


# 싱글톤 그래프 인스턴스
_question_graph = None


def get_question_graph() -> StateGraph:
    """컴파일된 그래프 인스턴스 반환 (싱글톤)"""
    global _question_graph
    if _question_graph is None:
        _question_graph = build_question_graph()
    return _question_graph

@observe(name="question_pipeline")
async def run_question_pipeline(initial_state: QuestionState) -> dict:
    """질문 생성 파이프라인 실행 """
    graph = get_question_graph()
    try: 
        result = await graph.ainvoke(initial_state)
        return result
    except AppException:
        raise
    except Exception as e:
        logger.error(f"question generate graph failed | {type(e).__name__}: {e}")
        raise AppException(ErrorMessage.FEEDBACK_GENERATION_FAILED) from e

