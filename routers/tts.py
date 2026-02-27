from fastapi import APIRouter
from fastapi.responses import Response
from schemas.tts import TTSRequest
from services.tts_service import tts_transcribe
from core.logging import get_logger, log_execution_time
import json

router = APIRouter()
logger = get_logger(__name__)


@router.post("/tts")
@log_execution_time(logger)
async def text_to_speech(request: TTSRequest) -> Response:
    """TTS 엔드포인트 - 텍스트를 음성으로 변환"""
    logger.info(f"TTS 요청 시작 | user_id={request.user_id}, session_id={request.session_id}")

    audio_data = await tts_transcribe(str(request.text))

    # JSON 파트 구성
    json_data = {
        "message": "get_audio_file_success",
        "data": {
            "user_id": request.user_id,
            "session_id": request.session_id
        }
    }
    json_content = json.dumps(json_data, ensure_ascii=False)
    
    # Multipart body 구성
    boundary = "----AudioBoundary"
    
    body = (
        f"--{boundary}\r\n"
        f"Content-Type: application/json; charset=utf-8\r\n"
        f"\r\n"
        f"{json_content}\r\n"
        f"--{boundary}\r\n"
        f"Content-Type: audio/mpeg\r\n"
        f"Content-Disposition: attachment\r\n"
    ).encode('utf-8') + audio_data + f"\r\n--{boundary}--\r\n".encode('utf-8')

    logger.info(f"TTS 요청 완료 | user_id={request.user_id}, audio_size={len(audio_data)} bytes")

    return Response(
        content=body,
        media_type=f"multipart/mixed; boundary={boundary}"
    )