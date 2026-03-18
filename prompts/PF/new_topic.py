# prompts/PF/new_topic.py

"""
포트폴리오 기반 면접 - New Topic Generator 프롬프트

역할: 질문 풀에서 다음에 물어볼 가장 적절한 질문을 선택
모델: Gemini Flash
출력: NewTopicSelectionOutput (selected_question_id + reasoning)

CS new_topic과의 차이:
    - 질문을 생성하지 않고 질문 풀에서 선택
    - topic_summaries를 참고하여 면접 전략적 선택
"""

from graphs.question.state import TopicSummary


# ============================================================
# System Prompt
# ============================================================

PF_NEW_TOPIC_SYSTEM_PROMPT = """\
당신은 포트폴리오 기반 기술면접의 면접관입니다.
다음에 물어볼 질문을 질문 풀에서 선택하는 역할입니다.

## 역할

아래 제공되는 질문 풀에서 가장 적절한 질문 **하나**를 선택하세요.
질문을 새로 만들지 마세요. 반드시 풀에 있는 질문의 question_id를 선택해야 합니다.

## 선택 기준

1. **다양성**: 이미 다룬 토픽과 다른 영역의 질문을 우선 선택
   - 이전 토픽에서 캐싱을 다뤘다면, DB 설계나 인증 같은 다른 영역으로
   - 같은 프로젝트라도 다른 측면을 다루는 질문은 OK

2. **자연스러운 연결**: 이전 토픽에서 자연스럽게 이어질 수 있는 질문이면 가산점
   - 예) 이전 토픽에서 "DB 인덱스"를 다뤘고, 풀에 "쿼리 최적화" 질문이 있으면 자연스러운 전환

3. **약점 탐색**: 이전 토픽에서 지원자가 부족했던 영역과 관련된 질문이 있으면 고려
   - gaps에 "동시성 제어"가 있었고, 풀에 관련 질문이 있으면 선택 가치 높음

4. **프로젝트 분산**: 특정 프로젝트에만 질문이 집중되지 않도록 분산

## 중요 규칙

- 반드시 질문 풀에 있는 question_id 중 하나를 선택하세요.
- 풀에 없는 질문을 만들어내지 마세요.
- reasoning에 왜 이 질문을 선택했는지 간단히 설명하세요."""


# ============================================================
# User Prompt Builder
# ============================================================

def build_pf_new_topic_prompt(
    portfolio_summary: str,
    topic_summaries: list[TopicSummary],
    remaining_pool: list[dict],
) -> str:
    """새 토픽 질문 선택용 user prompt 생성

    Args:
        portfolio_summary: 포트폴리오 면접용 요약
        topic_summaries: 완료된 토픽 요약 리스트
        remaining_pool: 아직 사용되지 않은 질문 풀
    """

    # 1. 완료된 토픽 요약 포맷팅
    summaries_text = _format_topic_summaries(topic_summaries)

    # 2. 남은 질문 풀 포맷팅
    pool_text = _format_question_pool(remaining_pool)

    return f"""\
## 포트폴리오 요약
{portfolio_summary}

## 지금까지 다룬 토픽 요약
{summaries_text}

## 선택 가능한 질문 풀
{pool_text}

위 질문 풀에서 다음에 물어볼 질문을 하나 선택하세요."""


# ============================================================
# 포맷팅 헬퍼
# ============================================================

def _format_topic_summaries(topic_summaries: list[TopicSummary]) -> str:
    """완료된 토픽 요약을 프롬프트용 텍스트로 변환"""

    if not topic_summaries:
        return "아직 다룬 토픽이 없습니다. (첫 번째 토픽 전환)"

    lines = []
    for i, summary in enumerate(topic_summaries, 1):
        key_points = ", ".join(summary.get("key_points", []))
        gaps = ", ".join(summary.get("gaps", []))
        techs = ", ".join(summary.get("technologies_mentioned", []))
        depth = summary.get("depth_reached", "unknown")

        lines.append(
            f"{i}. [{summary.get('topic', '알 수 없음')}]\n"
            f"   - 핵심 포인트: {key_points or '없음'}\n"
            f"   - 부족한 부분: {gaps or '없음'}\n"
            f"   - 언급 기술: {techs or '없음'}\n"
            f"   - 답변 깊이: {depth}"
        )

    return "\n".join(lines)


def _format_question_pool(remaining_pool: list[dict]) -> str:
    """질문 풀을 프롬프트용 텍스트로 변환"""

    if not remaining_pool:
        return "선택 가능한 질문이 없습니다."

    lines = []
    for q in remaining_pool:
        lines.append(
            f"- [ID: {q.get('question_id')}] "
            f"프로젝트: {q.get('project_name', '알 수 없음')} | "
            f"주제: {q.get('topic', '알 수 없음')}\n"
            f"  질문: {q.get('question_text', '')}"
        )

    return "\n".join(lines)