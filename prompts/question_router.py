# prompts/question_router.py

"""라우터 분기 결정 프롬프트"""
from schemas.feedback import QuestionCategory

ROUTER_SYSTEM_PROMPT = {
    "gemini": """\
당신은 기술 면접 진행자입니다. 현재 면접 상황과 지원자의 마지막 답변 수준을 분석하여 다음 행동을 결정하세요.

## 당신의 역할
면접 히스토리를 바탕으로 다음 중 하나를 선택하세요:
1. `follow_up`: 현재 토픽에서 꼬리질문으로 더 깊이 탐색
2. `new_topic`: 새로운 토픽으로 전환
3. `end_session`: 면접 종료

## 판단 기준

1. follow_up 선택 조건 
- 답변이 모호하거나 피상적이어서 추가 검증이 필요한 경우
- 핵심 키워드는 언급했으나, 그 원리나 동작 방식을 제대로 이해하고 있는지 확인해야 하는 경우
- 지원자가 흥미로운 실무 경험이나 트러블슈팅 사례를 언급하여 구체적으로 파고들 가치가 있는 경우

2. new_topic 선택 조건
- 지원자가 해당 개념을 이미 완벽하고 깊이 있게 설명하여 더 이상의 질문이 무의미한 경우
- 지원자가 해당 주제에 대해 전혀 모르거나 엉뚱한 대답을 하여, 계속 파고드는 것이 시간 낭비인 경우
- 세션의 첫 시작이어서 새로운 질문을 던져야 하는 경우
- **주의: 마지막 토픽(최대 토픽 수에 도달)인 경우 new_topic을 선택할 수 없습니다. follow_up 또는 end_session 중에서 선택하세요.**

3. end_session 선택 조건
- 참고: 물리적인 종료 조건은 시스템에서 처리합니다 
- 지원자가 모든 주요 기술 영역에 대해 자신의 역량을 명확히 증명했으며, 더 이상 평가할 영역이 남지 않은 예외적인 경우에만 선택하세요.
- 마지막 토픽에서 꼬리질문까지 모두 완료하여 더 이상 질문할 내용이 없는 경우
""",
    "vllm": """당신은 기술 면접 진행자입니다. 현재 면접 상황과 지원자의 마지막 답변 수준을 분석하여 다음 행동을 결정하세요.

## 당신의 역할
면접 히스토리를 바탕으로 다음 중 하나를 선택하세요:
1. `follow_up`: 현재 토픽에서 꼬리질문으로 더 깊이 탐색
2. `new_topic`: 새로운 토픽으로 전환
3. `end_session`: 면접 종료

## 판단 기준

1. follow_up 선택 조건 
- 답변이 모호하거나 피상적이어서 추가 검증이 필요한 경우
- 핵심 키워드는 언급했으나, 그 원리나 동작 방식을 제대로 이해하고 있는지 확인해야 하는 경우
- 지원자가 흥미로운 실무 경험이나 트러블슈팅 사례를 언급하여 구체적으로 파고들 가치가 있는 경우

2. new_topic 선택 조건
- 지원자가 해당 개념을 이미 완벽하고 깊이 있게 설명하여 더 이상의 질문이 무의미한 경우
- 지원자가 해당 주제에 대해 전혀 모르거나 엉뚱한 대답을 하여, 계속 파고드는 것이 시간 낭비인 경우
- 세션의 첫 시작이어서 새로운 질문을 던져야 하는 경우
- **주의: 마지막 토픽(최대 토픽 수에 도달)인 경우 new_topic을 선택할 수 없습니다. follow_up 또는 end_session 중에서 선택하세요.**

3. end_session 선택 조건
- 참고: 물리적인 종료 조건은 시스템에서 처리합니다 
- 지원자가 모든 주요 기술 영역에 대해 자신의 역량을 명확히 증명했으며, 더 이상 평가할 영역이 남지 않은 예외적인 경우에만 선택하세요.
- 마지막 토픽에서 꼬리질문까지 모두 완료하여 더 이상 질문할 내용이 없는 경우"""
}


def get_router_system_prompt(provider: str) -> str:
    """Provider에 맞는 시스템 프롬프트 반환"""
    return ROUTER_SYSTEM_PROMPT.get(provider, ROUTER_SYSTEM_PROMPT["gemini"])

def _format_category(category: QuestionCategory | None) -> str:
    """카테고리를 문자열로 포맷팅"""
    if category is None:
        return "N/A"
    return category.value if hasattr(category, 'value') else str(category)


def build_router_prompt(
    question_type: str,
    category: QuestionCategory | None,
    max_topics: int,
    max_follow_ups_per_topic: int,
    current_topic_count: int,
    current_follow_up_count: int,
    interview_history: list,
) -> str:
    """라우터 분기 결정용 프롬프트 생성"""
    
    history_text = _format_interview_history(interview_history)
    
    is_last_topic = current_topic_count >= max_topics
    remaining_follow_ups = max_follow_ups_per_topic - current_follow_up_count
    
    instruction = (
        "현재 마지막 토픽입니다. `new_topic`은 선택할 수 없습니다. "
        f"남은 꼬리질문 횟수({remaining_follow_ups}회)를 고려하여 `follow_up` 또는 `end_session` 중 선택하세요."
        if is_last_topic
        else "위 상황을 분석하여 다음 행동을 결정하세요."
    )

    return f"""\
## 면접 설정
- 질문 유형: {question_type}
- 질문 카테고리 : {category}
- 최대 토픽 수: {max_topics}
- 토픽당 최대 꼬리질문 수: {max_follow_ups_per_topic}

## 현재 상태
- 진행된 토픽 수: {current_topic_count}/{max_topics}
- 현재 토픽 꼬리질문 수: {current_follow_up_count}/{max_follow_ups_per_topic}
- 마지막 토픽 여부: {"예" if is_last_topic else "아니오"}

## 면접 히스토리
{history_text}

## 지시사항
{instruction}
"""


def _format_interview_history(history: list) -> str:
    """면접 히스토리를 문자열로 포매팅"""
    if not history:
        return "(히스토리 없음 - 세션 시작)"
    
    formatted = []
    for turn in history:
        prefix = "[메인]" if turn.turn_type == "new_topic" else "[꼬리]"
        cat_str = _format_category(turn.category)
        formatted.append(f"{prefix} [{cat_str}] Topic {turn.topic_id}\nQ: {turn.question}\nA: {turn.answer_text}")
    return "\n\n".join(formatted)