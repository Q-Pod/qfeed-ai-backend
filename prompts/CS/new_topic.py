# # prompts/cs/new_topic.py

# prompts/cs/new_topic.py

"""CS 새 토픽 질문 생성 프롬프트

CS 실전모드에서 새로운 토픽의 메인 질문을 생성할 때 사용한다.
question_router가 new_topic으로 분기한 경우 호출된다.

LLM: skt/A.X-4.0-Light (7B) - 명확하고 직접적인 지시 필요
"""

from schemas.feedback import QuestionCategory, QATurn
from taxonomy.loader import (
    get_cs_categories_for_prompt,
    get_subcategories_for_prompt,
)


# ============================================================
# System Prompt (7B 모델용 - 간결하고 직접적)
# ============================================================




CS_NEW_TOPIC_SYSTEM_PROMPT = """\
당신은 신입 개발자 CS 면접관입니다. 새로운 토픽의 질문을 생성합니다.

## 🚨 절대 금지 (가장 중요)

1. **자문자답 금지**: 질문 안에 답이나 힌트를 넣지 마라.
   - ❌ "인덱스를 쓰면 조회는 빨라지지만 쓰기는 느려집니다. 어떻게 하시겠어요?"
   - ✅ "인덱스를 모든 컬럼에 걸지 않는 이유가 뭘까요?"

2. **복합 질문 금지**: 한 번에 하나만 물어라.
   - ❌ "A는 뭔가요? 그리고 B와 차이점은요?"
   - ✅ "A와 B 중 어떤 상황에서 A를 선택하시겠어요?"

3. **쿠션어에 기술 내용 금지**: 쿠션어는 전환만.
   - ❌ "그럼 인덱스에 대해 질문드릴게요."
   - ✅ "네, 다음 질문 드릴게요."

## 난이도: 신입 개발자 수준

기본 개념의 "왜?"를 묻는다. 심화 최적화/대규모 시스템은 묻지 않는다.

적절한 질문:
- "프로세스와 스레드 중 언제 스레드를 선택하나요?"
- "DB에서 인덱스를 모든 컬럼에 안 거는 이유가 뭘까요?"
- "HTTP 대신 HTTPS를 쓰는 이유가 뭔가요?"

부적절한 질문 (너무 어려움):
- "대용량 트래픽에서 DB 샤딩 전략을 설명해주세요."
- "분산 시스템의 CAP 정리를 적용한 설계를 해주세요."

## 톤 가이드
- 면접관은 정중하지만 간결하게
- "왜?" 단독 사용 금지 → "왜 그런가요?", "이유가 뭘까요?"
- 반말/명령조 금지

❌ "왜?" / "설명해봐" / "넘어가죠"
✅ "왜 그런가요?" / "설명해주시겠어요?" / "넘어가 볼게요"

## 쿠션어 (cushion_text)

- 1문장, 30자 이내
- 기술 용어 절대 금지
- 예시: "네, 다음 질문 드릴게요." / "좋습니다, 넘어가죠."

## 질문 (question_text)

- 1문장으로 80자 이내
- 시나리오 + "왜?" 또는 "어떤 걸 선택?"
- 정의형 금지 ("~란 무엇인가요?")
- Trade-off 직접 언급 금지 (답변에서 나오게 유도)

## taxonomy 선택 규칙

- category와 subcategory는 질문 생성 후 붙이는 라벨이 아니다.
- 먼저 CS taxonomy에서 category를 고르고, 그 category 하위의 subcategory ID를 고른 뒤 질문을 생성하라.
- 출력하는 category는 제공된 category ID 중 하나여야 한다.
- 출력하는 subcategory는 선택한 category 하위의 subcategory ID 중 하나여야 한다.
- taxonomy에 없는 ID를 임의로 만들지 마라.
"""


# ============================================================
# User Prompt Template
# ============================================================



CS_NEW_TOPIC_USER_PROMPT_TEMPLATE = """\
## 상태
{cushion_instruction}

## 설정
- 질문 유형: CS
- {category_instruction}
- {subcategory_instruction}

## CS taxonomy
{category_taxonomy}

## 선택 가능한 subcategories
{available_subcategories}

## 이전 토픽
{previous_topic_summary}

## 이미 다룬 질문
{covered_questions}

---
🚨 다시 한번 확인:
- 질문 안에 답/힌트 넣지 마라 (자문자답 금지)
- 한 번에 하나만 물어라
- 쿠션어에 기술 내용 넣지 마라

새 질문을 생성하세요.
"""


# ============================================================
# Prompt Builder
# ============================================================

def get_cs_new_topic_system_prompt() -> str:
    return CS_NEW_TOPIC_SYSTEM_PROMPT


def build_cs_new_topic_prompt(
    interview_history: list[QATurn],
    forced_category: QuestionCategory | None = None,
    forced_subcategory: str | None = None,
    available_categories: list[str] | None = None,
    router_analysis: dict | None = None,
) -> str:
    """CS 새 토픽 질문 생성용 유저 프롬프트

    Args:
        interview_history: 전체 면접 히스토리
        forced_category: 첫 질문 시 강제 지정 카테고리
        forced_subcategory: 강제 지정 subcategory
        available_categories: 선택 가능한 카테고리 목록
        router_analysis: question_router가 남긴 이전 토픽 분석 결과
    """

    # 쿠션어 지시 (간결하게)
    if not interview_history:
        cushion_instruction = "면접 시작. 가벼운 인사만."
    else:
        cushion_instruction = "화제 전환. 짧게 마무리."

    # 카테고리 지시
    if forced_category:
        category_instruction = f"category는 반드시 `{forced_category.value}`를 선택하세요."
    elif available_categories:
        category_instruction = (
            "category는 반드시 다음 ID 중 하나를 선택하세요: "
            f"{', '.join(available_categories)}"
        )
    else:
        category_instruction = "category는 반드시 제공된 CS taxonomy의 ID 중 하나여야 합니다."

    if forced_subcategory:
        subcategory_instruction = (
            f"subcategory는 반드시 `{forced_subcategory}`를 선택하세요."
        )
    elif forced_category:
        subcategory_instruction = (
            f"subcategory는 `{forced_category.value}` 하위 소분류 ID 중 하나여야 합니다."
        )
    else:
        subcategory_instruction = (
            "subcategory는 선택한 category 하위의 소분류 ID 중 하나여야 합니다."
        )

    category_taxonomy = get_cs_categories_for_prompt()
    available_subcategories = (
        get_subcategories_for_prompt(forced_category.value)
        if forced_category
        else "(category를 먼저 선택한 뒤, 위 taxonomy에서 해당 category의 subcategory ID를 고르세요.)"
    )

    # 이전 토픽 요약
    previous_topic_summary = _build_previous_topic_summary(
        interview_history, router_analysis
    )

    # 이미 다룬 질문 목록
    covered_questions = _format_covered_questions(interview_history)

    return CS_NEW_TOPIC_USER_PROMPT_TEMPLATE.format(
        cushion_instruction=cushion_instruction,
        category_instruction=category_instruction,
        subcategory_instruction=subcategory_instruction,
        category_taxonomy=category_taxonomy,
        available_subcategories=available_subcategories,
        previous_topic_summary=previous_topic_summary,
        covered_questions=covered_questions,
    )


def _build_previous_topic_summary(
    interview_history: list[QATurn],
    router_analysis: dict | None,
) -> str:
    """이전 토픽 요약 (간결하게)"""
    if not interview_history:
        return "(첫 토픽)"

    last_topic_id = max(t.topic_id for t in interview_history)
    last_topic_turns = [t for t in interview_history if t.topic_id == last_topic_id]
    main_question = last_topic_turns[0].question if last_topic_turns else "N/A"

    # 70자로 truncate
    if len(main_question) > 70:
        main_question = main_question[:67] + "..."

    summary = f"직전: {main_question}"

    if router_analysis and router_analysis.get("covered_concepts"):
        concepts = router_analysis["covered_concepts"][:3]  # 최대 3개
        summary += f"\n다룬 개념: {', '.join(concepts)}"

    return summary


def _format_covered_questions(history: list[QATurn]) -> str:
    """이미 다룬 질문 목록 (간결하게)"""
    if not history:
        return "(없음)"

    # 메인 질문만 추출 (turn_order == 0 또는 각 토픽의 첫 번째)
    topics: dict[int, str] = {}
    for turn in history:
        if turn.topic_id not in topics:
            question = turn.question
            if len(question) > 50:
                question = question[:47] + "..."
            topics[turn.topic_id] = question

    return "\n".join(f"- {q}" for q in topics.values())

# """CS 새 토픽 질문 생성 프롬프트

# CS 실전모드에서 새로운 토픽의 메인 질문을 생성할 때 사용한다.
# question_router가 new_topic으로 분기한 경우 호출된다.

# router가 state에 남긴 router_analysis(이전 토픽 분석 결과)를
# 참고하여, 이전 토픽과 자연스럽게 연결되면서도 다른 영역의 질문을 생성한다.
# """

# from schemas.question import QuestionType
# from schemas.feedback import QuestionCategory, QATurn


# # ============================================================
# # 쿠션어 공통 규칙 (시스템 프롬프트 상단)
# # ============================================================

# _CUSHION_RULES = """\
# ## 쿠션어 필수 규칙
# - 쿠션어는 "전환 역할만" 수행. 질문 내용을 절대 포함하지 마세요.
# - "오늘 우리는 ~", "다음으로 ~에 대해" 패턴 금지
# - 기술 용어, 카테고리명, 과목명, 질문 힌트를 쿠션어에 넣지 마세요
# - "정답입니다/틀렸습니다" 같은 평가 표현 금지

# ### ❌ 잘못된 쿠션어 예시
# - "그럼 인덱스에 대해 질문드릴게요." (질문 내용 스포일러)
# - "메모리 관리 쪽으로 넘어가볼게요." (토픽 힌트)
# - "인덱스의 역할과 성능 변화에 대해 어떻게 생각하시나요?" (질문 자체를 쿠션어에 포함)

# ### ✅ 올바른 쿠션어 예시
# - "네, 잘 들었습니다. 다음 질문 드릴게요."
# - "좋습니다. 그럼 다른 쪽으로 넘어가 보죠."
# - "까다로운 부분이긴 합니다. 다음 질문으로 가볼게요."\
# """


# # ============================================================
# # System Prompt
# # ============================================================

# CS_NEW_TOPIC_SYSTEM_PROMPT = """\
# 당신은 신입 개발자의 CS 기본기를 검증하는 실무 기술 면접관입니다.
# 새로운 토픽의 메인 질문을 생성합니다.

# ## 난이도 가이드 (신입 개발자 기준)
# - 기본 개념의 "왜?"를 묻는 수준
# - 교과서적 지식 + 간단한 상황 적용
# - 심화 최적화, 대규모 시스템 설계는 지양

# """ + _CUSHION_RULES + """

# ## 쿠션어 (cushion_text) 작성 가이드
# - 분량: 1~2문장, 최대 60자 이내
# - 첫 질문: 가벼운 인사 + 시작 멘트. 기술 주제 언급 금지.
# - 화제 전환: "네, 잘 들었습니다. 그럼 다음 질문 드릴게요." 수준으로 짧게.
# - 지원자가 막혔을 때: "까다로운 부분이긴 합니다. 다른 쪽으로 넘어가 볼게요."

# ## 메인 질문 (question_text) 작성 가이드
# - **단일 질문 원칙**: 하나의 질문에 하나의 핵심 포인트만
# - 1~2문장, 100자 이내로 간결하게
# - 시나리오 제시 후 "왜?" 또는 "어떻게?"로 마무리
# - Trade-off는 답변에서 자연스럽게 나오도록 유도 (직접 언급 금지)

# ### ❌ 잘못된 질문 예시
# - "인덱스를 사용하는 이유는 무엇인가요? 인덱스를 사용하면 검색 속도가 향상되지만, 쓰기 작업이 느려질 수 있습니다. 이 두 요소 간의 균형을 어떻게 맞출 것인가요?"
#   → 문제: 3개 질문이 합쳐짐, Trade-off 직접 언급, 150자 초과

# ### ✅ 올바른 질문 예시
# - "읽기가 많은 서비스에서 특정 쿼리가 느려졌을 때, 어떤 방식으로 개선을 시도하시겠어요?"
#   → 시나리오 + 단일 질문, Trade-off는 답변에서 자연스럽게 나옴

# ## 금지 사항
# - 이미 다룬 질문과 중복
# - 단순 정의형 ("A란 무엇인가요?")
# - 두 가지 이상 요구사항을 한 문장에 묶는 복합 질문
# - 전문용어에 원어 병기 금지 ("인덱스(Index)" → 한글 또는 영어 하나만)\
# """


# # ============================================================
# # User Prompt Template
# # ============================================================

# CS_NEW_TOPIC_USER_PROMPT_TEMPLATE = """\
# ## 면접 진행 상태
# {cushion_instruction}

# ## 면접 설정
# - 질문 유형: CS
# - {category_instruction}

# ## 이전 토픽 요약
# {previous_topic_summary}

# ## 이미 다룬 질문 (중복 피할 것)
# {covered_questions}

# 새로운 메인 질문을 생성하세요.\
# """


# # ============================================================
# # Prompt Builder
# # ============================================================

# def get_cs_new_topic_system_prompt() -> str:
#     return CS_NEW_TOPIC_SYSTEM_PROMPT


# def build_cs_new_topic_prompt(
#     interview_history: list[QATurn],
#     forced_category: QuestionCategory | None = None,
#     available_categories: list[str] | None = None,
#     router_analysis: dict | None = None,
# ) -> str:
#     """CS 새 토픽 질문 생성용 유저 프롬프트

#     Args:
#         interview_history: 전체 면접 히스토리
#         forced_category: 첫 질문 시 강제 지정 카테고리
#         available_categories: 선택 가능한 카테고리 목록
#         router_analysis: question_router가 남긴 이전 토픽 분석 결과
#     """

#     # 쿠션어 지시
#     if not interview_history:
#         cushion_instruction = (
#             "현재 상태: [면접 시작]\n"
#             "가벼운 인사와 함께 면접 시작을 알리세요."
#         )
#     else:
#         cushion_instruction = (
#             "현재 상태: [화제 전환]\n"
#             "이전 토픽을 짧게 마무리하고 다음 질문으로 넘어가세요."
#         )

#     # 카테고리 지시
#     if forced_category:
#         category_instruction = (
#             f"카테고리: 반드시 `{forced_category.value}`에서 질문하세요."
#         )
#     elif available_categories:
#         category_instruction = (
#             f"선택 가능한 카테고리: {available_categories}\n"
#             f"위 중 하나를 선택하여 category 필드에 정확히 기입하세요."
#         )
#     else:
#         category_instruction = "카테고리: 자유 선택"

#     # 이전 토픽 요약 (router 분석 결과 활용)
#     previous_topic_summary = _build_previous_topic_summary(
#         interview_history, router_analysis
#     )
   
#     # 이미 다룬 질문 목록
#     covered_questions = _format_covered_questions(interview_history)

#     return CS_NEW_TOPIC_USER_PROMPT_TEMPLATE.format(
#         cushion_instruction=cushion_instruction,
#         category_instruction=category_instruction,
#         previous_topic_summary=previous_topic_summary,
#         covered_questions=covered_questions,
#     )


# def _build_previous_topic_summary(
#     interview_history: list[QATurn],
#     router_analysis: dict | None,
# ) -> str:
#     """이전 토픽의 요약 정보를 구성한다.

#     router_analysis가 있으면 마지막 토픽에서 지원자가 잘한 점/부족한 점을
#     간결하게 전달하여, 새 토픽이 다른 영역을 커버하도록 유도한다.
#     """
#     if not interview_history:
#         return "(첫 번째 토픽)"

#     # 마지막 토픽의 메인 질문 추출
#     last_topic_id = max(t.topic_id for t in interview_history)
#     last_topic_turns = [t for t in interview_history if t.topic_id == last_topic_id]
#     main_question = last_topic_turns[0].question if last_topic_turns else "N/A"

#     summary = f"직전 토픽: {main_question}"

#     # router 분석이 있으면 요약 추가
#     if router_analysis:
#         if router_analysis.get("completeness"):
#             summary += f"\n완성도: {router_analysis['completeness']}"
#         if router_analysis.get("depth"):
#             summary += f"\n깊이: {router_analysis['depth']}"

#     return summary


# def _format_covered_questions(history: list[QATurn]) -> str:
#     """이미 다룬 질문 목록 (메인 + 꼬리질문 포함)"""
#     if not history:
#         return "(없음)"

#     # 토픽별로 그룹핑
#     topics: dict[int, list[QATurn]] = {}
#     for turn in history:
#         if turn.topic_id not in topics:
#             topics[turn.topic_id] = []
#         topics[turn.topic_id].append(turn)

#     formatted = []
#     for tid in sorted(topics.keys()):
#         turns = sorted(topics[tid], key=lambda t: t.turn_order)
#         main = turns[0].question
#         followups = [t.question for t in turns[1:]]

#         topic_text = f"- 토픽 {tid}: {main}"
#         if followups:
#             for fq in followups:
#                 topic_text += f"\n  └ 꼬리: {fq}"
#         formatted.append(topic_text)

#     return "\n".join(formatted)
