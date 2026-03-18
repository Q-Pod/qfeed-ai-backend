# core/dependencies.py
from core.config import get_settings
from providers.llm.base import LLMProvider
from providers.llm.vllm import VLLMProvider
from providers.llm.gemini import GeminiProvider
from providers.llm.fallback import FallbackLLMProvider
from providers.stt.huggingface import transcribe as hf_transcribe
from providers.stt.gpu_stt import transcribe as gpu_transcribe
from providers.stt.base import STTProvider, SimpleSTTProvider
from providers.stt.fallback import FallbackSTTProvider

settings = get_settings()

_llm_cache: dict[str, LLMProvider] = {}
_stt_cache: dict[str, STTProvider] = {}


def get_llm_provider(provider: str | None = None) -> LLMProvider:
    provider_name = provider or settings.LLM_PROVIDER
    if provider_name not in _llm_cache:
        if provider_name == "vllm":
            _llm_cache[provider_name] = FallbackLLMProvider(
                primary=VLLMProvider(),
                fallback=GeminiProvider(thinking_budget=0),
            )
        elif provider_name == "gemini_lite":
            _llm_cache[provider_name] = GeminiProvider(
                model=settings.GEMINI_LITE_MODEL_ID,
                thinking_budget=0,
            )
        elif provider_name == "gemini":
            _llm_cache[provider_name] = GeminiProvider(thinking_budget=0)
        else:
            _llm_cache[provider_name] = GeminiProvider(thinking_budget=1024)
    return _llm_cache[provider_name]

def get_stt_provider(provider: str | None = None) -> STTProvider:
    provider_name = provider or settings.STT_PROVIDER
    if provider_name not in _stt_cache:
        if provider_name == "gpu_stt":
            _stt_cache[provider_name] = FallbackSTTProvider(
                primary_fn=gpu_transcribe,
                primary_name="gpu_stt",
                fallback_fn=hf_transcribe,
                fallback_name="huggingface",
            )
        else:
            _stt_cache[provider_name] = SimpleSTTProvider(
                transcribe_fn=hf_transcribe,
                name="huggingface",
            )
    return _stt_cache[provider_name]