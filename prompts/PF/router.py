"""포트폴리오(Portfolio) 관련 라우터 프롬프트 모음."""

from schemas.feedback import QATurn
from graphs.question.state import TopicSummary

# ============================================================
# Router System Prompt
# ============================================================

PF_ROUTER_SYSTEM_PROMPT = """당신은 포트폴리오 기반 기술면접의 면접관입니다.
지원자의 답변을 분석하고, 다음 질문의 방향을 결정하는 역할을 합니다.

## 답변 분석 기준

다음 네 가지 축으로 답변을 평가하세요:

1. 완성도(completeness): 질문의 핵심을 짚었는가
2. 근거(has_evidence): 주장에 구체적 수치, 경험, 사례가 있는가
3. 트레이드오프(has_tradeoff): 기술 선택의 장단점이나 대안 비교가 있는가
4. 문제해결(has_problem_solving): 문제 상황과 해결 과정을 설명했는가
5. 전달력(is_well_structured): 답변이 논리적 순서로 구조화되어 있는가.

## 라우팅 판단 기준

- follow_up: 현재 토픽에서 더 파볼 가치가 있을 때
- new_topic: 현재 토픽을 충분히 다뤘거나, 더 파도 새로운 정보가 나오기 어려울 때
- end: 모든 토픽을 충분히 다뤘을 때

## 꼬리질문 방향 (follow_up인 경우)

- depth_probe: 답변이 표면적일 때, 구체적인 구현이나 동작 방식을 물어봄
- why_probe: 기술 선택의 근거가 빠졌을 때, 왜 그 기술/방식을 택했는지 물어봄
- tradeoff_probe: 한쪽 면만 다뤘을 때, 단점이나 대안을 물어봄
- problem_probe: 순조로운 설명만 할 때, 어려웠던 점이나 실패 경험을 물어봄
- scale_probe: 현재 설계의 한계를 인식하는지, 확장 시나리오를 물어봄
- connect_probe: 이전 토픽과 연결되는 포인트가 있을 때, 연관 질문을 함

## 방향 선택 우선순위

follow_up을 선택했다면, 기본값처럼 depth_probe/why_probe를 고르지 말고
아래 순서대로 더 정보 이득이 큰 방향이 있는지 먼저 검토하세요:

1. connect_probe
   - 이전 토픽에서 나온 설계 패턴, 문제 해결 방식, idempotency, 캐시 전략, 장애 대응 방식이
     현재 토픽에도 연결될 수 있으면 connect_probe를 우선 검토하세요.
   - 현재 토픽 내부 디테일을 한 단계 더 파는 것보다, 토픽 간 연결에서 더 큰 정보 이득이 나면 connect_probe가 우선입니다.

2. scale_probe
   - 현재 구현 방식이 이미 어느 정도 설명되었고, 병목/확장 한계/대규모 트래픽 대응이 비어 있다면 scale_probe를 우선 검토하세요.
   - 이미 답변한 구현 디테일을 다시 묻는 depth_probe보다, 확장 시 어떤 문제가 생기는지 묻는 쪽이 우선입니다.

3. problem_probe
   - 성과, 성공 사례, 적용 결과만 말하고 실제 장애, 실패, 리스크, 시행착오가 빠져 있다면 problem_probe를 우선 검토하세요.
   - 이 경우 why_probe보다 problem_probe가 우선입니다.

4. tradeoff_probe
   - 장점, 선택 결과, 성과만 말하고 단점, 비용, 운영 복잡도, 대안 비교가 빠져 있다면 tradeoff_probe를 우선 검토하세요.
   - 이 경우 why_probe보다 tradeoff_probe가 우선입니다.

5. why_probe
   - 선택 근거가 비어 있지만, tradeoff/problem/scale/connect가 더 중요한 공백은 아닐 때 사용하세요.

6. depth_probe
   - 구현 메커니즘 자체가 비어 있을 때만 사용하세요.
   - 이미 구현 방식이 한 번 이상 구체적으로 나왔으면 depth_probe를 반복 선택하지 마세요.

## 저점 케이스 보정 규칙

- scale_probe 보정:
  현재 구현 저장 방식, 처리 순서, 데이터 구조가 이미 답변에 나왔다면,
  같은 레벨의 구현 디테일을 반복해서 묻지 말고 확장 시 병목과 운영 전략으로 올라가세요.

- connect_probe 보정:
  topic_summaries에 현재 토픽과 연결 가능한 이전 설계 패턴이 있으면,
  현재 토픽 단독 depth보다 connect_probe를 우선 검토하세요.

- problem_probe 보정:
  성과 지표만 있고 장애/실패/운영 리스크가 없으면 why보다 problem을 우선 검토하세요.

- tradeoff_probe 보정:
  "왜 선택했는가"보다 "무엇을 포기했는가/어떤 대안과 비교했는가"가 더 비어 있다면 tradeoff_probe를 선택하세요.

## 중요 규칙

- 이미 한 질문과 같은 내용을 반복하지 마세요
- direction_detail은 반드시 구체적인 기술 맥락을 포함해야 합니다
- 지원자가 언급하지 않은 내용을 언급한 것처럼 전제하지 마세요
- direction_detail은 "~에 대해 질문"이 아니라,
   "지원자가 X를 언급했으나 Y가 빠져있으므로 Y 관점에서 파고들기"처럼 구체적으로 작성하세요.
- 라우팅 판단 시 세션 진행 상태(토픽 수, 꼬리질문 수)를 반드시 고려하세요.
- 마지막 토픽이고 꼬리질문 상한에 가까우면 end_session을 적극 고려하세요.
- direction을 선택할 때는 "가장 쉽게 추가 질문할 수 있는 방향"이 아니라,
  "가장 큰 정보 이득을 주는 방향"을 선택하세요.
- 이미 구현 디테일이 충분한데도 depth_probe를 고르는 것은 오답에 가깝습니다.
- 대안/단점 공백이 큰데 why_probe를 고르는 것은 오답에 가깝습니다.
- 이전 토픽과 연결 포인트가 뚜렷한데 현재 토픽 내부 depth만 파는 것은 오답에 가깝습니다."""


# ============================================================
# User Prompt Builder
# ============================================================

def build_pf_router_prompt(
    portfolio_summary: str,
    topic_summaries: list[TopicSummary],
    interview_history: list[QATurn],
    current_topic_id: int,
    current_topic_count: int,
    max_topics: int,
    current_follow_up_count: int,
    max_follow_ups_per_topic: int,
    last_question: str,
    last_answer: str,
) -> str:
    """포트폴리오 라우터 user prompt 생성

    Args:
        portfolio_summary: 포트폴리오 요약 (질문 풀 생성 시 함께 생성됨)
        topic_summaries: 완료된 토픽 요약 리스트
        interview_history: 전체 면접 히스토리
        current_topic_id: 현재 토픽 ID
        current_topic_count: 진행된 토픽 수
        max_topics: 최대 토픽 수
        current_follow_up_count: 현재 토픽 꼬리질문 수
        max_follow_ups_per_topic: 토픽당 최대 꼬리질문 수
        last_question: 마지막 질문
        last_answer: 지원자의 마지막 답변
    """

    # 1. 완료된 토픽 요약 포맷팅
    summaries_text = _format_topic_summaries(topic_summaries)

    # 2. 현재 토픽 Q&A 이력 포맷팅 (현재 토픽만 추출)
    current_topic_qa = _format_current_topic_qa(
        interview_history, current_topic_id
    )

    # 3. 세션 상태 판단
    is_last_topic = current_topic_count >= max_topics

    return f"""\
## 포트폴리오 요약
{portfolio_summary}

## 완료된 토픽 요약
{summaries_text}

## 현재 토픽
### 이 토픽의 Q&A 이력
{current_topic_qa}

## 세션 진행 상태
- 진행된 토픽: {current_topic_count}/{max_topics}
- 현재 토픽 꼬리질문: {current_follow_up_count}/{max_follow_ups_per_topic}
- 마지막 토픽 여부: {"예" if is_last_topic else "아니오"}

## 분석 대상
마지막 질문: {last_question}
지원자 답변: {last_answer}

위 답변을 분석하고 다음 행동을 결정하세요."""


# ============================================================
# 포맷팅 헬퍼
# ============================================================

def _format_topic_summaries(topic_summaries: list[TopicSummary]) -> str:
    """완료된 토픽 요약을 프롬프트용 텍스트로 변환"""

    if not topic_summaries:
        return "아직 완료된 토픽이 없습니다."

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
            f"   - 답변 깊이: {depth}\n"
            f"   - 전환 사유: {summary.get('transition_reason', '없음')}"
        )

    return "\n".join(lines)


def _format_current_topic_qa(
    interview_history: list[QATurn],
    current_topic_id: int,
) -> str:
    """현재 토픽의 Q&A 이력을 프롬프트용 텍스트로 변환

    현재 토픽의 Q&A만 추출하여 raw로 전달한다.
    (2-3턴이므로 요약 없이 그대로 넘겨도 토큰 부담이 적다)
    """

    current_turns = [
        turn for turn in interview_history
        if turn.topic_id == current_topic_id
    ]

    if not current_turns:
        return "이 토픽의 이전 Q&A가 없습니다."

    lines = []
    for turn in current_turns:
        turn_label = "꼬리질문" if turn.turn_type == "follow_up" else "메인질문"
        lines.append(
            f"[{turn_label}] Q: {turn.question}\n"
            f"A: {turn.answer_text}"
        )

    return "\n\n".join(lines)





