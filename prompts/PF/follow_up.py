# prompts/PF/follow_up.py

"""
포트폴리오 기반 면접 - Follow Up Generator 프롬프트

역할: router가 결정한 방향(direction)에 맞는 꼬리질문 문장을 생성
출력: PortfolioFollowUpOutput (cushion_text + question_text + tech_aspect_pairs)

CS follow_up과의 차이:
    - 포트폴리오 요약을 참조하여 프로젝트 맥락 유지
    - direction이 6종류로 세분화 (depth/why/tradeoff/problem/scale/connect)
    - 지원자의 실제 경험에 기반한 질문이어야 함
"""

from schemas.feedback import QATurn
from taxonomy.loader import get_aspect_tags_for_prompt, get_tech_tags_for_prompt


# ============================================================
# System Prompt
# ============================================================

PF_FOLLOW_UP_SYSTEM_PROMPT = """\
당신은 포트폴리오 기반 기술면접의 면접관입니다.
지원자의 답변에 대해 자연스러운 꼬리질문을 생성하고, 질문의 기술-관점 pair도 함께 결정합니다.

## 역할

라우터가 이미 답변을 분석하고 질문 방향을 결정했습니다.
당신은 그 방향에 맞는 **자연스러운 질문 문장과 기술-관점 pair**를 함께 생성하면 됩니다.

## 출력 구성

1. **cushion_text**: 지원자의 답변에 대한 자연스러운 호응 (1문장)
   - 답변 내용을 간단히 인정하거나 공감하는 표현
   - 예) "네, Redis를 도입하신 배경을 잘 이해했습니다."
   - 예) "캐시 전략에 대해 잘 설명해주셨네요."
   - 기계적인 칭찬("훌륭합니다", "대단하네요")은 피하세요

2. **question_text**: 핵심 꼬리질문 (1문장, 최대 2문장)
   - direction에서 지정한 방향에 정확히 맞는 질문
   - 구체적이고 명확하게 무엇을 묻는지 드러나야 함
   - 지원자가 답변한 내용에서 출발하는 자연스러운 질문

3. **tech_aspect_pairs**: 질문이 실제로 검증하려는 기술-관점 pair
   - 각 항목은 `{"tech_tag": "...", "aspect_tag": "..."}` 형태
   - tech_tag는 기술 태그 목록의 canonical_key만 사용
   - aspect_tag는 관점 태그 목록의 id만 사용
   - 0~2개

## 방향별 질문 톤

- **depth_probe**: "그 부분을 좀 더 구체적으로 설명해주실 수 있나요?"
- **why_probe**: "그 기술을 선택하신 특별한 이유가 있나요?"
- **tradeoff_probe**: "그 방식의 단점이나 아쉬웠던 점은 없었나요?"
- **problem_probe**: "그 과정에서 예상치 못한 어려움은 없었나요?"
- **scale_probe**: "만약 트래픽이 크게 늘어난다면 어떻게 대응하실 건가요?"
- **connect_probe**: "앞서 말씀하신 [이전 토픽]과 어떻게 연관되나요?"

## 중요 규칙

1. 질문은 반드시 direction_detail에서 제시한 구체적 방향을 따르세요.
2. 지원자가 언급하지 않은 기술이나 경험을 전제하지 마세요.
3. 질문은 간결하게. 한 번에 여러 가지를 묻지 마세요.
- question_text는 반드시 1문장으로 작성하세요. 최대 2문장.
- 한 번에 하나의 관점만 물어보세요. "~하셨나요? 그리고 ~도 궁금합니다" 식으로 묻지 마세요.
4. 면접관다운 톤을 유지하세요. 너무 딱딱하거나 너무 친근하지 않게.
5. tech_aspect_pairs는 반드시 아래 user prompt에 제공된 taxonomy 키만 사용하세요.
6. pair는 질문 문장 자체를 기준으로 고르세요. 이전 메인질문 태그를 기계적으로 복사하지 마세요.
7. 가능한 모든 조합을 나열하지 말고, 질문이 실제로 검증하는 pair만 넣으세요.
"""


# ============================================================
# User Prompt Builder
# ============================================================

def build_pf_follow_up_user_prompt(
    portfolio_summary: str,
    current_topic_turns: list[QATurn],
    follow_up_direction: str,
    direction_detail: str,
    last_question: str,
    last_answer: str,
) -> str:
    """포트폴리오 꼬리질문 생성용 user prompt

    Args:
        portfolio_summary: 포트폴리오 면접용 요약
        current_topic_turns: 현재 토픽의 Q&A 턴 리스트
        follow_up_direction: 꼬리질문 방향 (router가 결정)
        direction_detail: 구체적 질문 방향 설명 (router가 결정)
        last_question: 마지막 질문
        last_answer: 지원자의 마지막 답변
    """

    # 현재 토픽 Q&A 이력 포맷팅
    qa_lines = []
    for turn in current_topic_turns:
        turn_label = "꼬리질문" if turn.turn_type == "follow_up" else "메인질문"
        qa_lines.append(
            f"[{turn_label}] Q: {turn.question}\n"
            f"A: {turn.answer_text}"
        )
    topic_qa_text = "\n\n".join(qa_lines)
    current_topic_tech_tags = _extract_current_topic_tags(current_topic_turns, "tech_tags")
    current_topic_aspect_tags = _extract_current_topic_tags(current_topic_turns, "aspect_tags")
    tech_tags_list = get_tech_tags_for_prompt()
    aspect_tags_list = get_aspect_tags_for_prompt()

    return f"""\
## 포트폴리오 요약
{portfolio_summary}

## 현재 토픽 Q&A 이력
{topic_qa_text}

## 꼬리질문 방향
- 방향: {follow_up_direction}
- 구체적 지시: {direction_detail}

## 직전 Q&A
질문: {last_question}
답변: {last_answer}

## 현재 토픽에서 이미 관측된 태그
- tech_tags: {', '.join(current_topic_tech_tags) if current_topic_tech_tags else '없음'}
- aspect_tags: {', '.join(current_topic_aspect_tags) if current_topic_aspect_tags else '없음'}

## 기술 태그 목록 (canonical_key만 사용)
<tech_tags_list>
{tech_tags_list}
</tech_tags_list>

## 관점 태그 목록 (id만 사용)
<aspect_tags_list>
{aspect_tags_list}
</aspect_tags_list>

위 방향에 맞는 꼬리질문을 생성하고, 그 질문이 실제로 검증하는 tech_aspect_pairs도 함께 출력하세요."""


def _extract_current_topic_tags(
    current_topic_turns: list[QATurn],
    field_name: str,
) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    pair_key = "tech_tag" if field_name == "tech_tags" else "aspect_tag"

    for turn in current_topic_turns:
        source_tags = list(getattr(turn, field_name, []) or [])
        if not source_tags:
            for pair in getattr(turn, "tech_aspect_pairs", []) or []:
                value = getattr(pair, pair_key, None)
                if value is None and isinstance(pair, dict):
                    value = pair.get(pair_key)
                if value:
                    source_tags.append(value)

        for tag in source_tags:
            if not tag or tag in seen:
                continue
            seen.add(tag)
            result.append(tag)

    return result
