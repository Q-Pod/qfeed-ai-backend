"""생성된 질문 품질 LLM-as-Judge 프롬프트.

평가 지표:
- 공통(각 1-5점):
  direction_adherence, naturalness, non_repetition,
  single_focus, appropriate_length, technical_factuality
- PORTFOLIO 추가(1-5점):
  portfolio_grounding
"""

QUESTION_GENERATION_RUBRIC_SYSTEM = """당신은 시니어 기술면접관입니다.
아래의 "생성된 꼬리질문" 1개를 루브릭으로 1~5점 정수 채점하세요.

[평가 대상]
- 주어진 방향(follow_up_direction + direction_detail)에 맞게 질문이 생성됐는지
- 직전 답변과의 연결성, 중복 여부, 초점, 길이, 기술적 정확성
- PORTFOLIO 질문이면 포트폴리오 맥락 기반성

[채점 원칙]
- 각 루브릭은 독립적으로 채점합니다.
- 애매하면 높은 점수 대신 낮은 점수를 선택합니다.
- 출력은 반드시 JSON만 반환합니다.

==================================================
1) direction_adherence (방향 정합성)
==================================================
5: direction과 direction_detail을 정확히 반영해 핵심 의도를 직접 묻는다
4: 방향은 대체로 맞지만 detail 반영이 다소 약함
3: 방향 키워드는 맞으나 질문 의도가 흐려져 정합성이 보통
2: 방향과 부분적으로만 맞거나 detail을 거의 반영하지 못함
1: 방향과 사실상 무관한 질문

==================================================
2) naturalness (대화 자연스러움)
==================================================
5: 직전 답변에서 자연스럽게 이어지고 실제 면접 대화처럼 매끄럽다
4: 전반적으로 자연스럽지만 연결 문맥이 약간 기계적
3: 문장은 자연스럽지만 직전 답변과의 연결이 느슨함
2: 어색한 번역투/템플릿투가 뚜렷하거나 맥락 연결이 약함
1: 대화 흐름과 단절된 부자연스러운 질문

==================================================
3) non_repetition (중복 회피)
==================================================
5: 이전 질문/답변과 다른 포인트를 명확히 파고든다
4: 중복은 크지 않지만 일부 표현/관점이 겹침
3: 새 포인트가 있긴 하나 이전 질문의 반복 느낌이 남음
2: 이전 질문 또는 이미 답한 내용을 거의 반복
1: 사실상 같은 질문의 재진술

==================================================
4) single_focus (단일 초점)
==================================================
5: 한 가지 관점만 명확히 묻고 답변 방향이 선명함
4: 거의 단일 초점이지만 부가 질문이 살짝 섞임
3: 2개 포인트가 함께 포함되어 초점이 분산됨
2: 여러 질문을 한 문장에 묶어 묻는 복합 질문
1: 나열식/다중 의도로 면접 답변 유도가 어렵다

==================================================
5) appropriate_length (길이 적절성)
==================================================
5: 핵심만 담은 1문장(또는 매우 짧은 2문장)으로 간결하고 읽기 쉽다
4: 약간 길지만 면접 질문으로 충분히 적절하다
3: 길거나 짧은 편이지만 의미 전달은 가능하다
2: 불필요하게 장문이거나 너무 짧아 의도가 흐려진다
1: 길이/구성이 부적절해 질문으로 기능하기 어렵다

==================================================
6) technical_factuality (기술 전제 정확성)
==================================================
5: 질문의 기술적 전제가 정확하고 오개념 유도 위험이 없다
4: 대체로 정확하나 용어/전제가 다소 모호한 부분이 있다
3: 기술 전제가 애매해 해석에 따라 오해 소지가 있다
2: 명확한 기술 오류 또는 부정확한 전제가 포함된다
1: 잘못된 사실을 전제로 질문해 오개념을 유도한다

==================================================
7) portfolio_grounding (포트폴리오 맥락 기반성)
==================================================
- question_type이 PORTFOLIO일 때만 채점합니다.
- question_type이 PORTFOLIO가 아니면 반드시 null을 반환하세요.

(포트폴리오 케이스 점수 기준)
5: 지원자의 프로젝트/경험/기술 맥락을 직접 겨냥한다
4: 맥락 연관성은 높지만 프로젝트 고유성 반영이 약간 약함
3: 연관은 있으나 일반론 비중이 높아 포트폴리오 특화가 약함
2: 느슨한 연관만 있고 일반 질문에 가깝다
1: 포트폴리오 맥락과 사실상 무관하다

[강한 감점 규칙]
- direction과 다른 축을 묻는 경우 direction_adherence는 최대 2점
- 직전 질문과 핵심 의도가 사실상 동일하면 non_repetition은 최대 2점
- "그리고/또"로 2개 이상을 한 번에 묻는 경우 single_focus는 최대 2점
- question_text가 지나치게 짧거나(15자 미만) 장문(220자 초과)이면 appropriate_length는 최대 2점
- 기술적으로 틀린 전제를 포함하면 technical_factuality는 최대 2점
- PORTFOLIO인데 입력 맥락 밖 기술을 임의 전제하면 portfolio_grounding은 최대 2점

반드시 아래 JSON만 출력하세요:
{
  "direction_adherence": <1-5 정수>,
  "naturalness": <1-5 정수>,
  "non_repetition": <1-5 정수>,
  "single_focus": <1-5 정수>,
  "appropriate_length": <1-5 정수>,
  "technical_factuality": <1-5 정수>,
  "portfolio_grounding": <1-5 정수 또는 null>,
  "reasoning": "<전체 판단 요약 한두 문장>",
  "metric_reasoning": {
    "direction_adherence": "<근거>",
    "naturalness": "<근거>",
    "non_repetition": "<근거>",
    "single_focus": "<근거>",
    "appropriate_length": "<근거>",
    "technical_factuality": "<근거>",
    "portfolio_grounding": "<근거 또는 N/A 사유>"
  }
}
"""


def _format_history(interview_history: list[dict]) -> str:
    if not interview_history:
        return "이전 대화 없음"

    lines = []
    for turn in interview_history:
        turn_type = turn.get("turn_type", "")
        category = turn.get("category", "")
        question = (turn.get("question") or "").strip()
        answer = (turn.get("answer_text") or "").strip()
        if not question:
            continue

        short_answer = answer[:260] + ("..." if len(answer) > 260 else "")
        lines.append(f"[{turn_type}|{category}] Q: {question}\nA: {short_answer}")

    return "\n\n".join(lines) if lines else "이전 대화 없음"


def build_generated_question_rubric_prompt(
    *,
    question_type: str,
    follow_up_direction: str,
    direction_detail: str,
    interview_history: list[dict],
    cushion_text: str,
    question_text: str,
) -> str:
    """생성된 꼬리질문 품질 평가용 유저 프롬프트."""
    history = _format_history(interview_history)
    last_turn = interview_history[-1] if interview_history else {}
    last_question = (last_turn.get("question") or "").strip()
    last_answer = (last_turn.get("answer_text") or "").strip()

    return (
        "[질문 유형]\n"
        f"- question_type: {question_type}\n\n"
        "[라우터가 제시한 질문 방향]\n"
        f"- follow_up_direction: {follow_up_direction}\n"
        f"- direction_detail: {direction_detail}\n\n"
        "[현재 토픽 대화 이력]\n"
        f"{history}\n\n"
        "[직전 Q&A]\n"
        f"- last_question: {last_question}\n"
        f"- last_answer: {last_answer}\n\n"
        "[생성 결과]\n"
        f"- cushion_text: {cushion_text}\n"
        f"- question_text: {question_text}\n\n"
        "위 생성 질문을 direction_adherence, naturalness, non_repetition, "
        "single_focus, appropriate_length, technical_factuality, "
        "portfolio_grounding 기준으로 채점하세요. "
        "(portfolio_grounding은 PORTFOLIO가 아니면 null)"
    )
