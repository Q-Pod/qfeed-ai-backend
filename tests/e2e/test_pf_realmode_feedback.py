# tests/e2e/test_portfolio_realmode_e2e.py

"""포트폴리오 실전모드 E2E 테스트

전체 흐름을 시뮬레이션:
    1. 포트폴리오 분석 API → portfolio_summary + question_pool 생성
    2. 면접 세션 시뮬레이션: 질문 생성 → LLM 가상 답변 → 반복
    3. 세션 완료 후 피드백 생성

가상 답변은 LLM(Gemini)이 지원자 역할로 생성하여 현실적인 테스트 수행.
"""

import pytest
import json

from schemas.feedback import QATurn, QuestionType
from schemas.feedback_v2 import (
    FeedbackRequest,
    RouterAnalysisTurn,
    PortfolioTopicSummaryData,
)
from schemas.question import (
    QuestionGenerateRequest,
    PoolQuestion,
)
from schemas.portfolio import PortfolioAnalysisRequest, Portfolio, PortfolioProject
from services.portfolio_analysis_service import PortfolioAnalysisService
from services.feedback_service import FeedbackService
from services.rubric_scorer import score_portfolio_rubric
from graphs.nodes.realmode_feedback_generator import feedback_generator_realmode
from core.dependencies import get_llm_provider
from core.logging import get_logger

logger = get_logger(__name__)


# ============================================================
# 가상 포트폴리오 데이터
# ============================================================

SAMPLE_PORTFOLIO = Portfolio(
    projects=[
        PortfolioProject(
            project_name="FoodDelivery",
            tech_stack="Spring Boot, PostgreSQL, Redis, Docker, AWS EC2",
            arch_image_url=None,
            content=(
                "음식 배달 플랫폼 백엔드 서비스를 개발했습니다. "
                "주문 동시성 처리 문제와 메뉴 조회 성능 병목이 주요 기술적 도전이었습니다. "
                "Redis 분산 락과 비관적 락을 조합하여 재고 불일치 문제를 해결했고, "
                "Cache-Aside 패턴으로 Redis 캐시를 도입하여 메뉴 조회 성능을 개선했습니다. "
                "주문 처리 응답시간을 40% 개선했으며, 동시 주문 처리량 초당 500건을 달성했습니다."
            ),
            role="백엔드 개발자 (3인 팀)",
        ),
        PortfolioProject(
            project_name="StudyMate",
            tech_stack="Spring Boot, MySQL, WebSocket, FCM",
            arch_image_url=None,
            content=(
                "스터디 그룹 매칭 서비스를 1인 프로젝트로 개발했습니다. "
                "다차원 유사도 기반 매칭 알고리즘으로 매칭 성공률을 78%로 개선했습니다. "
                "WebSocket 기반 실시간 채팅과 FCM 푸시 알림 시스템을 구축했습니다."
            ),
            role="풀스택 개발자 (1인)",
        ),
    ]
)


# ============================================================
# LLM 가상 답변 생성기
# ============================================================

async def generate_fake_answer(question: str, portfolio_summary: str) -> str:
    """LLM으로 가상 지원자 답변 생성

    Gemini에게 "기술면접 지원자 역할"로 답변을 생성하게 한다.
    완벽한 답변이 아니라, 현실적인 수준의 답변을 생성하도록 프롬프트를 설계.
    """

    llm = get_llm_provider("gemini")

    prompt = f"""\
당신은 기술면접에 참여한 주니어 백엔드 개발자입니다.
아래 포트폴리오 정보를 참고하여 면접 질문에 답변하세요.

## 답변 가이드
- 완벽하지 않아도 됩니다. 실제 주니어 개발자 수준으로 답변하세요.
- 일부러 모든 것을 다 설명하지 마세요. 빠뜨리는 부분이 있어야 자연스럽습니다.
- 구체적 수치는 일부만 포함하세요.
- 3-5문장 정도로 답변하세요.

## 포트폴리오
{portfolio_summary}

## 질문
{question}

위 질문에 대해 답변하세요. 답변만 출력하세요."""

    response = await llm.generate(
        prompt=prompt,
        response_model=type("Dummy", (), {"__name__": "FakeAnswer"}),
        temperature=0.7,
        max_tokens=500,
    )

    return response


async def generate_fake_answer_simple(
    question: str, portfolio_summary: str
) -> str:
    """간단한 가상 답변 생성 (generate_structured 대신 직접 호출)"""

    from google import genai
    from google.genai import types
    from core.config import get_settings

    settings = get_settings()
    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    prompt = f"""\
당신은 기술면접에 참여한 주니어 백엔드 개발자입니다.
포트폴리오를 참고하여 면접 질문에 3-5문장으로 답변하세요.
완벽하지 않아도 됩니다. 실제 주니어 수준으로 답변하세요.
일부 내용을 빠뜨려도 자연스럽습니다.

포트폴리오: {portfolio_summary}

질문: {question}

답변:"""

    response = await client.aio.models.generate_content(
        model=settings.GEMINI_MODEL_ID,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.7,
            max_output_tokens=500,
        ),
    )

    return response.text.strip()


# ============================================================
# 면접 세션 시뮬레이터
# ============================================================

async def simulate_interview_session(
    portfolio_summary: str,
    question_pool: list[dict],
    max_topics: int = 2,
    max_follow_ups: int = 2,
) -> dict:
    """포트폴리오 면접 세션을 시뮬레이션

    실제 API 호출 대신 질문 생성 그래프를 직접 실행하고,
    LLM으로 가상 답변을 생성하여 면접 세션을 진행.

    Returns:
        dict: interview_history, router_analyses, topic_summaries
    """
    from graphs.question.state import create_initial_state
    from graphs.question.question_graph import run_question_pipeline

    interview_history: list[QATurn] = []
    router_analyses: list[RouterAnalysisTurn] = []
    topic_summaries: list[PortfolioTopicSummaryData] = []

    # 첫 질문은 풀에서 선택 (백엔드가 하는 역할 시뮬레이션)
    first_question = question_pool[0]
    current_topic_id = 1
    turn_order = 0

    # 첫 질문에 대한 가상 답변
    first_answer = await generate_fake_answer_simple(
        first_question["question_text"], portfolio_summary
    )

    interview_history.append(
        QATurn(
            question=first_question["question_text"],
            category="PORTFOLIO",
            answer_text=first_answer,
            turn_type="new_topic",
            turn_order=turn_order,
            topic_id=current_topic_id,
        )
    )
    turn_order += 1

    print(f"\n{'='*60}")
    print(f"[토픽 {current_topic_id}] 메인: {first_question['question_text'][:60]}...")
    print(f"[답변] {first_answer[:80]}...")

    # 면접 세션 루프
    session_ended = False
    while not session_ended:
        # 질문 생성 요청
        state = create_initial_state(
            user_id=1,
            session_id="test-pf-e2e",
            question_type=QuestionType.PORTFOLIO,
            interview_history=interview_history,
            portfolio_summary=portfolio_summary,
            question_pool=question_pool,
            max_topics=max_topics,
            max_follow_ups_per_topic=max_follow_ups,
        )

        # 기존 topic_summaries를 state에 주입
        state["topic_summaries"] = [
            {
                "topic_id": s.topic_id,
                "topic": s.topic,
                "key_points": s.key_points,
                "gaps": s.gaps,
                "depth_reached": s.depth_reached,
                "technologies_mentioned": s.technologies_mentioned,
                "transition_reason": "",
            }
            for s in topic_summaries
        ]

        result = await run_question_pipeline(state)

        generated = result.get("generated_question")
        if generated is None:
            print("[ERROR] generated_question is None")
            break

        # 세션 종료 체크
        if generated.is_session_ended:
            print(f"\n[세션 종료] {generated.end_reason}")
            session_ended = True
            break

        # router_analysis 수집
        router_analysis = result.get("router_analysis")
        if router_analysis:
            router_analyses.append(
                RouterAnalysisTurn(
                    topic_id=generated.topic_id,
                    turn_order=turn_order - 1,  # 이전 답변에 대한 분석
                    turn_type=interview_history[-1].turn_type,
                    completeness_detail=router_analysis.get("completeness"),
                    has_evidence=router_analysis.get("has_evidence"),
                    has_tradeoff=router_analysis.get("has_tradeoff"),
                    has_problem_solving=router_analysis.get("has_problem_solving"),
                    is_well_structured=router_analysis.get("is_well_structured"),
                    follow_up_direction=result.get("follow_up_direction"),
                )
            )

        # topic_summaries 수집
        new_summaries = result.get("topic_summaries", [])
        if len(new_summaries) > len(topic_summaries):
            latest = new_summaries[-1]
            topic_summaries.append(
                PortfolioTopicSummaryData(
                    topic_id=latest["topic_id"],
                    topic=latest["topic"],
                    key_points=latest.get("key_points", []),
                    gaps=latest.get("gaps", []),
                    depth_reached=latest.get("depth_reached", "surface"),
                    technologies_mentioned=latest.get("technologies_mentioned", []),
                )
            )

        # 생성된 질문에 가상 답변
        fake_answer = await generate_fake_answer_simple(
            generated.question_text, portfolio_summary
        )

        interview_history.append(
            QATurn(
                question=generated.question_text,
                category="PORTFOLIO",
                answer_text=fake_answer,
                turn_type=generated.turn_type,
                turn_order=turn_order,
                topic_id=generated.topic_id,
            )
        )

        turn_label = "꼬리" if generated.turn_type == "follow_up" else "메인"
        print(f"\n[토픽 {generated.topic_id}] {turn_label}: {generated.question_text[:60]}...")
        print(f"[답변] {fake_answer[:80]}...")

        turn_order += 1

        # 안전장치: 무한루프 방지
        if turn_order > 20:
            print("[WARNING] Turn limit reached")
            break

    return {
        "interview_history": interview_history,
        "router_analyses": router_analyses,
        "topic_summaries": topic_summaries,
    }


# ============================================================
# 테스트
# ============================================================

class TestPortfolioRealmodeE2E:
    """포트폴리오 실전모드 전체 흐름 E2E 테스트"""

    @pytest.mark.asyncio
    async def test_portfolio_analysis(self, fresh_llm_for_inprocess):
        """Step 1: 포트폴리오 분석 → 요약 + 질문 풀 생성"""

        service = PortfolioAnalysisService()
        request = PortfolioAnalysisRequest(
            user_id=1,
            portfolio=SAMPLE_PORTFOLIO,
        )

        response = await service.analyze_portfolio(request)

        assert len(response.portfolio_summary) > 100
        assert len(response.question_pool) >= 4
        assert all(q.question_id > 0 for q in response.question_pool)
        assert all(len(q.question_text) > 10 for q in response.question_pool)

        print(f"\n=== Portfolio Analysis ===")
        print(f"Summary length: {len(response.portfolio_summary)}")
        print(f"Questions: {len(response.question_pool)}")
        for q in response.question_pool:
            print(f"  [{q.question_id}] {q.project_name}: {q.question_text[:50]}...")

    @pytest.mark.asyncio
    async def test_full_flow(self, fresh_llm_for_inprocess):
        """전체 흐름: 포트폴리오 분석 → 면접 시뮬레이션 → 피드백 생성"""

        # Step 1: 포트폴리오 분석
        print("\n" + "=" * 60)
        print("STEP 1: 포트폴리오 분석")
        print("=" * 60)

        analysis_service = PortfolioAnalysisService()
        analysis_response = await analysis_service.analyze_portfolio(
            PortfolioAnalysisRequest(user_id=1, portfolio=SAMPLE_PORTFOLIO)
        )

        portfolio_summary = analysis_response.portfolio_summary
        question_pool = [
            {
                "question_id": q.question_id,
                "project_name": q.project_name,
                "question_text": q.question_text,
            }
            for q in analysis_response.question_pool
        ]

        print(f"Summary: {portfolio_summary[:100]}...")
        print(f"Question pool: {len(question_pool)} questions")

        # Step 2: 면접 세션 시뮬레이션
        print("\n" + "=" * 60)
        print("STEP 2: 면접 세션 시뮬레이션")
        print("=" * 60)

        session_result = await simulate_interview_session(
            portfolio_summary=portfolio_summary,
            question_pool=question_pool,
            max_topics=2,
            max_follow_ups=2,
        )

        interview_history = session_result["interview_history"]
        router_analyses = session_result["router_analyses"]
        topic_summaries = session_result["topic_summaries"]

        print(f"\nSession completed:")
        print(f"  Total turns: {len(interview_history)}")
        print(f"  Router analyses: {len(router_analyses)}")
        print(f"  Topic summaries: {len(topic_summaries)}")

        # Step 3: 피드백 생성
        print("\n" + "=" * 60)
        print("STEP 3: 피드백 생성")
        print("=" * 60)

        # 루브릭 산출
        rubric_scores = score_portfolio_rubric(router_analyses)
        print(f"\nRubric scores:")
        for m in rubric_scores.to_metrics_list():
            print(f"  {m['name']}: {m['score']}/5")

        # 피드백 생성
        feedback_result = await feedback_generator_realmode(
            interview_history=interview_history,
            question_type=QuestionType.PORTFOLIO,
            rubric_scores=rubric_scores,
            router_analyses=router_analyses,
            topic_summaries=topic_summaries,
        )

        topics_feedback = feedback_result["topics_feedback"]
        overall_feedback = feedback_result["overall_feedback"]

        print(f"\nTopics feedback: {len(topics_feedback)} topics")
        for tf in topics_feedback:
            print(f"\n--- Topic {tf.topic_id}: {tf.topic_name} ---")
            print(f"Strengths: {tf.strengths[:100]}...")
            print(f"Improvements: {tf.improvements[:100]}...")
            print(f"Actions: {tf.action_items}")

        print(f"\n--- Overall ---")
        print(f"Strengths: {overall_feedback.strengths[:100]}...")
        print(f"Improvements: {overall_feedback.improvements[:100]}...")
        print(f"Actions: {overall_feedback.action_items}")

        # 기본 검증
        assert len(topics_feedback) >= 1
        assert len(overall_feedback.strengths) >= 100
        assert len(overall_feedback.action_items) >= 1