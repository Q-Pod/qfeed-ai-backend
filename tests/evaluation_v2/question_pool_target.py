"""Evaluation target - 포트폴리오 질문 풀 생성 파이프라인 실행

run_experiment의 task 파라미터로 전달되어, 각 golden dataset item에 대해
PortfolioAnalysisService를 실행하고 evaluator가 소비할 형태로 결과를 반환한다.

반환 형태:
    {
        "user_id": int,
        "portfolio_summary": str,
        "portfolio_projects": list[dict],
        "generated_question_pool": list[dict],
        "question_count": int,
    }
"""

from schemas.portfolio import Portfolio, PortfolioAnalysisRequest
from services.portfolio_analysis_service import PortfolioAnalysisService


def _to_project_dicts(portfolio: Portfolio) -> list[dict]:
    """Judge 입력으로 사용할 프로젝트 정보를 dict 리스트로 변환한다."""
    projects: list[dict] = []
    for p in portfolio.projects:
        projects.append(
            {
                "project_name": p.project_name,
                "tech_stack": p.tech_stack,
                "content": p.content,
                "role": p.role,
            }
        )
    return projects


async def question_pool_eval_task(*, item, **kwargs) -> dict:
    """Langfuse experiment task: 포트폴리오 분석 실행 후 evaluator용 dict 반환"""
    input_data = item.input if hasattr(item, "input") else item["input"]

    request = PortfolioAnalysisRequest(
        user_id=input_data["user_id"],
        portfolio=Portfolio(**input_data["portfolio"]),
    )

    service = PortfolioAnalysisService()
    response = await service.analyze_portfolio(request)

    generated_question_pool = [
        {
            "question_id": q.question_id,
            "project_name": q.project_name,
            "question_text": q.question_text,
        }
        for q in response.question_pool
    ]

    return {
        "user_id": request.user_id,
        "portfolio_summary": response.portfolio_summary,
        "portfolio_projects": _to_project_dicts(request.portfolio),
        "generated_question_pool": generated_question_pool,
        "question_count": len(generated_question_pool),
    }
