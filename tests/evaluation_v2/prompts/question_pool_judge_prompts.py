"""질문 풀 품질 LLM-as-Judge 프롬프트.

평가 방식:
1. 질문별 4개 루브릭 점수 (1-5)
   - relevance
   - specificity
   - depth_potential
   - interview_fit
"""

QUESTION_RUBRIC_SYSTEM = """당신은 시니어 기술면접관입니다.
포트폴리오 맥락에서 생성된 "질문 1개"를 4개 루브릭으로 1~5점 정수 채점하세요.

[채점 원칙]
- 각 루브릭은 독립적으로 채점합니다.
- 애매하면 더 낮은 점수를 선택합니다(상향 관대 채점 금지).
- 골든 질문은 정답지가 아니라 참고 기준입니다(표현 다르면 무조건 감점 금지).
- 출력은 반드시 JSON만 반환합니다.

==================================================
1) relevance (포트폴리오 기반성)
==================================================
5: 포트폴리오의 특정 프로젝트/기술/경험을 정확히 겨냥하고, 질문 전제가 입력 내용과 일치함
4: 포트폴리오 기반이 명확하나 대상 범위가 약간 넓음
3: 주제는 관련 있으나 포트폴리오 근거가 약함(일반론 비중 큼)
2: 포트폴리오와 느슨한 연관만 있고, 외삽/추정이 많음
1: 포트폴리오와 사실상 무관하거나 입력에 없는 기술을 전제함

==================================================
2) specificity (질문의 구체성)
==================================================
5: 단일 맥락에서 "무엇/왜/어떻게"가 분명하고, 답변 근거(수치/설정/사례)를 요구함
4: 비교적 구체적이나 범위/조건 중 하나가 덜 명시적임
3: 의도는 보이지만 질문 범위가 넓거나 추상적 표현이 남아 있음
2: "소개해 주세요", "장단점은?"처럼 범용적이고 막연함
1: 무엇을 묻는지 불명확하거나 모호해서 면접 질문으로 부적합

==================================================
3) depth_potential (깊이 확장 가능성)
==================================================
5: 구현 의사결정, 근거, 트레이드오프, 장애 대응 등으로 자연스럽게 심화 가능
4: 심화 가능성은 높지만 확장 축이 다소 제한적
3: 추가 질문은 가능하나 깊이보다 사실 확인 중심
2: 짧은 답으로 종료되기 쉬운 질문
1: 예/아니오형 또는 단답형으로 끝나는 닫힌 질문

==================================================
4) interview_fit (실전 면접 적합성)
==================================================
5: 실무 의사결정/문제해결 역량을 검증하는 전형적 기술면접 질문
4: 면접에서 충분히 사용 가능하나 약간 교과서적
3: 나쁘진 않지만 실전 면접 효용이 보통 수준
2: 암기/정의 위주로 실무 검증력이 약함
1: 시험문제형 또는 비실무형으로 면접 적합성이 낮음

[추가 규칙]
- specificity <= 2인 경우 interview_fit은 4 이상을 줄 수 없습니다.
- 질문이 포트폴리오 외 기술을 전제하면 relevance는 최대 2점입니다.
- 질문이 닫힌 질문이면 depth_potential은 최대 2점입니다.

반드시 아래 JSON만 출력하세요:
{
  "relevance": <1-5 정수>,
  "specificity": <1-5 정수>,
  "depth_potential": <1-5 정수>,
  "interview_fit": <1-5 정수>,
  "reasoning": "<전체 판단 요약 한두 문장>",
  "metric_reasoning": {
    "relevance": "<근거>",
    "specificity": "<근거>",
    "depth_potential": "<근거>",
    "interview_fit": "<근거>"
  }
}
"""


def _format_projects(portfolio_projects: list[dict]) -> str:
    if not portfolio_projects:
        return "프로젝트 정보 없음"

    lines = []
    for i, project in enumerate(portfolio_projects, 1):
        lines.append(
            (
                f"{i}. {project.get('project_name', '')}\n"
                f"   - tech_stack: {project.get('tech_stack', '')}\n"
                f"   - role: {project.get('role', '')}\n"
                f"   - content: {project.get('content', '')}"
            )
        )
    return "\n".join(lines)


def _format_questions(question_pool: list[dict]) -> str:
    if not question_pool:
        return "질문 없음"

    lines = []
    for q in question_pool:
        qid = q.get("question_id", "?")
        pname = q.get("project_name", "")
        qtext = (q.get("question_text") or "").strip()
        if not qtext:
            continue
        lines.append(f"[{qid}] ({pname}) {qtext}")
    return "\n".join(lines) if lines else "질문 없음"


def build_question_rubric_user_prompt(
    portfolio_projects: list[dict],
    generated_question: dict,
    golden_question_pool: list[dict] | None = None,
) -> str:
    """질문 1개 루브릭 평가용 유저 프롬프트."""
    project_name = generated_question.get("project_name", "")
    question_text = (generated_question.get("question_text") or "").strip()

    golden_block = ""
    if golden_question_pool:
        golden_block = (
            "\n[참고용 시니어 골든 질문 풀]\n"
            f"{_format_questions(golden_question_pool)}\n"
        )

    return (
        "[포트폴리오 프로젝트]\n"
        f"{_format_projects(portfolio_projects)}\n\n"
        "[평가 대상 질문]\n"
        f"- project_name: {project_name}\n"
        f"- question_text: {question_text}\n"
        f"{golden_block}"
        "\n위 질문을 relevance/specificity/depth_potential/interview_fit 기준으로 채점하세요."
    )
