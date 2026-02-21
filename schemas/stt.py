from pydantic import BaseModel, Field, HttpUrl, field_validator
from urllib.parse import urlparse

from schemas.common import BaseResponse

class STTRequest(BaseModel):
    user_id : int = Field(..., description="사용자 ID")
    session_id : str | None = Field(None, description="세션 ID")
    audio_url : str = Field(..., description="음성 파일 URL")

    # 오디오 파일 확장자 검증
    @field_validator("audio_url")
    @classmethod
    def validate_audio_extension(cls, v:HttpUrl) -> HttpUrl:
        path = urlparse(str(v)).path
        allowed_extensions = ('.mp3', '.m4a', 'mp4') 
        if not path.endswith(allowed_extensions):
            raise ValueError("audio_url must end with .mp3, .m4a, .mp4")
        return v

class STTData(BaseModel):
    user_id : int = Field(..., description="사용자 ID")
    session_id : int | None = Field(None, description="세션 ID")
    text: str = Field(..., description="변환된 텍스트")

STTResponse = BaseResponse[STTData]