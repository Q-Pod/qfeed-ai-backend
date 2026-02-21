from typing import Callable, Awaitable
import time

from langsmith import traceable

from core.config import get_settings
from core.logging import get_logger
from core.tracing import record_tool_metrics
from exceptions.exceptions import AppException
from exceptions.error_messages import ErrorMessage
from providers.stt.huggingface import transcribe
from providers.stt.gpu_stt import transcribe as runpod_transcribe   

logger = get_logger(__name__)

# Provider 함수 타입
TranscribeFunc = Callable[[str], Awaitable[str]]
settings = get_settings()

def get_stt_provider() -> tuple[TranscribeFunc, str]:
    """설정에 따라 STT provider와 이름 반환"""
    if settings.STT_PROVIDER == "gpu_stt":
        return runpod_transcribe, "gpu_stt"
    return transcribe, "huggingface"


@traceable(run_type="chain", name="STT_service")
async def process_transcribe(audio_url: str) -> str:
    """음성 파일을 텍스트로 변환 처리"""
    start_time = time.perf_counter()
    file_name = audio_url.split('?')[0].split('/')[-1] if audio_url else "unknown"
    logger.debug(f"STT transcribe start | file={file_name}")

    # 2. STT 변환 처리
    provider, provider_name = get_stt_provider()

    try:
        text = await provider(audio_url)

        if not text or not text.strip():
            logger.warning(f"STT result is empty | file={file_name}")
            
            record_tool_metrics(
                tool_name="process_transcribe",
                latency_ms=(time.perf_counter() - start_time) * 1000,
                success=False,
                provider=provider_name,
                error="empty_result",
            )
            
            raise AppException(ErrorMessage.AUDIO_UNPROCESSABLE)

        latency_ms = (time.perf_counter() - start_time) * 1000

        logger.info(f"STT transcribe completed | file={file_name}")

        # 메트릭 기록
        record_tool_metrics(
            tool_name="STT_service",
            latency_ms=latency_ms,
            success=True,
            provider=provider_name,
            text_length=len(text),
            file_name=file_name,
        )

        return text
    except AppException:
        raise
    except Exception as e:
        logger.error(f"STT transcribe error | file={file_name} | {type(e).__name__}: {e}")
        
        record_tool_metrics(
            tool_name="STT_service",
            latency_ms=(time.perf_counter() - start_time) * 1000,
            success=False,
            provider=provider_name,
            error=str(e)[:200],
        )
        
        raise AppException(ErrorMessage.STT_CONVERSION_FAILED) from e
