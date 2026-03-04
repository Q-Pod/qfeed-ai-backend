# services/bad_case_checker.py
import re
from functools import lru_cache

from kiwipiepy import Kiwi
from sentence_transformers.util import cos_sim

from schemas.feedback import BadCaseResult, BadCaseType, InappropriateCheckResult
from providers.embedding.sentence_transformer import get_embedding_provider
from prompts.bad_case import INAPPROPRIATE_CHECK_PROMPT
from core.dependencies import get_llm_provider
from core.logging import get_logger
from langfuse import observe

logger = get_logger(__name__)

FILLER_POS = {
    "JKS", "JKC", "JKG", "JKO", "JKB", "JKV", "JX", "JC",
    "IC", "EP", "EF", "EC", "ETN", "ETM",
    "SF", "SP", "SS", "SE", "SO", "SW",
}


@lru_cache(maxsize=1)
def _get_kiwi() -> Kiwi:
    return Kiwi()

class BadCaseChecker:
    """답변 품질 사전 검사"""
    def __init__(self, min_meaningful_tokens: int = 3, similarity_threshold: float = 0.3):
        self.min_meaningful_tokens = min_meaningful_tokens
        self.similarity_threshold = similarity_threshold
        self._kiwi = _get_kiwi()
        self._model = get_embedding_provider()
        # Lite 모델은 dependency를 통해 공용으로 재사용
        self._llm = get_llm_provider("gemini_lite")

    def check_insufficient(self, answer: str) -> bool:
        """불충분 답변 체크 - 반복 패턴 및 의미 토큰 수 기반"""
        if self._has_repetitive_pattern(answer):
            return True
        if self._count_meaningful_tokens(answer) < self.min_meaningful_tokens:
            return True
        return False

    def check_off_topic(self, question: str, answer: str) -> bool:
        """주제 이탈 체크 - 임베딩 코사인 유사도 기반"""
        q_emb, a_emb = self._model.encode([question, answer])
        similarity = cos_sim(q_emb, a_emb).item()
        return similarity < self.similarity_threshold

    async def check_inappropriate(self, answer: str) -> bool:
        """부적절 표현 체크 - Gemini LLM 기반 문맥 판별"""
        try:
            result = await self._llm.generate_structured(
                prompt=INAPPROPRIATE_CHECK_PROMPT.format(answer=answer),
                response_model=InappropriateCheckResult,
                temperature=0.0,
                max_tokens=50,
            )
            return result.is_inappropriate
        except Exception as e:
            logger.warning(f"Inappropriate check LLM 실패, 정상 처리 | {type(e).__name__}: {e}")
            return False

    def _count_meaningful_tokens(self, text: str) -> int:
        try:
            tokens = self._kiwi.tokenize(text)
            return sum(1 for t in tokens if t.tag not in FILLER_POS)
        except Exception as e:
            logger.warning(f"토큰화 실패 | {type(e).__name__}: {e}")
            return len(text.split())

    def _has_repetitive_pattern(self, answer: str) -> bool:
        if re.search(r'(.)\1{4,}', answer):
            return True
        if re.search(r'(\S+)(\s+\1){2,}', answer):
            return True
        words = answer.split()
        if len(words) >= 4 and len(set(words)) / len(words) < 0.3:
            return True
        return False
    
    @observe(name="bad_case_check", as_type="tool")
    async def check(self, question: str, answer: str) -> BadCaseResult:
        """단일 Q&A 쌍 체크 - 메인 인터페이스
        
        비용 최적화: cheap 체크(동기)를 먼저 실행하고,
        통과한 경우에만 LLM(비동기)을 호출한다.
        """
        if self.check_insufficient(answer):
            return BadCaseResult.bad(BadCaseType.INSUFFICIENT)
        
        if self.check_off_topic(question, answer):
            return BadCaseResult.bad(BadCaseType.OFF_TOPIC)
        
        if await self.check_inappropriate(answer):
            return BadCaseResult.bad(BadCaseType.INAPPROPRIATE)
        
        return BadCaseResult.normal()
    
    
@lru_cache(maxsize=1)
def get_bad_case_checker() -> BadCaseChecker:
    return BadCaseChecker()
