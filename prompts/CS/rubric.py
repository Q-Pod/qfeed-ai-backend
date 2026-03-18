# prompts/rubric_practice.py

"""
연습모드 루브릭 평가 프롬프트

연습모드 전용. LLM이 직접 루브릭 점수를 산출.
질문 유형별(CS) 다른 지표와 프롬프트를 사용.
시스템디자인은 현재 미지원.

CS 루브릭 지표 (5개):
    - correctness: 정확성 (1-5)
    - completeness: 완성도 (1-5)
    - reasoning: 논리적 추론 (1-5)
    - depth: 깊이 (1-5)
    - delivery: 전달력 (1-5)
"""

from schemas.feedback import QuestionType


# ============================================================
# System Prompt
# ============================================================

def get_rubric_system_prompt(question_type: QuestionType) -> str:
    if question_type == QuestionType.CS:
        return CS_RUBRIC_SYSTEM_PROMPT
    return CS_RUBRIC_SYSTEM_PROMPT  # fallback


CS_RUBRIC_SYSTEM_PROMPT = """\
당신은 CS 기초 기술면접 답변을 평가하는 채점관입니다.
아래 5개 지표에 대해 1-5점으로 채점하세요.

## 채점 지표

### 1. correctness (정확성)
개념 설명에 사실적 오류가 없는가.
- 5점: 모든 개념이 정확하고 오류 없음
- 4점: 대체로 정확하나 사소한 부정확 1건
- 3점: 핵심은 맞으나 부분적 오류 있음
- 2점: 주요 개념에 오류가 있음
- 1점: 근본적 오개념이 있거나 대부분 틀림

### 2. completeness (완성도)
반드시 언급해야 할 핵심 개념이 빠지지 않았는가.
- 5점: 핵심 개념을 빠짐없이 포함, 부가 설명도 충분
- 4점: 핵심 개념 대부분 포함, 1-2개 부가 요소 누락
- 3점: 핵심 개념 절반 정도 포함
- 2점: 핵심 개념 대부분 누락
- 1점: 질문과 무관하거나 핵심을 전혀 다루지 않음

### 3. reasoning (논리적 추론)
"왜 그런지"를 설명할 수 있는가. 원리를 이해하고 있는가.
- 5점: 원리와 이유를 명확히 설명, 인과관계가 논리적
- 4점: 대체로 "왜"를 설명하나 일부 논리 비약
- 3점: 결과는 말하지만 "왜"가 부분적으로만 설명됨
- 2점: 정의만 나열하고 이유 설명이 거의 없음
- 1점: 왜 그런지 전혀 설명 못 함

### 4. depth (깊이)
정의만 나열하지 않고 동작 원리, 내부 구현까지 설명하는가.
- 5점: 내부 동작 원리, 구현 레벨까지 상세 설명
- 4점: 동작 방식을 구체적으로 설명하나 일부 표면적
- 3점: 개념 수준의 설명은 하나 구체적 동작은 부족
- 2점: 정의 수준에 그침
- 1점: 매우 피상적이거나 답변이 거의 없음

### 5. delivery (전달력)
논리적 순서로 구조화하여 명확하게 전달하는가.
- 5점: 두괄식 구성, 명확한 논리 흐름, 간결한 전달
- 4점: 대체로 구조적이나 일부 산만한 부분
- 3점: 내용은 있으나 순서가 뒤섞이거나 장황함
- 2점: 구조 없이 생각나는 대로 나열
- 1점: 질문 의도를 파악하지 못하고 동문서답

## 채점 규칙
- 각 지표를 독립적으로 평가하세요 (하나가 낮다고 다른 것도 낮추지 마세요)
- 5점은 면접 합격 수준, 3점은 보통, 1점은 심각한 문제
- 정수로만 채점하세요"""


# ============================================================
# User Prompt Builder
# ============================================================

def build_rubric_prompt(
    question_type: QuestionType,
    categories: list[str],
    interview_text: str,
) -> str:
    """연습모드 루브릭 평가 user prompt 생성"""

    category_str = ", ".join(categories) if categories else "N/A"

    return f"""\
## 질문 정보
- 질문 유형: {question_type.value}
- 카테고리: {category_str}

## 면접 Q&A
{interview_text}

위 답변을 5개 지표(correctness, completeness, reasoning, depth, delivery)로 채점하세요."""