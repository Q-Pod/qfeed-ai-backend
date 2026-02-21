import httpx
import time
from pathlib import Path

from langsmith import traceable

from core.config import get_settings
from core.logging import get_logger
from core.tracing import record_stt_metrics, record_tool_metrics
from exceptions.exceptions import AppException
from exceptions.error_messages import ErrorMessage

logger = get_logger(__name__)   
settings = get_settings()

# MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
API_URL = "https://router.huggingface.co/hf-inference/models/openai/whisper-large-v3-turbo"
headers = {
    "Authorization": f"Bearer {settings.HUGGINGFACE_API_KEY}",
}

CONTENT_TYPE_MAP = {
    ".mp3": "audio/mpeg",
    ".mp4": "audio/x-m4a",
    ".m4a": "audio/x-m4a",
}

@traceable(run_type="tool", name="download_audio")
async def download_audio(url: str) -> bytes:
    """오디오 다운로드"""
    start_time = time.perf_counter()
    logger.debug("오디오 다운로드 시작")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            
            if response.status_code == 404:
                logger.warning("오디오 파일 없음 | status=404")
                raise AppException(ErrorMessage.AUDIO_NOT_FOUND)
            elif response.status_code == 403:
                logger.warning("S3 접근 거부 | status=403")
                raise AppException(ErrorMessage.S3_ACCESS_FORBIDDEN)
            
            response.raise_for_status()
            audio_data = response.content

            latency_ms = (time.perf_counter() - start_time) * 1000
            audio_size_kb = len(audio_data) / 1024

            logger.info(f"size={audio_size_kb:.1f}KB")

            record_tool_metrics(
                tool_name="download_audio",
                latency_ms=latency_ms,
                success=True,
                audio_size_kb=round(audio_size_kb, 1),
            )
            return audio_data
            
    except AppException:
        raise  # 우리가 던진 건 그대로 전파
    except httpx.TimeoutException:
        logger.error("오디오 다운로드 타임 아웃")
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


def get_content_type(audio_url: str) -> str:
    ext = Path(audio_url).suffix.lower()  # URL에서 확장자 추출
    # 쿼리 파라미터 제거 필요!
    if '?' in audio_url:
        audio_url = audio_url.split('?')[0]
    ext = Path(audio_url).suffix.lower()
    return CONTENT_TYPE_MAP[ext]

@traceable(run_type="tool", name="huggingface_stt")
async def transcribe(audio_url: str) -> str:
    """Presigned URL에서 오디오 다운로드하여 STT 수행"""
    content_type = get_content_type(audio_url)
    audio_data = await download_audio(audio_url)

    logger.debug("Huggingface API 호출 시작 | model=whisper-large-v3-turbo | content_type={content_type} | audio_size={audio_size_kb:.1f}KB")
    api_start = time.perf_counter()

    # Huggingface API 호출
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                API_URL,
                headers={"Content-Type": content_type, **headers},
                content=audio_data,
            )
            response.raise_for_status()
            text = response.json()["text"]
            
            api_elapsed_ms = (time.perf_counter() - api_start) * 1000
            logger.info(f"Huggingface API 완료(순수 STT 시간) | {api_elapsed_ms:.2f}ms")
            
            # LangSmith 메트릭 기록
            record_stt_metrics(
                provider="huggingface",
                model="whisper-large-v3-turbo",
                latency_ms=api_elapsed_ms,
                transcribed_text_length=len(text),
            )
            
            return text
    except httpx.TimeoutException:
        logger.error("Huggingface API 타임아웃 ")
        record_stt_metrics(
            provider="huggingface",
            model="whisper-large-v3-turbo",
            latency_ms=(time.perf_counter() - api_start) * 1000,
            transcribed_text_length=0,
        )
        raise AppException(ErrorMessage.STT_TIMEOUT)
    except httpx.HTTPStatusError as e:
        error_detail = e.response.json() if e.response.content else {}
        logger.error(
            "HuggingFace API 400 에러 상세",
            extra={
                "status_code": e.response.status_code,
                "error_detail": error_detail,
            }
        )
        if e.response.status_code == 401:
            logger.warning("Huggingface API 인증 실패")
            raise AppException(ErrorMessage.API_KEY_INVALID)
        if e.response.status_code == 429:
            logger.warning("Huggingface Rate Limit 초과")
            raise AppException(ErrorMessage.RATE_LIMIT_EXCEEDED)
        raise AppException(ErrorMessage.STT_CONVERSION_FAILED)
        
