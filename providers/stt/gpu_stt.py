import httpx
import time 
from pathlib import Path

from langfuse import observe

from core.config import get_settings
from core.logging import get_logger
from core.tracing import update_span
from exceptions.exceptions import AppException
from exceptions.error_messages import ErrorMessage

logger = get_logger(__name__) 
settings = get_settings()

@observe(name="gpu_stt_download_audio")
async def download_audio(url: str) -> bytes:
    """오디오 다운로드"""
    start_time = time.perf_counter()
    logger.debug("audio download start")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            
            if response.status_code == 404:
                logger.warning("audio not found | status=404")
                raise AppException(ErrorMessage.AUDIO_NOT_FOUND)
            elif response.status_code == 403:
                logger.warning("S3 access forbidden | status=403")
                raise AppException(ErrorMessage.S3_ACCESS_FORBIDDEN)
            
            response.raise_for_status()
            audio_data = response.content

            latency_ms = (time.perf_counter() - start_time) * 1000

            logger.info(f"size={len(audio_data) / 1024:.1f}KB")

            
            return audio_data, latency_ms
            
    except AppException:
        raise  # 우리가 던진 건 그대로 전파
    except httpx.TimeoutException:
        logger.error("오디오 다운로드 타임 아웃")
        # record_tool_metrics(
        #     tool_name="download_audio",
        #     latency_ms=(time.perf_counter() - start_time) * 1000,
        #     success=False,
        #     error="timeout",
        # )
        raise AppException(ErrorMessage.AUDIO_DOWNLOAD_TIMEOUT)
    except httpx.HTTPStatusError as e:
        if e.response.status_code >= 500:
            logger.error(f"서버 내부 오류 | status={e.response.status_code}")
            raise AppException(ErrorMessage.INTERNAL_SERVER_ERROR)
        logger.error(f"오디오 다운로드 에러 | status={e.response.status_code}")
        raise AppException(ErrorMessage.AUDIO_DOWNLOAD_FAILED)
    except httpx.RequestError as re:
        logger.error(f"네트워크 연결 실패 | {type(re).__name__}: {re}")
        raise AppException(ErrorMessage.AUDIO_DOWNLOAD_FAILED)
    except Exception as e:
        # 예상치 못한 에러
        logger.error(f"오디오 다운로드 예외 |{type(e).__name__}: {e}")
        raise AppException(ErrorMessage.AUDIO_DOWNLOAD_FAILED)
    
def get_filename(audio_url: str) -> str:
    """URL에서 파일명 추출"""
    if "?" in audio_url:
        audio_url = audio_url.split("?")[0]
    return Path(audio_url).name or "audio.mp4"

@observe(name="gpu_stt_transcribe")
async def transcribe(audio_url: str, language: str = "ko") -> str:
    """Presigned URL에서 오디오 다운로드하여 RunPod GPU 인스턴스로 STT 수행"""
    filename = get_filename(audio_url)
    audio_data, download_latency = await download_audio(audio_url)
    audio_size_kb = len(audio_data) / 1024

    logger.debug(
        f"STT model call | model=whisper-large-v3-turbo | "
        f"filename={filename} | audio_size={audio_size_kb:.1f}KB"
    )
    api_start = time.perf_counter()

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{settings.GPU_STT_URL}/whisper/stt",
                files={"audio": (filename, audio_data)},
                data={"language": language},
            )

            if response.status_code == 503:
                logger.error("stt_service_unavailtalbe | status=503")
                raise AppException(ErrorMessage.STT_SERVICE_UNAVAILABLE)

            if response.status_code == 400:
                logger.error(f"audio decoding failed | detail={response.text}")
                raise AppException(ErrorMessage.AUDIO_UNPROCESSABLE)

            response.raise_for_status()
            result = response.json()
            text = result.get("text", "").strip()

            api_elapsed_ms = (time.perf_counter() - api_start) * 1000
            audio_duration_sec = result.get("duration", 0)

            logger.info(
                f"stt model call completed | duration={result.get('duration', 0):.1f}s | "
                f"processing_time={result.get('processing_time_ms', 0):.0f}ms | "
                f"api_latency={api_elapsed_ms:.0f}ms"
            )

            update_span(metadata={
                "model": "whisper-large-v3-turbo",
                "language": language,
                "audio_size_kb": round(audio_size_kb, 1),
                "audio_duration_sec": audio_duration_sec if audio_duration_sec > 0 else None,
                "download_latency_ms": round(download_latency, 1),
                "api_latency_ms": round(api_elapsed_ms, 1),
                "server_processing_ms": result.get("processing_time_ms", 0),
                "transcribed_text_length": len(text),
            })

            return text

    except AppException:
        raise
    except httpx.TimeoutException:
        logger.error("stt model call timeout")
        # record_stt_metrics(
        #     provider="runpod",
        #     model="whisper-large-v3-turbo",
        #     latency_ms=(time.perf_counter() - api_start) * 1000,
        #     transcribed_text_length=0,
        #     language=language,
        # )
        raise AppException(ErrorMessage.STT_TIMEOUT)
    except httpx.HTTPStatusError as e:
        logger.error(
            "stt model call error",
            extra={
                "status_code": e.response.status_code,
                "response_text": e.response.text,
            },
        )
        if e.response.status_code == 429:
            logger.warning("stt call rate limit exceeded")
            raise AppException(ErrorMessage.RATE_LIMIT_EXCEEDED)
        raise AppException(ErrorMessage.STT_CONVERSION_FAILED)
    except httpx.RequestError as re:
        logger.error(f"gpu server connetion failed | {type(re).__name__}: {re}")
        raise AppException(ErrorMessage.SERVER_CONNECTION_FAILED)
    except Exception as e:
        logger.error(f"stt conversion failed | {type(e).__name__}: {e}")
        raise AppException(ErrorMessage.STT_CONVERSION_FAILED)