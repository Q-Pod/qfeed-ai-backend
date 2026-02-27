from fastapi import APIRouter
from schemas.stt import STTRequest, STTResponse, STTData
from services.stt_service import process_transcribe
from core.logging import get_logger, log_execution_time

router = APIRouter()
logger = get_logger(__name__)


@router.post("/stt")
@log_execution_time(logger)
async def speech_to_text(request: STTRequest) -> STTResponse:
    logger.info(f"STT request | user_id={request.user_id}, session_id={request.session_id}")
    text = await process_transcribe(str(request.audio_url))
    # 시간넣을지 고민해보기
    logger.info(f"STT request completed | text_length={len(text)}")
    return STTResponse(
        message="speech_to_text_success",
        data=STTData(user_id=request.user_id, session_id=request.session_id, text=text)
    )
