# graphs/question/pf_question_graph.py
"""
포트폴리오 질문 생성 그래프

포트폴리오 실전모드의 질문 생성 파이프라인을 정의한다.

흐름:
    router → follow_up_generator (LLM)
           → topic_summarizer → new_topic_generator (LLM) 
           → session_terminator


파이프라인 설계:
    1. pf_question_router: 답변 분석 + 라우팅 결정 + 꼬리질문 방향 제시
       - PortfolioRouterOutput (Union 타입) 으로 structured output
       - follow_up / new_topic / end_session 분기 결정
       
    2. pf_follow_up_generator: router의 direction을 기반으로 꼬리질문 생성
       - router가 분석과 방향을 이미 결정했으므로, 질문 문장만 생성
       
    3. topic_summarizer: 완료된 토픽의 Q&A를 압축 요약
       - new_topic 분기 시에만 실행
       - 요약 결과를 topic_summaries에 누적
       
    4. pf_new_topic_generator: 이전 토픽 요약을 참고하여 새 토픽 질문 생성
       - topic_summaries를 참조하여 중복 토픽 방지
       
    5. session_terminator: 면접 종료 처리
"""

from langgraph.graph import StateGraph, END

from graphs.question.state import QuestionState
from graphs.nodes.PF.question_router import pf_question_router, get_pf_route_decision
from graphs.nodes.PF.followup_generator import pf_follow_up_generator
from graphs.nodes.PF.new_topic_generator import pf_new_topic_generator
from graphs.nodes.topic_summarizer import topic_summarizer
from graphs.nodes.session_terminator import session_terminator
from schemas.question import RouteDecision

from core.logging import get_logger

logger = get_logger(__name__)   

def build_pf_question_graph() -> StateGraph:
    """포트폴리오 질문 생성 그래프 빌드

    그래프 구조:
        START
          ↓
        [pf_question_router] ── 답변 분석 + 라우팅 결정 + 방향 제시
          ↓ (conditional edge)
        ┌─────────────────┼──────────────────┐
        ↓                 ↓                  ↓
    [follow_up]   [topic_summarizer]   [terminator]
        ↓                 ↓                  ↓
       END        [new_topic_generator]     END
                          ↓
                         END

    노드별 역할:
        - pf_question_router: 답변 분석, 라우팅 결정, 꼬리질문 방향 제시 (Gemini Flash)
        - pf_follow_up_generator: direction 기반 꼬리질문 생성 (Gemini Flash)
        - topic_summarizer: 완료된 토픽 Q&A 압축 요약 (Gemini Flash)
        - pf_new_topic_generator: 토픽 요약 참조하여 새 질문 생성 (Gemini Flash)
        - session_terminator: 면접 종료 응답 생성 (LLM 호출 없음)
    """


    graph = StateGraph(QuestionState)

    # ── 노드 등록 ──────────────────────────────────────────────
    graph.add_node("pf_question_router", pf_question_router)
    graph.add_node("pf_follow_up_generator", pf_follow_up_generator)
    graph.add_node("topic_summarizer", topic_summarizer)
    graph.add_node("pf_new_topic_generator", pf_new_topic_generator)
    graph.add_node("session_terminator", session_terminator)


    # ── 엣지 등록 ──────────────────────────────────────────────
    graph.set_entry_point("pf_question_router")

    # router -> conditional edge 분기
    graph.add_conditional_edges(
        "pf_question_router",
        get_pf_route_decision,
        {
            RouteDecision.FOLLOW_UP: "pf_follow_up_generator",
            RouteDecision.NEW_TOPIC: "topic_summarizer",
            RouteDecision.END_SESSION: "session_terminator",
        }
    )

    graph.add_edge("topic_summarizer", "pf_new_topic_generator")

    # 터미널 노드 -> 
    graph.add_edge("pf_follow_up_generator", END)
    graph.add_edge("pf_new_topic_generator", END)
    graph.add_edge("session_terminator", END)   


    return graph

# ── 컴파일된 그래프 싱글턴 ───────────────────────────────────────
# 그래프 컴파일은 10-50ms 소요되므로 싱글턴으로 재사용
_compiled_graph = None


def get_pf_question_graph():
    """컴파일된 포트폴리오 질문 생성 그래프 반환 (싱글턴)"""
    global _compiled_graph
    if _compiled_graph is None:
        graph = build_pf_question_graph()
        _compiled_graph = graph.compile()
        logger.info("Portfolio question graph compiled successfully")
    return _compiled_graph