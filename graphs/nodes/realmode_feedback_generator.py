# graphs/nodes/feedback_generator_realmode.py

"""실전모드 피드백 텍스트 생성

질문 생성 파이프라인에서 누적된 분석 데이터와 rule-based 루브릭 점수를 기반으로
토픽별 피드백 + 종합 피드백을 생성한다.

기존 feedback_generator와의 차이:
    - LangGraph 노드가 아닌 독립 함수 (실전모드는 그래프 불필요)
    - router_analyses, topic_summaries, rubric_scores를 직접 입력받음
    - 분석이 이미 끝났으므로 LLM은 피드백 텍스트 생성에만 집중
    - 질문 유형별(CS/포트폴리오) 프롬프트 분리
"""
from schemas.feedback_v2 import (
    QATurn, 
    QuestionType,
    RouterAnalysisTurn,
    PortfolioTopicSummaryData,
    CSTopicSummaryData, 
    PortfolioRubricScores,
    CSRubricScores,
    RealModeFeedback,
)
from prompts.feedback_realmode import (
    get_realmode_feedback_system_prompt,
    build_portfolio_realmode_feedback_prompt,
    build_cs_realmode_feedback_prompt,
)
from core.dependencies import get_llm_provider
from core.logging import get_logger
from langfuse import observe

logger = get_logger(__name__)


@observe(name="feedback_generator_realmode", as_type="generation")
async def feedback_generator_realmode(
    interview_history: list[QATurn],
    question_type: QuestionType,
    rubric_scores: PortfolioRubricScores | CSRubricScores,
    router_analyses: list[RouterAnalysisTurn],
    topic_summaries: list[PortfolioTopicSummaryData]
    | list[CSTopicSummaryData]
    | None = None,
) -> dict:
    """실전모드 피드백 생성 (LLM 1회)

    Args:
        interview_history: 전체 면접 히스토리
        question_type: 질문 유형 (CS / PORTFOLIO)
        rubric_scores: rule-based 루브릭 점수
        router_analyses: 매 턴의 라우터 분석 결과
        topic_summaries: 토픽별 요약 (포트폴리오만)

    Returns:
        dict: topics_feedback + overall_feedback
    """

    llm = get_llm_provider("vllm")

    system_prompt = get_realmode_feedback_system_prompt(question_type)

    if question_type == QuestionType.PORTFOLIO:
        user_prompt = build_portfolio_realmode_feedback_prompt(
            interview_history=interview_history,
            rubric_scores=rubric_scores,
            router_analyses=router_analyses,
            topic_summaries=topic_summaries or [],
        )
    else:
        user_prompt = build_cs_realmode_feedback_prompt(
            interview_history=interview_history,
            rubric_scores=rubric_scores,
            router_analyses=router_analyses,
        )

    logger.debug(
        f"Realmode feedback generation | "
        f"question_type={question_type.value} | "
        f"topics={len(set(t.topic_id for t in interview_history))}"
    )

    result = await llm.generate_structured(
        prompt=user_prompt,
        response_model=RealModeFeedback,
        system_prompt=system_prompt,
        temperature=0.5,
        max_tokens=4000,
    )

    logger.info(
        f"Realmode feedback generated | "
        f"topics_count={len(result.topics_feedback)} | "
        f"overall_strengths_len={len(result.overall_feedback.strengths)}"
    )

    return {
        "topics_feedback": result.topics_feedback,
        "overall_feedback": result.overall_feedback,
    }