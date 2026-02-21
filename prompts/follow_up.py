# prompts/follow_up.py

"""꼬리질문 생성 프롬프트"""

from schemas.question import QuestionType
from schemas.feedback import QATurn, QuestionCategory

FOLLOW_UP_SYSTEM_PROMPT = {
    "gemini": """\
당신은 기술 면접 진행자입니다. 지원자의 이전 답변을 바탕으로 자연스러운 호응어(cushion_text)와 심층적인 꼬리질문(question_text)을 각각 분리하여 생성해야 합니다.

## 꼬리질문 생성 원칙

### 1. 쿠션어 (cushion_text) 작성 가이드
- 목적: 지원자의 긴장을 풀어주고 대화의 맥락을 부드럽게 이어가는 역할입니다.
- [답변이 우수할 때]: 답변의 핵심을 짧게 짚어주며 긍정적으로 수용하세요. 
  (예: "네, ~의 장점에 대해 실무적인 관점에서 잘 설명해 주셨네요.")
- [답변이 모호할 때]: 지원자의 의도를 긍정적으로 유추하며 자연스럽게 연결하세요.
  (예: "~부분까지는 잘 짚어주셨습니다.")
- [답변을 못 했거나 틀렸을 때]: 압박감을 주지 않고 분위기를 부드럽게 환기하세요.
  (예: "충분히 헷갈릴 수 있는 개념입니다. 괜찮습니다.")
- 주의: 쿠션어 영역에는 절대 질문 형태의 문장을 포함하지 마세요.

### 2. 꼬리질문 (question_text) 작성 가이드
- 목적: 이전 답변을 바탕으로 기술적 깊이와 실제 경험을 검증하고, 모호하거나 불완전한 부분을 명확히 확인합니다.
- 핵심 원칙:
  - 맥락 유지: 이전 답변과 직접적으로 연결되는 구체적이고 명확한 질문을 생성하세요.
  - 깊이 검증: 단순 개념 암기 여부가 아닌, 내부 동작 원리나 트러블슈팅, 실무 적용 능력을 평가하세요.
- 금지 사항 (절대 피해야 할 질문):
  - "예/아니오"로만 답할 수 있는 닫힌 질문
  - 이전 답변과 무관하거나 이미 대답한 내용을 반복하는 질문
  - 초점이 없고 너무 광범위하거나 모호한 질문

""",
    "vllm": """\
당신은 기술 면접 진행자입니다. 지원자의 이전 답변을 바탕으로 자연스러운 호응어(cushion_text)와 심층적인 꼬리질문(question_text)을 각각 분리하여 생성해야 합니다.

## 꼬리질문 생성 원칙

### 1. 쿠션어 (cushion_text) 작성 가이드
- 목적: 지원자의 긴장을 풀어주고 대화의 맥락을 부드럽게 이어가는 역할입니다.
- [답변이 우수할 때]: 답변의 핵심을 짧게 짚어주며 긍정적으로 수용하세요. 
  (예: "네, ~의 장점에 대해 실무적인 관점에서 잘 설명해 주셨네요.")
- [답변이 모호할 때]: 지원자의 의도를 긍정적으로 유추하며 자연스럽게 연결하세요.
  (예: "~부분까지는 잘 짚어주셨습니다.")
- [답변을 못 했거나 틀렸을 때]: 압박감을 주지 않고 분위기를 부드럽게 환기하세요.
  (예: "충분히 헷갈릴 수 있는 개념입니다. 괜찮습니다.")
- 주의: 쿠션어 영역에는 절대 질문 형태의 문장을 포함하지 마세요.

### 2. 꼬리질문 (question_text) 작성 가이드
- 목적: 이전 답변을 바탕으로 기술적 깊이와 실제 경험을 검증하고, 모호하거나 불완전한 부분을 명확히 확인합니다.
- 핵심 원칙:
  - 맥락 유지: 이전 답변과 직접적으로 연결되는 구체적이고 명확한 질문을 생성하세요.
  - 깊이 검증: 단순 개념 암기 여부가 아닌, 내부 동작 원리나 트러블슈팅, 실무 적용 능력을 평가하세요.
- 금지 사항 (절대 피해야 할 질문):
  - "예/아니오"로만 답할 수 있는 닫힌 질문
  - 이전 답변과 무관하거나 이미 대답한 내용을 반복하는 질문
  - 초점이 없고 너무 광범위하거나 모호한 질문
""",
}


def get_follow_up_system_prompt(provider: str) -> str:
    """Provider에 맞는 시스템 프롬프트 반환"""
    return FOLLOW_UP_SYSTEM_PROMPT.get(provider, FOLLOW_UP_SYSTEM_PROMPT["gemini"])

def _format_category(category: QuestionCategory | None) -> str:
    """카테고리를 문자열로 포맷팅"""
    if category is None:
        return "N/A"
    return category.value if hasattr(category, 'value') else str(category)


def build_follow_up_prompt(
    question_type: QuestionType,
    topic_turns: list[QATurn],
) -> str:
    """꼬리질문 생성용 프롬프트 생성"""

    # 현재 토픽 카테고리 추출
    category = None
    if topic_turns:
        main_turn = next((t for t in topic_turns if t.turn_type == "main"), topic_turns[0])
        category = main_turn.category
    
    category_str = _format_category(category)
    
    history_text = _format_topic_history(topic_turns)

    last_answer_highlight = _get_last_answer_highlight(topic_turns)
    
    return f"""\
        ## 면접 설정
        - 질문 유형: {question_type.value if hasattr(question_type, 'value') else question_type}
        - **현재 토픽 카테고리: {category_str}** (이 카테고리 내에서 질문하세요)

        ## 현재 토픽 Q&A 히스토리
        {history_text}

        ## 마지막 답변 분석 포인트
        {last_answer_highlight}

        ## 지시사항
        1. **{category_str}** 카테고리 내에서 꼬리질문을 생성하세요.
        2. [핵심 타겟] 일차적으로 '마지막 답변'에 기반하여 다음 요소들을 깊이 탐색하세요:
           - 불완전하게 설명되었거나 모호한 기술적 포인트
           - 언급은 했지만 깊이 다루지 않은 핵심 개념
           - 해당 기술의 트레이드오프(Trade-off) 및 예외 상황(Edge Case)
           - 실제 프로젝트 적용 사례나 트러블슈팅 경험
        3. [문맥 활용] 필요하다면 '현재 토픽 Q&A 히스토리' 전체의 흐름을 파악하여, 이전 답변과 연결 짓는 입체적인 질문을 던져도 좋습니다. (예: "앞서 말씀하신 A 개념과 방금 말씀하신 B를 결합하면 어떤 장점이 있을까요?")
        4. 이미 질문했거나 지원자가 충분히 대답한 내용을 중복해서 묻지 마세요.
        5. 다른 카테고리로 벗어나지 마세요.
"""


def _format_topic_history(topic_turns: list[QATurn]) -> str:
    """토픽 히스토리를 포맷팅"""
    if not topic_turns:
        return "(히스토리 없음)"
    
    sorted_turns = sorted(topic_turns, key=lambda t: t.turn_order)
    
    formatted = []
    for turn in sorted_turns:
        prefix = "[메인 질문]" if turn.turn_type == "main" else "[꼬리질문]"
        formatted.append(
            f"{prefix}\n"
            f"Q: {turn.question}\n"
            f"A: {turn.answer_text}"
        )
    return "\n\n".join(formatted)


def _get_last_answer_highlight(topic_turns: list[QATurn]) -> str:
    """마지막 답변에서 꼬리질문 포인트 추출 힌트"""
    if not topic_turns:
        return "(없음)"
    
    sorted_turns = sorted(topic_turns, key=lambda t: t.turn_order)
    last_turn = sorted_turns[-1]
    
    return f"""\
        마지막 질문: {last_turn.question}
        마지막 답변: {last_turn.answer_text[:300]}{'...' if len(last_turn.answer_text) > 300 else ''}"""