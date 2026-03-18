# prompts/common/topic_summarizer.py

"""
공통 토픽 요약 프롬프트

CS / 포트폴리오 모두 동일한 프롬프트를 사용.
토픽의 Q&A를 보고 핵심 포인트, 부족한 부분, 깊이, 기술 목록을 요약.
"""

from schemas.feedback import QATurn


TOPIC_SUMMARIZER_SYSTEM_PROMPT = """\
당신은 기술면접의 토픽별 요약을 생성하는 역할입니다.

면접관이 이후 질문 방향을 결정할 때 참고할 수 있도록,
간결하고 정보 밀도가 높은 요약을 작성하세요.

## 요약 기준

1. **topic**: 이 토픽의 핵심 주제를 한 구절로 요약 (예: "Redis 캐시 전략 설계", "프로세스와 스레드의 차이")
2. **key_points**: 지원자가 명확히 설명한 핵심 포인트 (최대 3개, 각 1문장)
   - 지원자가 실제로 말한 내용만 포함. 추론하지 마세요.
3. **gaps**: 답변에서 부족하거나 빠진 부분 (최대 3개, 각 1문장)
   - 질문했으나 충분히 답변하지 못한 부분
   - 면접관이라면 추가로 확인하고 싶었을 부분
4. **depth_reached**: 답변 깊이를 세 단계로 판단
   - "surface": 개념만 언급하고 구체적 설명이 없음
   - "moderate": 구현 내용은 설명했으나 근거나 트레이드오프가 부족
   - "deep": 구체적 근거, 트레이드오프, 문제해결 과정까지 설명
5. **technologies_mentioned**: 지원자가 언급한 기술/도구 목록

## 중요 규칙

- 지원자가 실제로 말한 내용만 요약하세요. 추론이나 추측을 포함하지 마세요.
- 각 항목은 간결하게 작성하세요. 이 요약은 프롬프트에 포함되므로 토큰 효율이 중요합니다.
- gaps는 비난이 아니라 "추가로 확인할 수 있었던 부분"으로 작성하세요."""


def build_topic_summarizer_prompt(
    topic_turns: list[QATurn],
    topic_transition_reason: str,
) -> str:
    """토픽 요약용 user prompt 생성"""

    qa_lines = []
    for turn in topic_turns:
        turn_label = "꼬리질문" if turn.turn_type == "follow_up" else "메인질문"
        qa_lines.append(
            f"[{turn_label}] Q: {turn.question}\n"
            f"A: {turn.answer_text}"
        )
    qa_text = "\n\n".join(qa_lines)

    return f"""\
## 토픽 전환 사유
{topic_transition_reason}

## 이 토픽의 전체 Q&A
{qa_text}

위 Q&A를 요약하세요."""