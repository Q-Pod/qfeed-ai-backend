# services/session_end_detector.py

"""사용자 발화에서 '면접 종료' 요청 여부 감지 (룰 + LLM 백업)"""

import re

from core.dependencies import get_llm_provider
from core.logging import get_logger
from prompts.session_end_intent import (
    get_session_end_intent_system_prompt,
    build_session_end_intent_prompt,
)
from schemas.question import SessionEndIntentOutput

logger = get_logger(__name__)

# 사용자가 면접 종료를 요청할 때 쓸 수 있는 표현 (공백 정규화 후 포함 여부로 판단)
_USER_END_PHRASES = [
    "면접 종료",
    "면접종료",
    "면접 끝",
    "면접 끝낼게요",
    "면접 끝낼게",
    "면접 그만",
    "면접 여기까지",
    "종료할게요",
    "종료할게",
    "끝낼게요",
    "끝낼게",
    "그만할게요",
    "그만할게",
    "여기까지 할게요",
    "여기까지 할게",
    "종료해 주세요",
    "끝내주세요",
    "면접 종료해 주세요",
    "면접 끝내주세요",
]

_LLM_TRIGGER_HINTS = [
    # 룰로 못 잡더라도 "종료 의도"가 섞여 있을 가능성이 높은 힌트들만
    "종료",
    "끝",
    "그만",
    "stop",
    "end",
    "finish",
]


def _normalize(text: str) -> str:
    """비교를 위해 공백·줄바꿈 정규화 (한글은 대소문자 없음)"""
    if not text or not isinstance(text, str):
        return ""
    return re.sub(r"\s+", " ", text.strip())

def is_user_requested_session_end_rule_only(answer_text: str) -> bool:
    """룰 기반으로만 '면접 종료' 요청 여부를 판단합니다."""
    if not answer_text or not answer_text.strip():
        return False
    normalized = _normalize(answer_text)
    for phrase in _USER_END_PHRASES:
        if phrase in normalized:
            return True
    return False

def _should_invoke_llm(normalized_answer: str) -> bool:
    """LLM 백업 호출이 의미 있는지(비용/노이즈 감소) 1차로 필터링."""
    lowered = normalized_answer.lower()
    return any(hint in lowered for hint in _LLM_TRIGGER_HINTS)


async def is_user_requested_session_end(
    *,
    last_question: str,
    answer_text: str,
    confidence_threshold: float = 0.92,
    llm_provider: str = "gemini_lite",
) -> tuple[bool, float, str]:
    """
    하이브리드 판단:
    - 1차: 룰 매칭(명시적 종료 표현) → 즉시 True
    - 2차: (룰 미매치 + 힌트 존재 시) LLM 구조화 분류 → confidence_threshold 이상일 때만 True

    Returns:
        (should_end, confidence, reasoning)
    """
    if not answer_text or not answer_text.strip():
        return (False, 0.0, "empty_answer")

    normalized = _normalize(answer_text)

    # Step 1: 룰 기반 즉시 종료
    if is_user_requested_session_end_rule_only(normalized):
        return (True, 1.0, "rule_match")

    # Step 2: 애매한 케이스만 LLM 백업
    if not _should_invoke_llm(normalized):
        return (False, 0.0, "no_llm_hint")

    try:
        llm = get_llm_provider(llm_provider)
        system_prompt = get_session_end_intent_system_prompt(llm.provider_name)
        prompt = build_session_end_intent_prompt(
            last_question=last_question or "",
            last_answer=answer_text,
        )

        result = await llm.generate_structured(
            prompt=prompt,
            response_model=SessionEndIntentOutput,
            system_prompt=system_prompt,
            temperature=0.0,
            max_tokens=300,
        )

        should_end = bool(result.should_end and result.confidence >= confidence_threshold)
        reasoning = "llm_confident" if should_end else "llm_not_confident"
        return (should_end, float(result.confidence), reasoning)
    except Exception as e:
        logger.warning(f"session_end_intent llm failed: {type(e).__name__}: {e}")
        return (False, 0.0, "llm_failed")
