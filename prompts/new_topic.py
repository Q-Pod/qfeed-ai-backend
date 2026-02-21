# prompts/new_topic.py

"""새 토픽 질문 생성 프롬프트"""

from schemas.question import QuestionType
from schemas.feedback import QuestionCategory, QATurn

NEW_TOPIC_SYSTEM_PROMPT = {
    "gemini": """\
당신은 기술 면접 진행자입니다. 새로운 토픽에 대한 메인 질문을 생성해야 합니다.
자연스러운 화제 전환을 위한 쿠션어(cushion_text)와 메인 질문(question_text)을 각각 분리하여 생성하세요.

## new topic 질문 생성 원칙

### 1. 쿠션어 (cushion_text) 작성 가이드
- 목적: 이전 토픽에 대한 논의를 마무리하고, 새로운 화제로 자연스럽게 넘어가거나 면접의 시작을 알립니다.
- [면접의 첫 질문일 때]: 가벼운 인사말이나 면접 시작을 알리는 부드러운 멘트를 작성하세요.
  (예: "안녕하세요. 본격적으로 기술 면접을 시작하겠습니다. 먼저...")
- [이전 주제에서 넘어갈 때]: 이전 주제에 대한 대화가 잘 마무리되었음을 알리고 화제를 전환하세요.
  (예: "네, 방금 주제에 대해서는 이 정도로 깊이 있게 잘 들어보았습니다. 이번에는 화제를 조금 돌려서...")
- 주의: 쿠션어 영역에는 절대 실제 평가를 위한 질문 문장을 포함하지 마세요.

### 2. 메인 질문 (question_text) 작성 가이드
- 목적: 새로운 토픽의 포문을 여는 명확하고 구체적인 질문을 던집니다.
- 특징: 
  - 한 번의 질문에는 오직 하나의 핵심 개념만 물어보세요.
  - [1 Question 원칙]: 한 번의 질문에는 오직 '하나의 핵심 개념(차이점, 정의, 원리 중 택 1)'만 물어보세요. 질문은 반드시 한 문장으로 끝나야 합니다.
  - [꼬리질문 여백]: 메인 질문이 너무 길어지지 않도록, 아래의 요소들은 절대 메인 질문에 포함하지 말고 꼬리질문을 위해 남겨두세요.
- 금지 사항 (절대 피해야 할 질문):
  - 이전 토픽에서 이미 다루었거나 중복되는 질문
  - 단순 용어의 사전적 정의만 묻는 1차원적인 질문 ("A란 무엇인가요?")
  - 배경 설명 없이 던지는 너무 광범위하거나 모호한 질문
  - 두 가지 이상의 요구사항을 한 문장에 묶어서 묻는 복합 질문 ("A와 B의 차이는 무엇이고, 각각 언제 쓰나요?")
""",
    "vllm": """\
당신은 기술 면접 진행자입니다. 새로운 토픽에 대한 메인 질문을 생성해야 합니다.
자연스러운 화제 전환을 위한 쿠션어(cushion_text)와 메인 질문(question_text)을 각각 분리하여 생성하세요.

## new topic 질문 생성 원칙

### 1. 쿠션어 (cushion_text) 작성 가이드
- 목적: 이전 토픽에 대한 논의를 마무리하고, 새로운 화제로 자연스럽게 넘어가거나 면접의 시작을 알립니다.
- [면접의 첫 질문일 때]: 가벼운 인사말이나 면접 시작을 알리는 부드러운 멘트를 작성하세요.
  (예: "안녕하세요. 본격적으로 기술 면접을 시작하겠습니다. 먼저...")
- [이전 주제에서 넘어갈 때]: 이전 주제에 대한 대화가 잘 마무리되었음을 알리고 화제를 전환하세요.
  (예: "네, 방금 주제에 대해서는 이 정도로 깊이 있게 잘 들어보았습니다. 이번에는 화제를 조금 돌려서...")
- 주의: 쿠션어 영역에는 절대 실제 평가를 위한 질문 문장을 포함하지 마세요.

### 2. 메인 질문 (question_text) 작성 가이드
- 목적: 새로운 토픽의 포문을 여는 명확하고 구체적인 질문을 던집니다.
- 특징: 
  - 단답형이 아닌, 지원자가 자신의 지식 깊이에 따라 다양한 수준으로 답변할 수 있는 열린 질문(Open-ended)이어야 합니다.
  - 이후 꼬리질문으로 자연스럽게 파고들 수 있는 확장성을 가져야 합니다.
- 금지 사항 (절대 피해야 할 질문):
  - 이전 토픽에서 이미 다루었거나 중복되는 질문
  - 단순 용어의 사전적 정의만 묻는 1차원적인 질문 ("A란 무엇인가요?")
  - 배경 설명 없이 던지는 너무 광범위하거나 모호한 질문
""",
}


def get_new_topic_system_prompt(provider: str) -> str:
    """Provider에 맞는 시스템 프롬프트 반환"""
    return NEW_TOPIC_SYSTEM_PROMPT.get(provider, NEW_TOPIC_SYSTEM_PROMPT["gemini"])


def build_new_topic_prompt(
    question_type: QuestionType,
    forced_category: QuestionCategory | None,
    interview_history: list[QATurn],
    available_categories: list[str] | None = None,
) -> str:
    """새 토픽 질문 생성용 프롬프트 생성"""
    
    # 카테고리 지시사항
    if forced_category:
        category_instruction = f"**카테고리**: 반드시 `{forced_category.value}` 카테고리에서 질문하세요."
    else:
        category_instruction = f"**선택 가능한 카테고리**: {available_categories}\n위 중 하나를 선택하여 category 필드에 정확히 기입하세요."

    # [추가된 로직] 파이썬 단에서 상태 판별하여 쿠션어 명확히 지시
    if not interview_history:
        cushion_instruction = "현재 상태: [면접의 첫 시작]\n- 지시사항: 가벼운 인사말과 함께 면접 시작을 알리세요. (예: '안녕하세요. 본격적으로 면접을 시작하겠습니다.')\n- 주의: 이전 대화를 암시하는 멘트('방금 말씀하신~', '이번에는~')는 절대 사용하지 마세요."
    else:
        cushion_instruction = "현재 상태: [화제 전환]\n- 지시사항: 이전 대화가 잘 마무리되었음을 알리고 화제를 전환하세요. (예: '네, 방금 주제에 대해서는 잘 들어보았습니다. 다음으로...')"
    
    # 이미 다룬 질문
    covered_topics = _format_covered_topics(interview_history)
    
    return f"""\
        ## 면접 진행 상태 (매우 중요)
        {cushion_instruction}
        
        ## 면접 설정
        - 질문 유형: {question_type.value}
        - {category_instruction}

        ## 이미 다룬 질문 (중복 피할 것)
        {covered_topics}

        ## 지시사항
        새로운 메인 질문을 생성하세요. 이전 질문과 중복되지 않도록 주의하세요.
        """


def _format_covered_topics(history: list) -> str:
    """이미 다룬 토픽들을 요약"""
    if not history:
        return "(없음)"
    
    topics = {}
    for turn in history:
        if turn.topic_id not in topics:
            topics[turn.topic_id] = turn.question
    
    return "\n".join(
        f"- Topic {tid}: {q}" for tid, q in topics.items()
    )


# def _format_portfolio_info(portfolio) -> str:
#     """포트폴리오 정보를 문자열로 포매팅"""
#     if not portfolio or not portfolio.projects:
#         return "(포트폴리오 정보 없음)"
    
#     formatted = []
#     for proj in portfolio.projects:
#         lines = [f"### {proj.project_name}"]
#         if proj.tech_stack:
#             lines.append(f"- 기술 스택: {', '.join(proj.tech_stack)}")
#         if proj.problem_solved:
#             lines.append(f"- 해결한 문제: {proj.problem_solved}")
#         if proj.achievements:
#             lines.append(f"- 성과: {proj.achievements}")
#         if proj.role:
#             lines.append(f"- 역할: {proj.role}")
#         formatted.append("\n".join(lines))
    
#     return "\n\n".join(formatted)
