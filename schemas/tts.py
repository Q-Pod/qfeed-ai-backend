from pydantic import BaseModel, Field


class TTSRequest(BaseModel):
    """TTS 요청 스키마"""
    user_id: int = Field(..., description="사용자 ID")
    session_id: str = Field(..., description="면접 세션 ID")
    text: str = Field(..., description="음성으로 변환할 텍스트")


class TTSData(BaseModel):
    """TTS 응답 데이터"""
    audio_file: bytes = Field(..., description="오디오 파일 바이너리 데이터")


class TTSResponse(BaseModel):
    """TTS 응답 스키마 (JSON 파트용)"""
    message: str = Field(default="get_audio_file_success", description="응답 메시지")