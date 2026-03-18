# tests/unit/providers/test_fallback.py

import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import BaseModel

from exceptions.exceptions import AppException
from exceptions.error_messages import ErrorMessage
from providers.llm.fallback import FallbackLLMProvider
from providers.stt.fallback import FallbackSTTProvider


# ============================================
# 테스트용 Pydantic 모델
# ============================================

class DummyOutput(BaseModel):
    text: str


# ============================================
# FallbackLLMProvider 테스트
# ============================================

class TestFallbackLLMProvider:

    def _make_provider(self, retry_interval: int = 300) -> tuple:
        primary = MagicMock()
        primary.provider_name = "vllm"
        primary.generate_structured = AsyncMock()
        primary.generate = AsyncMock()

        fallback = MagicMock()
        fallback.provider_name = "gemini"
        fallback.generate_structured = AsyncMock()
        fallback.generate = AsyncMock()

        provider = FallbackLLMProvider(
            primary=primary,
            fallback=fallback,
            retry_interval=retry_interval,
        )
        return provider, primary, fallback

    # --- 정상 동작 ---

    @pytest.mark.asyncio
    async def test_primary_성공시_primary_결과_반환(self):
        provider, primary, fallback = self._make_provider()
        expected = DummyOutput(text="vllm result")
        primary.generate_structured.return_value = expected

        result = await provider.generate_structured(
            prompt="test", response_model=DummyOutput
        )

        assert result == expected
        primary.generate_structured.assert_called_once()
        fallback.generate_structured.assert_not_called()

    @pytest.mark.asyncio
    async def test_provider_name_정상시_primary(self):
        provider, _, _ = self._make_provider()
        assert provider.provider_name == "vllm"

    # --- Fallback 전환 ---

    @pytest.mark.asyncio
    async def test_SERVICE_UNAVAILABLE시_fallback_전환(self):
        provider, primary, fallback = self._make_provider()
        primary.generate_structured.side_effect = AppException(
            ErrorMessage.LLM_SERVICE_UNAVAILABLE
        )
        expected = DummyOutput(text="gemini result")
        fallback.generate_structured.return_value = expected

        result = await provider.generate_structured(
            prompt="test", response_model=DummyOutput
        )

        assert result == expected
        assert provider.provider_name == "gemini"

    @pytest.mark.asyncio
    async def test_TIMEOUT시_fallback_전환(self):
        provider, primary, fallback = self._make_provider()
        primary.generate_structured.side_effect = AppException(
            ErrorMessage.LLM_TIMEOUT
        )
        expected = DummyOutput(text="gemini result")
        fallback.generate_structured.return_value = expected

        result = await provider.generate_structured(
            prompt="test", response_model=DummyOutput
        )

        assert result == expected
        assert provider.provider_name == "gemini"

    @pytest.mark.asyncio
    async def test_PARSE_FAILED는_fallback하지_않고_raise(self):
        provider, primary, _ = self._make_provider()
        primary.generate_structured.side_effect = AppException(
            ErrorMessage.LLM_RESPONSE_PARSE_FAILED
        )

        with pytest.raises(AppException) as exc_info:
            await provider.generate_structured(
                prompt="test", response_model=DummyOutput
            )

        assert exc_info.value.message == ErrorMessage.LLM_RESPONSE_PARSE_FAILED
        assert provider.provider_name == "vllm"

    # --- TTL 동작 ---

    @pytest.mark.asyncio
    async def test_fallback_상태에서_TTL_내_요청은_fallback_유지(self):
        provider, primary, fallback = self._make_provider(retry_interval=300)
        primary.generate_structured.side_effect = AppException(
            ErrorMessage.LLM_SERVICE_UNAVAILABLE
        )
        fallback.generate_structured.return_value = DummyOutput(text="gemini")

        await provider.generate_structured(prompt="1st", response_model=DummyOutput)
        assert provider.provider_name == "gemini"

        primary.generate_structured.reset_mock()
        await provider.generate_structured(prompt="2nd", response_model=DummyOutput)

        primary.generate_structured.assert_not_called()
        assert fallback.generate_structured.call_count == 2

    @pytest.mark.asyncio
    async def test_TTL_만료후_primary_재시도_성공시_복귀(self):
        provider, primary, fallback = self._make_provider(retry_interval=1)

        primary.generate_structured.side_effect = AppException(
            ErrorMessage.LLM_SERVICE_UNAVAILABLE
        )
        fallback.generate_structured.return_value = DummyOutput(text="gemini")
        await provider.generate_structured(prompt="fail", response_model=DummyOutput)
        assert provider.provider_name == "gemini"

        time.sleep(1.1)

        expected = DummyOutput(text="vllm recovered")
        primary.generate_structured.side_effect = None
        primary.generate_structured.return_value = expected

        result = await provider.generate_structured(
            prompt="retry", response_model=DummyOutput
        )

        assert result == expected
        assert provider.provider_name == "vllm"

    @pytest.mark.asyncio
    async def test_TTL_만료후_primary_재시도_실패시_TTL_갱신(self):
        provider, primary, fallback = self._make_provider(retry_interval=1)

        primary.generate_structured.side_effect = AppException(
            ErrorMessage.LLM_SERVICE_UNAVAILABLE
        )
        fallback.generate_structured.return_value = DummyOutput(text="gemini")
        await provider.generate_structured(prompt="fail", response_model=DummyOutput)

        time.sleep(1.1)

        result = await provider.generate_structured(
            prompt="retry-fail", response_model=DummyOutput
        )

        assert result.text == "gemini"
        assert provider.provider_name == "gemini"
        assert provider._fallback_since is not None

    # --- generate 메서드도 동일 패턴 ---

    @pytest.mark.asyncio
    async def test_generate_메서드도_fallback_동작(self):
        provider, primary, fallback = self._make_provider()
        primary.generate.side_effect = AppException(
            ErrorMessage.LLM_SERVICE_UNAVAILABLE
        )
        fallback.generate.return_value = "gemini text"

        result = await provider.generate(
            prompt="test", response_model=DummyOutput
        )

        assert result == "gemini text"
        assert provider.provider_name == "gemini"


# ============================================
# FallbackSTTProvider 테스트
# ============================================

class TestFallbackSTTProvider:

    def _make_provider(self, retry_interval: int = 300) -> tuple:
        primary_fn = AsyncMock()
        fallback_fn = AsyncMock()

        provider = FallbackSTTProvider(
            primary_fn=primary_fn,
            primary_name="gpu_stt",
            fallback_fn=fallback_fn,
            fallback_name="huggingface",
            retry_interval=retry_interval,
        )
        return provider, primary_fn, fallback_fn

    # --- 정상 동작 ---

    @pytest.mark.asyncio
    async def test_primary_성공시_primary_결과_반환(self):
        provider, primary_fn, fallback_fn = self._make_provider()
        primary_fn.return_value = "gpu stt result"

        result = await provider.transcribe("http://example.com/audio.mp4")

        assert result == "gpu stt result"
        primary_fn.assert_called_once()
        fallback_fn.assert_not_called()

    @pytest.mark.asyncio
    async def test_provider_name_정상시_primary(self):
        provider, _, _ = self._make_provider()
        assert provider.provider_name == "gpu_stt"

    # --- Fallback 전환 ---

    @pytest.mark.asyncio
    async def test_SERVICE_UNAVAILABLE시_fallback_전환(self):
        provider, primary_fn, fallback_fn = self._make_provider()
        primary_fn.side_effect = AppException(ErrorMessage.STT_SERVICE_UNAVAILABLE)
        fallback_fn.return_value = "huggingface result"

        result = await provider.transcribe("http://example.com/audio.mp4")

        assert result == "huggingface result"
        assert provider.provider_name == "huggingface"

    @pytest.mark.asyncio
    async def test_STT_TIMEOUT시_fallback_전환(self):
        provider, primary_fn, fallback_fn = self._make_provider()
        primary_fn.side_effect = AppException(ErrorMessage.STT_TIMEOUT)
        fallback_fn.return_value = "huggingface result"

        result = await provider.transcribe("http://example.com/audio.mp4")

        assert result == "huggingface result"
        assert provider.provider_name == "huggingface"

    @pytest.mark.asyncio
    async def test_SERVER_CONNECTION_FAILED시_fallback_전환(self):
        provider, primary_fn, fallback_fn = self._make_provider()
        primary_fn.side_effect = AppException(ErrorMessage.SERVER_CONNECTION_FAILED)
        fallback_fn.return_value = "huggingface result"

        result = await provider.transcribe("http://example.com/audio.mp4")

        assert result == "huggingface result"
        assert provider.provider_name == "huggingface"

    @pytest.mark.asyncio
    async def test_AUDIO_UNPROCESSABLE은_fallback하지_않고_raise(self):
        provider, primary_fn, _ = self._make_provider()
        primary_fn.side_effect = AppException(ErrorMessage.AUDIO_UNPROCESSABLE)

        with pytest.raises(AppException) as exc_info:
            await provider.transcribe("http://example.com/audio.mp4")

        assert exc_info.value.message == ErrorMessage.AUDIO_UNPROCESSABLE
        assert provider.provider_name == "gpu_stt"

    @pytest.mark.asyncio
    async def test_STT_CONVERSION_FAILED는_fallback하지_않고_raise(self):
        provider, primary_fn, _ = self._make_provider()
        primary_fn.side_effect = AppException(ErrorMessage.STT_CONVERSION_FAILED)

        with pytest.raises(AppException) as exc_info:
            await provider.transcribe("http://example.com/audio.mp4")

        assert exc_info.value.message == ErrorMessage.STT_CONVERSION_FAILED
        assert provider.provider_name == "gpu_stt"

    # --- TTL 동작 ---

    @pytest.mark.asyncio
    async def test_fallback_상태에서_TTL_내_요청은_fallback_유지(self):
        provider, primary_fn, fallback_fn = self._make_provider(retry_interval=300)
        primary_fn.side_effect = AppException(ErrorMessage.STT_SERVICE_UNAVAILABLE)
        fallback_fn.return_value = "huggingface"

        await provider.transcribe("http://example.com/1.mp4")
        assert provider.provider_name == "huggingface"

        primary_fn.reset_mock()
        await provider.transcribe("http://example.com/2.mp4")

        primary_fn.assert_not_called()
        assert fallback_fn.call_count == 2

    @pytest.mark.asyncio
    async def test_TTL_만료후_primary_재시도_성공시_복귀(self):
        provider, primary_fn, fallback_fn = self._make_provider(retry_interval=1)

        primary_fn.side_effect = AppException(ErrorMessage.STT_SERVICE_UNAVAILABLE)
        fallback_fn.return_value = "huggingface"
        await provider.transcribe("http://example.com/fail.mp4")
        assert provider.provider_name == "huggingface"

        time.sleep(1.1)

        primary_fn.side_effect = None
        primary_fn.return_value = "gpu recovered"

        result = await provider.transcribe("http://example.com/retry.mp4")

        assert result == "gpu recovered"
        assert provider.provider_name == "gpu_stt"

    @pytest.mark.asyncio
    async def test_TTL_만료후_primary_재시도_실패시_TTL_갱신(self):
        provider, primary_fn, fallback_fn = self._make_provider(retry_interval=1)

        primary_fn.side_effect = AppException(ErrorMessage.SERVER_CONNECTION_FAILED)
        fallback_fn.return_value = "huggingface"
        await provider.transcribe("http://example.com/fail.mp4")

        time.sleep(1.1)

        result = await provider.transcribe("http://example.com/retry.mp4")

        assert result == "huggingface"
        assert provider.provider_name == "huggingface"
        assert provider._fallback_since is not None
