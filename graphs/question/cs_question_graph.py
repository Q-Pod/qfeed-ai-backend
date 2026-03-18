# graphs/question/cs_question_graph.py

"""CS 기초 질문 생성 그래프

CS 실전모드의 질문 생성 파이프라인을 정의한다.

흐름:
    router → follow_up_generator (LLM)
           → topic_summarizer (LLM) → new_topic_generator (LLM)
           → session_terminator

v2 변경사항:
    - topic_summarizer 추가: new_topic 분기 시 완료된 토픽 요약 생성
    - 요약 결과는 topic_summaries에 누적
    - 백엔드에 전달되어 피드백 생성 시 활용
"""

from langgraph.graph import StateGraph, END

from graphs.question.state import QuestionState
from graphs.nodes.CS.question_router import cs_question_router, get_cs_route_decision
from graphs.nodes.CS.follow_up_generator import cs_follow_up_generator
from graphs.nodes.CS.new_topic_generator import cs_new_topic_generator
from graphs.nodes.topic_summarizer import topic_summarizer
from graphs.nodes.session_terminator import session_terminator
from schemas.question import RouteDecision

from core.logging import get_logger

logger = get_logger(__name__)


def build_cs_question_graph() -> StateGraph:
    """CS 질문 생성 그래프 빌드

    그래프 구조:
        START
          ↓
        [cs_question_router] ── 답변 분석 + 라우팅 결정 + 방향 제시
          ↓ (conditional edge)
        ┌─────────────────┼──────────────────┐
        ↓                 ↓                  ↓
    [follow_up]   [topic_summarizer]   [terminator]
        ↓                 ↓                  ↓
       END        [new_topic_generator]     END
                          ↓
                         END

    v1 → v2 변경:
        - new_topic 분기 시 topic_summarizer가 먼저 실행
        - topic_summarizer → new_topic_generator 순차 연결
    """

    graph = StateGraph(QuestionState)

    # ── 노드 등록 ──────────────────────────────────────────────
    graph.add_node("router", cs_question_router)
    graph.add_node("follow_up_generator", cs_follow_up_generator)
    graph.add_node("topic_summarizer", topic_summarizer)
    graph.add_node("new_topic_generator", cs_new_topic_generator)
    graph.add_node("session_terminator", session_terminator)

    # ── 엣지 연결 ──────────────────────────────────────────────
    graph.set_entry_point("router")

    graph.add_conditional_edges(
        "router",
        get_cs_route_decision,
        {
            RouteDecision.FOLLOW_UP.value: "follow_up_generator",
            RouteDecision.NEW_TOPIC.value: "topic_summarizer",
            RouteDecision.END_SESSION.value: "session_terminator",
        },
    )

    # topic_summarizer → new_topic_generator (순차)
    graph.add_edge("topic_summarizer", "new_topic_generator")

    # 터미널 노드 → END
    graph.add_edge("follow_up_generator", END)
    graph.add_edge("new_topic_generator", END)
    graph.add_edge("session_terminator", END)

    compiled = graph.compile()
    logger.info("CS question generation graph compiled successfully")

    return compiled


# 싱글톤
_cs_question_graph = None


def get_cs_question_graph():
    """컴파일된 CS 그래프 인스턴스 반환 (싱글톤)"""
    global _cs_question_graph
    if _cs_question_graph is None:
        _cs_question_graph = build_cs_question_graph()
    return _cs_question_graph