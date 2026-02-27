# core/dependencies.py
from core.config import get_settings
from providers.llm.base import LLMProvider
from providers.llm.vllm import VLLMProvider
from providers.llm.gemini import GeminiProvider


# from providers.stt.base import STTProvider
# from providers.stt.huggingface import HuggingFaceSTTProvider
settings = get_settings()

_provider_cache: dict[str, LLMProvider] = {}

def get_llm_provider(provider: str | None = None) -> LLMProvider:
    provider_name = provider or settings.LLM_PROVIDER
    if provider_name not in _provider_cache:
        if provider_name == "vllm":
            _provider_cache[provider_name] = VLLMProvider()
        else:
            _provider_cache[provider_name] = GeminiProvider()
    return _provider_cache[provider_name]


# @lru_cache  
# def get_stt_provider() -> STTProvider:
#     if settings.STT_PROVIDER == "huggingface":

#         return HuggingFaceSTTProvider()

#     return RunpodSTTProvider()