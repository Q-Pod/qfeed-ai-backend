from schemas.feedback import QATurn, QuestionCategory, QuestionType


CS_PRACTICE_ANALYSIS_SYSTEM_PROMPT = """\
당신은 CS 기술면접 답변 분석기입니다.
지원자의 답변 자체만 평가하고, 다음 질문 방향은 판단하지 마세요.

다음 기준으로 마지막 답변 1개를 분석하세요.

1. 정확성(correctness): 사실적 오류가 있는가
2. 완성도(completeness): 핵심 개념이 빠졌는가
3. 깊이(depth): 정의만 말했는지, 원리까지 설명했는가
4. 전달력(is_well_structured): 논리적 순서로 전달되었는가

중요 규칙:
- has_error는 명백한 기술 오개념이 있을 때만 true
- has_missing_concepts는 질문의 핵심 구성요소가 빠졌을 때만 true
- is_superficial은 정의/암기 수준에 머물렀을 때만 true
- correctness/completeness/depth는 각각 1~2문장으로 간결하게 작성하세요
- 출력은 주어진 스키마 필드만 채우세요"""


PF_PRACTICE_ANALYSIS_SYSTEM_PROMPT = """\
당신은 포트폴리오 기술면접 답변 분석기입니다.
지원자의 답변 자체만 평가하고, 다음 질문 방향은 판단하지 마세요.

다음 기준으로 마지막 답변 1개를 분석하세요.

1. 완성도(completeness): 질문의 핵심을 짚었는가
2. 근거(has_evidence): 수치, 사례, 실제 경험이 있는가
3. 트레이드오프(has_tradeoff): 장단점이나 대안 비교가 있는가
4. 문제해결(has_problem_solving): 문제 상황과 해결 과정이 있는가
5. 전달력(is_well_structured): 논리적 순서로 전달되었는가

중요 규칙:
- completeness는 1~2문장으로 간결하게 작성하세요
- 질문에서 요구하지 않은 내용을 추측해서 채우지 마세요
- 출력은 주어진 스키마 필드만 채우세요"""


def get_practice_analysis_system_prompt(question_type: QuestionType) -> str:
    if question_type == QuestionType.PORTFOLIO:
        return PF_PRACTICE_ANALYSIS_SYSTEM_PROMPT
    return CS_PRACTICE_ANALYSIS_SYSTEM_PROMPT


def build_practice_answer_analysis_prompt(
    question_type: QuestionType,
    interview_history: list[QATurn],
    category: QuestionCategory | None = None,
) -> str:
    last_turn = interview_history[-1]
    current_topic_turns = [
        turn for turn in interview_history if turn.topic_id == last_turn.topic_id
    ]
    current_topic_qa = _format_current_topic_qa(current_topic_turns)
    category_str = _format_category(category or getattr(last_turn, "category", None))

    return f"""\
## 질문 정보
- 질문 유형: {question_type.value}
- 카테고리: {category_str}
- 토픽 ID: {last_turn.topic_id}
- 턴 순서: {last_turn.turn_order}
- 턴 유형: {last_turn.turn_type}

## 현재 토픽 Q&A 이력
{current_topic_qa}

## 최종 분석 대상
질문: {last_turn.question}
답변: {last_turn.answer_text}

위 마지막 답변만 분석하세요. 이전 턴은 문맥 참고용입니다."""


def _format_current_topic_qa(turns: list[QATurn]) -> str:
    lines = []
    for turn in sorted(turns, key=lambda item: item.turn_order):
        turn_label = "꼬리질문" if turn.turn_type == "follow_up" else "메인질문"
        lines.append(f"[{turn_label}] Q: {turn.question}\nA: {turn.answer_text}")

    return "\n\n".join(lines) if lines else "이 토픽의 이전 Q&A가 없습니다."


def _format_category(category: QuestionCategory | None) -> str:
    if category is None:
        return "N/A"
    return category.value if hasattr(category, "value") else str(category)
