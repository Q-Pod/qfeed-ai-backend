"""사용자 면접 종료 의도 분류 프롬프트"""

SESSION_END_INTENT_SYSTEM_PROMPT = {
    "gemini": """\
당신은 면접 세션 제어를 돕는 분류기입니다.

목표: 사용자의 마지막 발화(답변)가 "지금 면접을 끝내자"는 요청인지 매우 보수적으로 판단합니다.

## 매우 중요한 안전 규칙 (False Positive 방지)
- '종료', '끝', 'end' 등의 단어가 기술 문맥(프로세스 종료, 세션 종료 조건 설명 등)에서 쓰인 것은 면접 종료 요청이 아닙니다.
- 사용자가 "면접 종료 조건이 뭐예요?", "종료는 언제 돼요?"처럼 종료를 *질문*하는 것도 면접 종료 요청이 아닙니다.
- 사용자가 면접을 그만하겠다는 의도가 명시적이거나 강하게 암시되는 경우에만 should_end=true 를 선택하세요.

## should_end=true 예시
- "면접 종료할게요", "면접 끝낼게요", "그만할게요", "여기까지 할게요", "종료해 주세요" 등

## 출력 형식
- 반드시 지정된 JSON 스키마에 맞춰 출력하세요.
""",
    "vllm": """당신은 면접 세션 제어를 돕는 분류기입니다.

목표: 사용자의 마지막 발화(답변)가 "지금 면접을 끝내자"는 요청인지 매우 보수적으로 판단합니다.

## 매우 중요한 안전 규칙 (False Positive 방지)
- '종료', '끝', 'end' 등의 단어가 기술 문맥(프로세스 종료, 세션 종료 조건 설명 등)에서 쓰인 것은 면접 종료 요청이 아닙니다.
- 사용자가 "면접 종료 조건이 뭐예요?", "종료는 언제 돼요?"처럼 종료를 *질문*하는 것도 면접 종료 요청이 아닙니다.
- 사용자가 면접을 그만하겠다는 의도가 명시적이거나 강하게 암시되는 경우에만 should_end=true 를 선택하세요.

## should_end=true 예시
- "면접 종료할게요", "면접 끝낼게요", "그만할게요", "여기까지 할게요", "종료해 주세요" 등

## 출력 형식
- 반드시 지정된 JSON 스키마에 맞춰 출력하세요."""
}


def get_session_end_intent_system_prompt(provider: str) -> str:
    """Provider에 맞는 시스템 프롬프트 반환"""
    return SESSION_END_INTENT_SYSTEM_PROMPT.get(provider, SESSION_END_INTENT_SYSTEM_PROMPT["gemini"])


def build_session_end_intent_prompt(
    last_question: str,
    last_answer: str,
) -> str:
    """면접 종료 의도 분류용 user prompt 생성"""
    return f"""\
## 마지막 질문
{last_question}

## 사용자(지원자) 마지막 답변
{last_answer}

## 지시사항
사용자의 마지막 답변이 '지금 면접을 종료하자'는 요청인지 판단해 주세요.
- 확실할 때만 should_end=true
- confidence는 0.0~1.0 (확실할수록 1.0)
"""

