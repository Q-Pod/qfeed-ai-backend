from typing import Callable, Awaitable

from langfuse import observe

from core.config import get_settings
from core.logging import get_logger
from core.tracing import update_span
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


@observe(name="stt_service")
async def process_transcribe(audio_url: str) -> str:
    """음성 파일을 텍스트로 변환 처리"""

    file_name = audio_url.split('?')[0].split('/')[-1] if audio_url else "unknown"
    logger.debug(f"STT transcribe start | file={file_name}")

    # 2. STT 변환 처리
    provider, provider_name = get_stt_provider()
    update_span(metadata={"provider": provider_name, "file_name": file_name})

    try:
        text = await provider(audio_url)

        if not text or not text.strip():
            logger.warning(f"STT result is empty | file={file_name}")   
            raise AppException(ErrorMessage.AUDIO_UNPROCESSABLE)

        logger.info(f"STT transcribe completed | file={file_name}")
        update_span(output={"text_length": len(text)})

        return text
    except AppException:
        raise
    except Exception as e:
        logger.error(f"STT transcribe error | file={file_name} | {type(e).__name__}: {e}")
        raise AppException(ErrorMessage.STT_CONVERSION_FAILED) from e
