import time
import re

from langsmith import traceable

from providers.tts.eleven_labs import ElevenLabsTTSProvider
from core.logging import get_logger

logger = get_logger(__name__)
tts_provider = ElevenLabsTTSProvider()

@traceable(run_type="chain", name="tts_service")
async def tts_transcribe(text: str) -> bytes:
    """텍스트를 음성으로 변환"""

    start_time = time.time()
    processed_text = preprocess_text(text)

    # 2. ElevenLabs TTS API 호출
    audio_data = await tts_provider.synthesize(processed_text)
    
    elapsed_time = time.time() - start_time
    logger.info(f"TTS 변환 완료 | elapsed={elapsed_time:.2f}s, audio_size={len(audio_data)} bytes")
    
    return audio_data



def preprocess_text(text: str) -> str:
    """TTS를 위한 텍스트 전처리"""
    # 앞뒤 공백 제거
    text = text.strip()
    
    # 연속된 공백을 단일 공백으로
    text = re.sub(r'\s+', ' ', text)
    
    # 필요시 추가 전처리 로직
    # - 특수문자 처리
    # - 숫자 -> 한글 변환
    # - 약어 확장 등
    
    return text