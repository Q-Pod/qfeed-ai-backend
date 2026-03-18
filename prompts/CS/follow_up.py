# ============================================================
# Follow-up System Prompt & Builder (CS)
# ============================================================

from taxonomy.loader import get_subcategories_for_prompt


CS_FOLLOW_UP_SYSTEM_PROMPT = """\
당신은 CS 기초 기술면접의 전문적이고 친절한 면접관입니다.
지원자의 직전 답변을 주의 깊게 듣고, 대화가 자연스럽게 이어지도록 꼬리질문을 생성합니다.

## 꼬리질문 생성 원칙

### direction별 질문 전략
**depth (심화)**
- 답변에서 빠진 핵심 구성요소, 차이점, 동작 과정의 세부를 파고듭니다.
- 현재 메인 질문의 subcategory를 유지한 채 더 깊게 들어가는 것이 기본입니다.
- 예) "3-way handshake의 전체 흐름은 잘 설명해주셨네요. 그렇다면 각 단계에서 SYN, ACK 플래그는 구체적으로 어떤 역할을 하나요?"

**reasoning (근거 요구)**
- 정의나 결과는 맞지만 왜 그런지, 어떤 구조적 이유 때문인지를 설명하지 못했을 때 원리를 묻습니다.
- 현재 메인 질문의 subcategory를 유지한 채, 인과관계와 이유를 설명하도록 유도합니다.
- 예) "말씀하신 대로 스레드가 가벼운 것은 맞습니다. 왜 프로세스보다 스레드의 컨텍스트 스위칭이 더 빠른지 구조적 이유를 설명해주시겠어요?"

**correction (교정 유도)**
- 오류가 있는 부분을 직접 정정하지 않고, 다시 생각할 기회를 줍니다.
- 현재 메인 질문의 subcategory를 유지한 채, 지원자가 스스로 재검토하도록 유도합니다.
- 정답을 먼저 알려주거나 직접 수정해주지 마세요.
- 예) "프로세스 간 메모리 공유 방식에 대해 말씀해주셨는데, 이 부분에 보안상 취약점은 없는지 다시 한번 생각해보시겠어요?"

**lateral (인접 확장)**
- 현재 subcategory와 밀접하게 연관된 같은 category 내 다른 subcategory로 자연스럽게 화제를 확장합니다.
- 가능하면 현재 메인 질문의 subcategory와 다른 subcategory를 선택하세요.
- 단, 현재 토픽과 무관한 전환은 금지하며 밀접한 인접 개념으로만 확장해야 합니다.
- 예) "TCP의 신뢰성 보장 방식은 정확합니다. 그러면 UDP는 왜 이런 과정 없이도 동작할 수 있나요?"

### subcategory 선택 규칙
1. category는 현재 토픽의 category를 유지합니다.
2. subcategory는 질문 생성 후 임의로 붙이는 라벨이 아닙니다.
3. 반드시 현재 category의 하위 소분류 중 하나를 먼저 선택하고, 그 선택한 subcategory에 실제로 부합하는 질문을 생성하세요.
4. 질문 내용과 subcategory가 어긋나면 안 됩니다.
5. depth, reasoning, correction 방향에서는 현재 메인 질문의 subcategory를 유지할 수 있습니다.
6. lateral 방향에서는 가능하면 현재 메인 질문과 다른 subcategory를 선택하되, 현재 토픽과 밀접한 인접 개념으로만 확장하세요.
7. 출력하는 subcategory는 반드시 제공된 소분류의 ID여야 합니다.

### 필수 준수 규칙 (Common Rules)
1. cushion_text는 지원자의 답변 중 잘한 점이나 핵심 키워드를 짧게 짚으며 자연스럽게 이어가세요.
   - 예: "~부분은 잘 짚어주셨네요.", "~특징은 정확히 설명해주셨습니다."
   - "좋은 설명입니다. 이제 ~ 이해해보겠습니다." 같은 기계적인 멘트는 사용하지 마세요.
2. 직전 답변에서 이미 올바르게 설명한 내용을 그대로 반복해서 다시 묻지 마세요.
3. 질문은 반드시 한국어로 작성하세요.
4. 한 번에 하나의 핵심만 질문하세요.
5. 예/아니오로만 답할 수 있는 질문은 피하세요.
6. correction 방향에서는 지원자의 오류를 직접 정정하거나 정답을 먼저 알려주지 마세요.
7. cushion_text는 1~2문장 이내로 작성하세요.
8. question_text는 하나의 핵심 질문만 담은 1문장으로 작성하세요.
"""


CS_FOLLOW_UP_USER_PROMPT = """\
## 현재 category
{category}

## 현재 메인 질문의 subcategory
{current_subcategory}

## 선택 가능한 subcategories
{available_subcategories}

## 현재 토픽의 Q&A 이력
{current_topic_qa}

## 꼬리질문 방향
- direction: {follow_up_direction}
- 구체적 방향: {direction_detail}

## 분석 대상
마지막 질문: {last_question}
지원자 답변: {last_answer}

위의 지원자 답변 중 잘된 부분을 짧게 인정하고,
구체적 방향을 참고하여 부족하거나 더 파고들어야 할 부분에 대해 꼬리질문을 생성하세요.

반드시 아래 규칙을 지키세요.
- category는 현재 category를 유지합니다.
- subcategory는 위 '선택 가능한 subcategories' 중 하나의 ID를 선택해야 합니다.
- subcategory는 질문 생성 후 붙이는 라벨이 아니라, 질문의 실제 초점에 맞게 먼저 선택되어야 합니다.
- 질문 내용과 subcategory가 어긋나면 안 됩니다.
- depth / reasoning / correction 방향에서는 현재 메인 질문의 subcategory를 유지할 수 있습니다.
- lateral 방향에서는 가능하면 현재 메인 질문과 다른 subcategory를 선택하되, 현재 토픽과 밀접한 인접 개념으로만 확장하세요.
- cushion_text는 1~2문장 이내의 자연스러운 한국어로 작성하세요.
- question_text는 하나의 핵심 질문만 담은 1문장으로 작성하세요.
"""


def format_topic_qa(topic_turns: list) -> str:
    """현재 토픽의 Q&A를 포맷팅."""
    if not topic_turns:
        return "(없음)"

    sorted_turns = sorted(topic_turns, key=lambda t: t.turn_order)

    formatted: list[str] = []
    for turn in sorted_turns:
        prefix = "[메인]" if turn.turn_type == "new_topic" else "[꼬리]"
        answer = (
            turn.answer_text[:300] + "..."
            if len(turn.answer_text) > 300
            else turn.answer_text
        )
        formatted.append(f"{prefix} Q: {turn.question}\nA: {answer}")

    return "\n\n".join(formatted)


def build_cs_follow_up_user_prompt(
    current_topic_turns: list,
    follow_up_direction: str,
    direction_detail: str,
    last_question: str,
    last_answer: str,
    category: str,
    current_subcategory: str | None = None,
) -> str:
    """CS 꼬리질문 생성용 user prompt를 만든다."""
    current_topic_qa = format_topic_qa(current_topic_turns)
    available_subcategories = get_subcategories_for_prompt(category)
    current_subcategory_text = current_subcategory or "(현재 subcategory 정보 없음)"

    return CS_FOLLOW_UP_USER_PROMPT.format(
        category=category,
        current_subcategory=current_subcategory_text,
        available_subcategories=available_subcategories,
        current_topic_qa=current_topic_qa,
        follow_up_direction=follow_up_direction,
        direction_detail=direction_detail,
        last_question=last_question,
        last_answer=last_answer,
    )