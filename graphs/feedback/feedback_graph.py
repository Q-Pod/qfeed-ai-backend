import asyncio
from langgraph.graph import StateGraph, END

from .state import FeedbackGraphState
from graphs.nodes.rubric_evaluator import rubric_evaluator
from graphs.nodes.keyword_checker import keyword_checker
from graphs.nodes.feedback_generator import feedback_generator
# from nodes.send_callback import send_callback # 추후 비동기 도입 시 사용

from exceptions.exceptions import AppException
from exceptions.error_messages import ErrorMessage
from core.logging import get_logger

logger = get_logger(__name__)

def build_feedback_graph():
    """피드백 생성 그래프 빌드"""
    graph = StateGraph(FeedbackGraphState)

    graph.add_node("keyword_checker", _wrap_node("keyword_checker", keyword_checker))
    graph.add_node("rubric_evaluator", _wrap_node("rubric_evaluator", rubric_evaluator))
    graph.add_node("feedback_generator", _wrap_node("feedback_generator", feedback_generator))

    # 엣지 연결 (순차 실행)
    graph.set_entry_point("keyword_checker")
    graph.add_edge("keyword_checker", "rubric_evaluator")
    graph.add_edge("rubric_evaluator", "feedback_generator")
    graph.add_edge("feedback_generator", END)

    return graph.compile()

def _wrap_node(node_name: str, node_func):
    """
    노드 함수 래핑 - 로깅 추가
    
    AppException은 그대로 전파 (이미 적절한 에러 메시지 포함)
    예상치 못한 예외는 FEEDBACK_GENERATION_FAILED로 변환
    """
    async def async_wrapper(state: FeedbackGraphState) -> dict:
        logger.info(f"node start | node={node_name}")
        try:
            result = await node_func(state)
            logger.info(f"node completed | node={node_name}")
            return result
        except AppException:
            # AppException은 그대로 전파 (vLLM 등에서 발생)
            logger.error(f"node failed | node={node_name}")
            raise
        except Exception as e:
            # 예상치 못한 예외는 래핑
            logger.error(f"node failed | node={node_name} | {type(e).__name__}: {e}")
            raise AppException(ErrorMessage.FEEDBACK_GENERATION_FAILED) from e
    def sync_wrapper(state: FeedbackGraphState) -> dict:
        logger.info(f"node start | node={node_name}")
        try:
            result = node_func(state)
            logger.info(f"node completed | node={node_name}")
            return result
        except AppException:
            logger.error(f"node failed | node={node_name}")
            raise
        except Exception as e:
            logger.error(f"node failed | node={node_name} | {type(e).__name__}: {e}")
            raise AppException(ErrorMessage.FEEDBACK_GENERATION_FAILED) from e
    
    if asyncio.iscoroutinefunction(node_func):
        return async_wrapper
    return sync_wrapper

_feedback_graph = None

def get_feedback_graph() -> StateGraph:
    """컴파일된 그래프 인스턴스 반환 (싱글톤)"""
    global _feedback_graph
    if _feedback_graph is None:
        _feedback_graph = build_feedback_graph()
    return _feedback_graph

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