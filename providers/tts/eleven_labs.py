import httpx
import secrets
import time
from typing import Optional
from langsmith import traceable
from core.config import get_settings
from core.logging import get_logger
from core.tracing import record_tts_metrics
from exceptions.exceptions import AppException
from exceptions.error_messages import ErrorMessage

logger = get_logger(__name__)
settings = get_settings()

class ElevenLabsTTSProvider:
    """ElevenLabs TTS Provider 구현체"""
    
    BASE_URL = "https://api.elevenlabs.io/v1"
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        voice_ids: Optional[list[str]] = None,
        model_id: Optional[str] = None,
    ):
        self.api_key = api_key or settings.ELEVENLABS_API_KEY
        self.voice_ids = voice_ids or settings.elevenlabs_voice_id_list
        self.model_id = model_id or settings.ELEVENLABS_MODEL_ID

    def _get_random_voice_id(self) -> str:
        """랜덤하게 voice_id 선택"""
        return secrets.choice(self.voice_ids)

    @traceable(run_type="llm", name="elevenlabs_provider")
    async def synthesize(
        self,
        text: str,
        voice_id: Optional[str] = None,
        output_format: str = "mp3_44100_128"
    ) -> bytes:
        """텍스트를 음성으로 변환"""

        start_time = time.time()

        # voice_id 지정 안 하면 랜덤 선택
        selected_voice_id = voice_id or self._get_random_voice_id()

        url = f"{self.BASE_URL}/text-to-speech/{selected_voice_id}"
        
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg"
        }
        
        payload = {
            "text": text,
            "model_id": self.model_id,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
                "use_speaker_boost": True
            }
        }
        
        logger.debug(f"ElevenLabs TTS 요청 | voice_id={self.voice_ids}, text_length={len(text)}")
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    url,
                    headers=headers,
                    json=payload,
                    params={"output_format": output_format}
                )
                
                self._handle_response_error(response)
                audio_content = response.content

                latency_ms = (time.time() - start_time) * 1000
                
                # LangSmith 메트릭 기록
                record_tts_metrics(
                    model=self.model_id,
                    latency_ms=latency_ms,
                    text_length=len(text),
                    audio_size_bytes=len(audio_content),
                    voice_id=selected_voice_id,
                )
                
                logger.debug(f"ElevenLabs TTS 완료 | voice_id={selected_voice_id}, audio_size={len(response.content)} bytes")
                return audio_content
                
        except AppException:
            # AppException은 그대로 raise
            raise
        except httpx.TimeoutException:
            logger.error("ElevenLabs API 타임아웃")
            raise AppException(ErrorMessage.TTS_TIMEOUT)
        except httpx.ConnectError:
            logger.error("ElevenLabs API 연결 실패")
            raise AppException(ErrorMessage.TTS_SERVICE_UNAVAILABLE)
        except Exception as e:
            logger.error(f"ElevenLabs TTS 변환 실패: {type(e).__name__}: {e}")
            raise AppException(ErrorMessage.TTS_CONVERSION_FAILED)
        
    def _handle_response_error(self, response: httpx.Response) -> None:
        """HTTP 응답 에러 처리"""
        if response.status_code == 200:
            return
        
        logger.error(f"ElevenLabs API 에러: {response.status_code} - {response.text}")
        
        if response.status_code == 401:
            raise AppException(ErrorMessage.API_KEY_INVALID)
        elif response.status_code == 404:
            raise AppException(ErrorMessage.TTS_VOICE_NOT_FOUND)
        elif response.status_code == 429:
            raise AppException(ErrorMessage.RATE_LIMIT_EXCEEDED)
        elif response.status_code >= 500:
            raise AppException(ErrorMessage.TTS_SERVICE_UNAVAILABLE)
        else:
            raise AppException(ErrorMessage.TTS_CONVERSION_FAILED)
