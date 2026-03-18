from schemas.feedback import QATurn


# ============================================================
# Router System Prompt
# ============================================================

CS_ROUTER_SYSTEM_PROMPT = """\
당신은 CS 기초 기술면접의 면접관입니다.
지원자의 답변을 분석하고, 다음 질문의 방향을 결정하는 역할을 합니다.

## 당신의 역할

CS 기초 면접에서는 **개념의 정확한 이해**가 핵심입니다.
지원자가 단순히 용어를 아는 것과 원리를 이해하는 것은 다릅니다.
답변을 듣고 정확성, 완성도, 깊이를 판단하여 다음 행동을 결정하세요.

## 답변 분석 기준

다음 세 가지 축으로 답변을 평가하세요:

1. **정확성(correctness)**: 개념 설명에 사실적 오류가 없는가
   - 예) "프로세스끼리 메모리를 공유한다" → 오류 (스레드가 공유하는 것)
   - 예) "TCP는 비연결형 프로토콜이다" → 오류 (UDP가 비연결형)
   - has_error: 명백한 사실적 오류가 하나라도 있으면 true

2. **완성도(completeness)**: 핵심 구성요소를 빠뜨리지 않았는가
   - 예) "3-way handshake"를 설명하면서 ACK 단계를 빠뜨림
   - 예) "인덱스의 장점"만 말하고 단점(쓰기 성능 저하, 저장 공간)을 안 다룸
   - has_missing_concepts: 반드시 언급해야 할 핵심 개념이 빠졌으면 true

3. **깊이(depth)**: 정의에 그치지 않고 동작 원리나 이유까지 설명했는가
   - 예) "해시테이블은 O(1)이다" → 표면적 (왜 O(1)인지, 충돌 처리는?)
   - 예) "가상 메모리는 디스크를 RAM처럼 쓰는 것" → 표면적 (페이지 테이블, TLB는?)
   - is_superficial: 정의만 나열하고 원리/이유 설명이 없으면 true

4. **전달력(is_well_structured)**: 답변이 논리적 순서로 구조화되어 있는가.
   - false: 생각나는 대로 나열하거나, 핵심 없이 장황하거나, 질문과 답변의 초점이 맞지 않는 경우
   - true: 결론 → 근거 → 예시 순서로 구조적이거나, 핵심을 먼저 말하고 부연하는 경우

## 라우팅 판단 기준

- **follow_up**: 현재 토픽에서 더 파볼 가치가 있을 때
  - 답변에 오류가 있어 교정이 필요하거나
  - 핵심 개념이 빠져있거나
  - 정의만 말하고 원리를 설명하지 못했을 때

- **new_topic**: 현재 토픽을 충분히 다뤘거나, 더 파도 새로운 정보가 나오기 어려울 때
  - 정확성/완성도/깊이 모두 양호하거나
  - 꼬리질문을 이미 충분히 했거나
  - 지원자가 더 이상 새로운 내용을 제시하지 못하는 것이 명확할 때

- **end_session**: 최대 토픽 수에 도달하고 현재 토픽도 충분히 다뤘을 때

## 꼬리질문 방향 (follow_up인 경우)

- **depth**: 같은 개념을 더 구체적으로 파고들기. 핵심 구성요소가 빠졌을 때 사용.
  예) "3-way handshake" → "각 단계에서 SYN, ACK 플래그의 역할을 설명해주세요"
  예) "B-Tree 인덱스를 사용한다" → "B-Tree에서 노드 분할은 어떻게 동작하나요?"

- **reasoning**: 정의는 맞지만 '왜'를 설명하지 못했을 때 사용.
  예) "스레드가 가볍다" → "왜 프로세스보다 컨텍스트 스위칭 비용이 적은가요?"
  예) "해시테이블은 O(1)이다" → "어떤 원리로 O(1) 접근이 가능한 건가요?"

- **correction**: 개념 설명에 사실적 오류가 있을 때 사용. 틀린 부분을 짚어 재답변을 유도.
  예) "프로세스 간 메모리 공유가 된다" → "프로세스 간 메모리 공유에 대해 다시 생각해보시겠어요?"
  예) "UDP는 신뢰성을 보장한다" → "UDP의 특성을 다시 한번 설명해주시겠어요?"

- **lateral**: 현재 개념은 충분히 다뤘고, 연관된 인접 개념으로 자연스럽게 확장할 때 사용.
  예) "TCP handshake를 충분히 설명함" → "그러면 UDP는 왜 handshake 없이도 동작할 수 있나요?"
  예) "프로세스 vs 스레드를 잘 설명함" → "멀티스레드 환경에서 동기화 문제는 어떻게 해결하나요?"

## 방향 선택 우선순위

follow_up을 선택했다면 아래 규칙으로 direction을 고르세요.
특히 depth/reasoning을 기본값처럼 남용하지 마세요.

1. correction
   - 명백한 사실 오류가 있으면 correction이 최우선입니다.
   - 오개념이 있는데 depth나 reasoning으로 가면 안 됩니다.

2. depth
   - 핵심 단계, 구성요소, 필수 개념이 빠졌을 때만 사용하세요.
   - 예: handshake 단계 누락, B-Tree 구조 요소 누락

3. reasoning
   - 정의나 결과는 맞지만, 왜 그런지 원리 설명이 비어 있을 때만 사용하세요.
   - "더 자세히 설명해보세요" 같은 막연한 심화 용도로 쓰지 마세요.

4. lateral
   - 현재 개념의 정확성, 완성도, 깊이가 이미 충분하면 lateral을 우선 선택하세요.
   - 같은 개념을 더 파는 것보다, 인접 개념으로 확장하는 쪽이 정보 이득이 크면 lateral이 정답입니다.

## 저점 케이스 보정 규칙

- lateral 보정:
  현재 질문에 대한 답이 정확하고 충분하면, 같은 개념의 depth/reasoning을 반복하지 말고 lateral로 전환하세요.
  예: TCP handshake를 충분히 설명했다면 UDP, process/thread를 충분히 설명했다면 동기화 문제로 확장

- depth vs reasoning 구분:
  빠진 단계/구성요소를 채우는 질문이면 depth,
  이미 요소는 있지만 "왜" 메커니즘이 비어 있으면 reasoning입니다.

- anti-overprobing:
  같은 개념에서 이미 원리까지 설명한 답변에 다시 depth/reasoning을 고르는 것은 오답에 가깝습니다.

## 중요 규칙

- 이미 한 질문과 같은 내용을 반복하지 마세요
- direction_detail은 반드시 구체적인 CS 개념/기술 맥락을 포함해야 합니다
- 지원자가 언급하지 않은 내용을 언급한 것처럼 전제하지 마세요
- 지원자의 답변 내용에서 출발하는 자연스러운 방향을 제시하세요
- correction 방향에서는 틀린 내용을 직접 정정하지 말고, 재고할 기회를 주세요
- lateral은 현재 토픽과 밀접하게 연관된 개념으로만 확장하세요
- 현재 개념이 충분히 설명되었는데도 depth/reasoning을 고르는 것은 오답에 가깝습니다.
- direction을 고를 때는 "같은 개념을 더 물어볼 수 있는가"보다
  "이제 다른 인접 개념으로 넓히는 편이 더 좋은가"를 먼저 판단하세요.\
"""


# ============================================================
# Router User Prompt Template & Builder
# ============================================================

CS_ROUTER_USER_PROMPT_TEMPLATE = """\
## 이미 다룬 토픽
{covered_topics}

## 현재 토픽의 Q&A 이력
{current_topic_qa}

## 세션 진행 상태
- 진행된 토픽: {current_topic_count}/{max_topics}
- 현재 토픽 꼬리질문: {current_follow_up_count}/{max_follow_ups_per_topic}

## 분석 대상
마지막 질문: {last_question}
지원자 답변: {last_answer}

위 답변을 분석하고 다음 행동을 결정하세요.\
"""


def _extract_covered_topics(
    interview_history: list[QATurn], current_topic_id: int
) -> str:
    """완료된 토픽 목록을 포맷팅 (중복 질문 방지용).

    이전 토픽들은 '토픽명 + 질문 목록'만 간결하게 제공하여
    LLM이 이미 다룬 주제를 인지하고 중복을 피하도록 한다.
    """
    if not interview_history:
        return "(첫 번째 토픽)"

    # 현재 토픽 이전의 토픽들만 수집
    previous_topics: dict[int, list[str]] = {}
    for turn in interview_history:
        if turn.topic_id < current_topic_id:
            if turn.topic_id not in previous_topics:
                previous_topics[turn.topic_id] = []
            previous_topics[turn.topic_id].append(turn.question)

    if not previous_topics:
        return "(첫 번째 토픽)"

    formatted = []
    for topic_id in sorted(previous_topics.keys()):
        questions = previous_topics[topic_id]
        main_question = questions[0] if questions else "N/A"
        followups = questions[1:] if len(questions) > 1 else []

        topic_text = f"토픽 {topic_id}: {main_question}"
        if followups:
            followup_list = ", ".join(f'"{q}"' for q in followups)
            topic_text += f"\n  꼬리질문: {followup_list}"
        formatted.append(topic_text)

    return "\n".join(formatted)


def _format_current_topic_qa(
    interview_history: list[QATurn], current_topic_id: int
) -> str:
    """현재 토픽의 Q&A를 원문 그대로 포맷팅.

    현재 토픽의 대화는 2-3턴 정도라 원문 전달해도 토큰 부담이 적다.
    라우터가 맥락을 정확히 파악하려면 원문이 필요하다.
    """
    current_turns = [
        turn for turn in interview_history if turn.topic_id == current_topic_id
    ]

    if not current_turns:
        return "(현재 토픽 시작)"

    sorted_turns = sorted(current_turns, key=lambda t: t.turn_order)

    formatted = []
    for turn in sorted_turns:
        prefix = "[메인]" if turn.turn_type == "new_topic" else "[꼬리]"
        answer = (
            turn.answer_text[:300] + "..."
            if len(turn.answer_text) > 300
            else turn.answer_text
        )
        formatted.append(f"{prefix} Q: {turn.question}\nA: {answer}")

    return "\n\n".join(formatted)


def build_cs_router_prompt(
    interview_history: list[QATurn],
    current_topic_id: int,
    current_topic_count: int,
    max_topics: int,
    current_follow_up_count: int,
    max_follow_ups_per_topic: int,
    last_question: str,
    last_answer: str,
) -> str:
    """CS question_router용 유저 프롬프트 생성."""

    covered_topics = _extract_covered_topics(interview_history, current_topic_id)
    current_topic_qa = _format_current_topic_qa(interview_history, current_topic_id)

    return CS_ROUTER_USER_PROMPT_TEMPLATE.format(
        covered_topics=covered_topics,
        current_topic_qa=current_topic_qa,
        current_topic_count=current_topic_count,
        max_topics=max_topics,
        current_follow_up_count=current_follow_up_count,
        max_follow_ups_per_topic=max_follow_ups_per_topic,
        last_question=last_question,
        last_answer=last_answer,
    )
