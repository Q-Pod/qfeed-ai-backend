# providers/llm/base.py
from typing import Protocol, TypeVar, Type
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

class LLMProvider(Protocol):
    """LLM Provider 인터페이스"""

    @property
    def provider_name(self) -> str:
        """Provider 식별자"""
        ...
    
    async def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """일반 텍스트 생성"""
        ...
    
    async def generate_structured(
        self,
        prompt: str,
        response_model: Type[T],
        *,
        system_prompt: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 2000,
    ) -> T:
        """Structured Output 생성 - Pydantic 모델로 파싱된 결과 반환"""
        ...