# core/config.py
import os
from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Literal
from utils.ssm_loader import get_ssm_loader

class Settings(BaseSettings):
    ENVIRONMENT: Literal["prod", "dev", "local"] = "local"

    # SSM Parameter Store 경로 (production, dev 환경에서 외부 주입)
    AWS_PARAMETER_STORE_PATH: str | None = None

    # 로그 설정
    LOG_DIR: str | None = None

    @property
    def log_directory(self) -> str:
        if self.LOG_DIR and self.LOG_DIR.strip():
            return self.LOG_DIR
        # 환경별 기본값
        log_dirs = {
            "local": "./logs",
            "dev": "/var/log/qfeed/ai",
            "prod": "/var/log/qfeed/ai",
        }
        return log_dirs.get(self.ENVIRONMENT, "./logs")
    
    STT_PROVIDER: str = "gpu_stt"  #huggingface or "gpu_stt"
    LLM_PROVIDER: str = "vllm"  # "gemini" or "vllm"

    #v1 : STT
    HUGGINGFACE_API_KEY: str
    HUGGINGFACE_MODEL_ID: str = "openai/whisper-large-v3-turbo"

    # gemini
    GEMINI_API_KEY: str
    GEMINI_MODEL_ID: str = "gemini-2.5-flash"

    # Callback 설정 (V2)
    feedback_callback_url: str = "http://backend-server/ai/interview/feedback/callback"
    callback_timeout_seconds: int = 30

    # GPU 서버 URL (외부 주입 - Runpod 등으로 이전 시 환경변수만 변경)
    GPU_STT_URL: str | None = None  
    GPU_LLM_URL: str | None = None   

    LLM_MODEL_ID: str = "skt/A.X-4.0-Light"
    # LLM_MODEL_ID: str = "openai/gpt-oss-20b"

    # TTS(eleven_labs)
    ELEVENLABS_API_KEY: str
    ELEVENLABS_VOICE_IDS: str = "a52RveZOORPA9buQulXm,z6Kj0hecH20CdetSElRT,pb3lVZVjdFWbkhPKlelB" #daehyeok,jennie,harry
    ELEVENLABS_MODEL_ID: str = "eleven_flash_v2_5"

    @property
    def elevenlabs_voice_id_list(self) -> list[str]:
        """VOICE_IDS를 리스트로 변환"""
        return [v.strip() for v in self.ELEVENLABS_VOICE_IDS.split(",")]


    # Langfuse
    LANGFUSE_PUBLIC_KEY: str
    LANGFUSE_SECRET_KEY: str
    LANGFUSE_HOST: str = "https://us.cloud.langfuse.com"

    
    model_config = {
        "env_file": ".env",
        "extra": "ignore",  # 정의되지 않은 환경변수 무시 (E2E 테스트용 등)
    }

def _load_ssm_secrets(base_path: str) -> None:
    """SSM Parameter Store에서 시크릿을 로드하여 환경변수로 설정
    
    Args:
        base_path: SSM 경로의 base path (예: /qfeed/prod/ai)
    """
    loader = get_ssm_loader()
    
    # base_path 끝의 슬래시 제거
    base_path = base_path.rstrip("/")

    ssm_keys = {
        "HUGGINGFACE_API_KEY": "huggingface-api-key",
        "GEMINI_API_KEY": "gemini-api-key",
        "ELEVENLABS_API_KEY": "elevenlabs-api-key",
        "LANGFUSE_PUBLIC_KEY": "langfuse-public-key",
        "LANGFUSE_SECRET_KEY": "langfuse-secret-key",
    }

    for env_var, key_name in ssm_keys.items():
        if env_var not in os.environ:
            ssm_path = f"{base_path}/{key_name}"
            value = loader.get_parameter(ssm_path, required=False)
            if value:
                os.environ[env_var] = value

def _configure_langfuse(settings: Settings) -> None:
    """Langfuse SDK가 환경변수에서 읽을 수 있도록 설정"""
    if settings.LANGFUSE_PUBLIC_KEY:
        os.environ["LANGFUSE_PUBLIC_KEY"] = settings.LANGFUSE_PUBLIC_KEY
    if settings.LANGFUSE_SECRET_KEY:
        os.environ["LANGFUSE_SECRET_KEY"] = settings.LANGFUSE_SECRET_KEY
    if settings.LANGFUSE_HOST:
        os.environ["LANGFUSE_HOST"] = settings.LANGFUSE_HOST

@lru_cache
def get_settings() -> Settings:
    """환경에 따라 설정 로드
    
    - prod, dev: AWS SSM Parameter Store에서 시크릿 로드
      (AWS_PARAMETER_STORE_PATH 환경변수로 base path 지정 필요)
    - local: .env 파일에서 로드 (로컬 개발/테스트용)
    """
    environment = os.getenv("ENVIRONMENT", "local")

    # prod, dev 환경에서는 SSM에서 시크릿 로드
    if environment in ("prod", "dev"):
        base_path = os.getenv("AWS_PARAMETER_STORE_PATH")
        
        if not base_path:
            raise ValueError(
                f"AWS_PARAMETER_STORE_PATH 환경변수가 필요합니다. "
                f"(ENVIRONMENT={environment})"
            )
        
        _load_ssm_secrets(base_path)

    settings = Settings()
    # Langfuse SDK용 환경변수 설정
    _configure_langfuse(settings)
    print(f"=== ENVIRONMENT: {settings.ENVIRONMENT} ===")
    return settings
