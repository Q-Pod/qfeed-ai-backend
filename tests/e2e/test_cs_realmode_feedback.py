# tests/e2e/test_cs_realmode_feedback_e2e.py

"""CS 실전모드 E2E 테스트

면접 세션 결과(interview_history + router_analyses + topic_summaries)를
가상 데이터로 구성하고, 피드백 생성까지 전체 흐름을 테스트한다.

흐름:
    가상 면접 데이터 구성
        ↓
    rubric_scorer (rule-based) → 루브릭 점수 산출
        ↓
    feedback_generator_realmode (LLM) → 토픽별 + 종합 피드백 생성
        ↓
    결과 검증
"""

import pytest
import asyncio
import json

from schemas.feedback import QATurn, QuestionType, InterviewType
from schemas.feedback_v2 import (
    FeedbackRequest,
    RouterAnalysisTurn,
    CSTopicSummaryData,
)
from services.rubric_scorer import score_cs_rubric
from graphs.nodes.realmode_feedback_generator import feedback_generator_realmode


# ============================================================
# 가상 면접 데이터: CS 실전모드 3토픽
# ============================================================

CS_INTERVIEW_HISTORY = [
    # 토픽 1: 프로세스와 스레드
    QATurn(
        question="프로세스와 스레드의 차이점에 대해 설명해주세요.",
        category="OS",
        answer_text="프로세스는 운영체제에서 실행 중인 프로그램의 인스턴스이고, 각각 독립된 메모리 공간을 가집니다. 스레드는 프로세스 내에서 실행되는 흐름의 단위로, 같은 프로세스 내의 스레드들은 힙 메모리를 공유합니다.",
        turn_type="new_topic",
        turn_order=0,
        topic_id=1,
    ),
    QATurn(
        question="스레드가 프로세스보다 컨텍스트 스위칭 비용이 낮은 이유는 무엇인가요?",
        category="OS",
        answer_text="스레드는 같은 프로세스 내에서 메모리 공간을 공유하기 때문에 컨텍스트 스위칭 시 메모리 매핑을 변경할 필요가 없습니다. 반면 프로세스 간 전환은 페이지 테이블을 교체하고 TLB를 플러시해야 해서 비용이 큽니다.",
        turn_type="follow_up",
        turn_order=1,
        topic_id=1,
    ),
    # 토픽 2: TCP와 UDP
    QATurn(
        question="TCP와 UDP의 차이점을 설명해주세요.",
        category="NETWORK",
        answer_text="TCP는 연결 지향적이고 신뢰성을 보장합니다. 3-way handshake로 연결을 수립하고, 순서 보장과 재전송을 지원합니다. UDP는 비연결형이고 신뢰성을 보장하지 않지만 오버헤드가 적어 빠릅니다.",
        turn_type="new_topic",
        turn_order=2,
        topic_id=2,
    ),
    QATurn(
        question="실시간 스트리밍 서비스에서 UDP를 사용하는 이유는 무엇인가요?",
        category="NETWORK",
        answer_text="실시간 스트리밍에서는 약간의 패킷 손실보다 지연이 더 치명적입니다. TCP의 재전송 메커니즘은 지연을 유발하기 때문에, UDP를 사용하고 애플리케이션 레벨에서 필요한 만큼만 오류를 보정하는 게 효율적입니다.",
        turn_type="follow_up",
        turn_order=3,
        topic_id=2,
    ),
    # 토픽 3: 인덱스
    QATurn(
        question="데이터베이스 인덱스가 왜 필요하고, 어떻게 동작하나요?",
        category="DB",
        answer_text="인덱스는 테이블의 검색 속도를 높이기 위한 자료구조입니다. B+Tree 구조를 주로 사용하고, 리프 노드에 실제 데이터 포인터가 있어서 풀 스캔 없이 빠르게 조회할 수 있습니다.",
        turn_type="new_topic",
        turn_order=4,
        topic_id=3,
    ),
    QATurn(
        question="인덱스를 많이 생성하면 어떤 문제가 발생하나요?",
        category="DB",
        answer_text="쓰기 성능이 저하됩니다. INSERT, UPDATE, DELETE 시마다 인덱스도 함께 갱신해야 하니까요. 저장 공간도 추가로 필요하고요.",
        turn_type="follow_up",
        turn_order=5,
        topic_id=3,
    ),
]

CS_ROUTER_ANALYSES = [
    # 토픽 1: 프로세스와 스레드
    RouterAnalysisTurn(
        topic_id=1, turn_order=0, turn_type="new_topic",
        correctness_detail="프로세스와 스레드의 기본 정의는 정확함",
        has_error=False,
        completeness_cs_detail="힙 메모리 공유를 언급했으나 스택은 별도라는 점 미언급",
        has_missing_concepts=True,
        depth_detail="정의 수준의 설명에 그침",
        is_superficial=True,
        is_well_structured=True,
        follow_up_direction="reasoning",
    ),
    RouterAnalysisTurn(
        topic_id=1, turn_order=1, turn_type="follow_up",
        correctness_detail="페이지 테이블, TLB 플러시 언급이 정확함",
        has_error=False,
        completeness_cs_detail="핵심 이유를 잘 설명함",
        has_missing_concepts=False,
        depth_detail="내부 동작 원리까지 설명",
        is_superficial=False,
        is_well_structured=True,
        follow_up_direction=None,
    ),
    # 토픽 2: TCP와 UDP
    RouterAnalysisTurn(
        topic_id=2, turn_order=2, turn_type="new_topic",
        correctness_detail="TCP/UDP 차이 설명 정확",
        has_error=False,
        completeness_cs_detail="3-way handshake, 순서 보장, 재전송 등 핵심 포함",
        has_missing_concepts=False,
        depth_detail="특징 나열에 그치고 내부 동작 설명 부족",
        is_superficial=True,
        is_well_structured=True,
        follow_up_direction="reasoning",
    ),
    RouterAnalysisTurn(
        topic_id=2, turn_order=3, turn_type="follow_up",
        correctness_detail="실시간 스트리밍에서 UDP 사용 이유 정확",
        has_error=False,
        completeness_cs_detail="애플리케이션 레벨 오류 보정까지 언급",
        has_missing_concepts=False,
        depth_detail="트레이드오프를 이해하고 근거를 제시",
        is_superficial=False,
        is_well_structured=True,
        follow_up_direction=None,
    ),
    # 토픽 3: 인덱스
    RouterAnalysisTurn(
        topic_id=3, turn_order=4, turn_type="new_topic",
        correctness_detail="B+Tree 인덱스 설명 정확",
        has_error=False,
        completeness_cs_detail="B+Tree 구조와 리프 노드 포인터 언급",
        has_missing_concepts=False,
        depth_detail="기본 동작 원리를 설명",
        is_superficial=False,
        is_well_structured=True,
        follow_up_direction=None,
    ),
    RouterAnalysisTurn(
        topic_id=3, turn_order=5, turn_type="follow_up",
        correctness_detail="쓰기 성능 저하 설명 정확",
        has_error=False,
        completeness_cs_detail="쓰기 비용과 저장 공간 언급했으나 구체적 수치나 사례 없음",
        has_missing_concepts=True,
        depth_detail="표면적 설명에 그침",
        is_superficial=True,
        is_well_structured=False,
        follow_up_direction="depth",
    ),
]

CS_TOPIC_SUMMARIES = [
    CSTopicSummaryData(
        topic_id=1,
        topic="프로세스와 스레드의 차이",
        key_points=["메모리 공유 구조 설명", "컨텍스트 스위칭 비용 차이를 TLB/페이지 테이블로 설명"],
        gaps=["스택은 스레드별 독립이라는 점 미언급"],
        depth_reached="moderate",
    ),
    CSTopicSummaryData(
        topic_id=2,
        topic="TCP와 UDP 차이",
        key_points=["핵심 특성 차이 정확히 설명", "실시간 스트리밍에서 UDP 선택 이유를 트레이드오프로 설명"],
        gaps=["TCP 내부 흐름 제어/혼잡 제어 미언급"],
        depth_reached="moderate",
    ),
    CSTopicSummaryData(
        topic_id=3,
        topic="데이터베이스 인덱스",
        key_points=["B+Tree 구조와 동작 원리 설명"],
        gaps=["인덱스 과다 생성의 구체적 영향 수치 없음", "복합 인덱스, 커버링 인덱스 미언급"],
        depth_reached="surface",
    ),
]


# ============================================================
# 테스트
# ============================================================

class TestCSRealmodeE2E:
    """CS 실전모드 피드백 E2E 테스트"""

    @pytest.mark.asyncio
    async def test_rubric_scoring(self):
        """rule-based 루브릭 점수 산출 테스트"""

        scores = score_cs_rubric(CS_ROUTER_ANALYSES)

        # 기본 검증: 모든 점수가 1-5 범위
        assert 1 <= scores.correctness <= 5
        assert 1 <= scores.completeness <= 5
        assert 1 <= scores.reasoning <= 5
        assert 1 <= scores.depth <= 5
        assert 1 <= scores.delivery <= 5

        # correctness: has_error가 모두 False → 높아야 함
        assert scores.correctness >= 4

        # delivery: is_well_structured가 대부분 True → 높아야 함
        assert scores.delivery >= 3

        # reasoning: follow_up_direction="reasoning"이 2/6 → 중간
        # reasoning_rate = 1 - 2/6 = 0.67 → 4점
        assert scores.reasoning >= 3

        print(f"\n=== CS Rubric Scores ===")
        print(f"correctness: {scores.correctness}/5")
        print(f"completeness: {scores.completeness}/5")
        print(f"reasoning: {scores.reasoning}/5")
        print(f"depth: {scores.depth}/5")
        print(f"delivery: {scores.delivery}/5")

    @pytest.mark.asyncio
    async def test_feedback_generation(self):
        """실전모드 피드백 생성 E2E 테스트 (LLM 호출 포함)"""

        # Step 1: 루브릭 산출
        scores = score_cs_rubric(CS_ROUTER_ANALYSES)

        # Step 2: 피드백 생성
        result = await feedback_generator_realmode(
            interview_history=CS_INTERVIEW_HISTORY,
            question_type=QuestionType.CS,
            rubric_scores=scores,
            router_analyses=CS_ROUTER_ANALYSES,
            topic_summaries=CS_TOPIC_SUMMARIES,
        )

        # Step 3: 결과 검증
        topics_feedback = result["topics_feedback"]
        overall_feedback = result["overall_feedback"]

        # 토픽별 피드백 3개
        assert len(topics_feedback) == 3

        for tf in topics_feedback:
            assert tf.topic_id in [1, 2, 3]
            assert len(tf.topic_name) > 0
            assert len(tf.strengths) >= 100
            assert len(tf.improvements) >= 100
            assert 1 <= len(tf.action_items) <= 3

        # 종합 피드백
        assert len(overall_feedback.strengths) >= 100
        assert len(overall_feedback.improvements) >= 100
        assert 1 <= len(overall_feedback.action_items) <= 3

        # 결과 출력
        print(f"\n=== CS Realmode Feedback ===")
        print(f"Rubric: {scores}")
        for tf in topics_feedback:
            print(f"\n--- Topic {tf.topic_id}: {tf.topic_name} ---")
            print(f"Strengths: {tf.strengths[:100]}...")
            print(f"Improvements: {tf.improvements[:100]}...")
            print(f"Actions: {tf.action_items}")
        print(f"\n--- Overall ---")
        print(f"Strengths: {overall_feedback.strengths[:100]}...")
        print(f"Improvements: {overall_feedback.improvements[:100]}...")
        print(f"Actions: {overall_feedback.action_items}")


    @pytest.mark.asyncio
    async def test_full_pipeline_via_service(self, fresh_llm_for_inprocess):
        """FeedbackService를 통한 전체 파이프라인 테스트"""
        from services.feedback_service import FeedbackService

        request = FeedbackRequest(
            user_id=1,
            interview_type=InterviewType.REAL_INTERVIEW,
            question_type=QuestionType.CS,
            interview_history=CS_INTERVIEW_HISTORY,
            session_id="test-cs-realmode-001",
            router_analyses=CS_ROUTER_ANALYSES,
            cs_topic_summaries=CS_TOPIC_SUMMARIES,
        )

        service = FeedbackService()
        response = await service.generate_feedback(request)
        # 연결 정리(aclose)가 같은 루프에서 끝나도록 한 번 양보
        await asyncio.sleep(0)

        assert response.message == "feedback_generated"
        assert response.data.metrics is not None
        assert len(response.data.metrics) == 5
        assert response.data.topics_feedback is not None
        assert response.data.overall_feedback is not None

        print(f"\n=== Full Pipeline Response ===")
        print(f"Metrics: {[(m.name, m.score) for m in response.data.metrics]}")
        print(f"Topics: {len(response.data.topics_feedback)}")