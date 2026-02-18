# core/config.py
import os
from pydantic_settings import BaseSettings
from functools import lru_cache
from utils.ssm_loader import get_ssm_loader

class Settings(BaseSettings):
    ENVIRONMENT: str = "local"  # local | production

    # 로그 설정 추가
    # 배포에서 LOG_DIR을 지정하지 않으면, 환경별 기본 경로를 사용합니다.
    # (EC2 로그 정책 예: /var/log/qfeed/ai)
    LOG_DIR: str | None = None

    @property
    def log_directory(self) -> str:
        if self.LOG_DIR and self.LOG_DIR.strip():
            return self.LOG_DIR
        # 환경별 기본값
        return "./logs" if self.ENVIRONMENT == "local" else "/var/log/qfeed/ai"

    STT_PROVIDER: str = "runpod"  #huggingface or "runpod"
    LLM_PROVIDER: str = "gemini"  # "gemini" or "vllm"

    #v1 : STT
    HUGGINGFACE_API_KEY: str
    HUGGINGFACE_MODEL_ID: str = "openai/whisper-large-v3-turbo"

    # gemini
    GEMINI_API_KEY: str
    GEMINI_MODEL_ID: str = "gemini-2.5-flash"

    # AWS S3 설정
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None
    AWS_REGION: str = "ap-northeast-2"
    # 버킷 설정 - 환경별
    AWS_S3_AUDIO_BUCKET: str | None = None


    # Callback 설정 (V2)
    feedback_callback_url: str = "http://backend-server/ai/interview/feedback/generate"
    callback_timeout_seconds: int = 30

    # GPU 관련 설정
    GPU_BASE_URL: str 
    VLLM_MODEL_ID: str

    # TTS(eleven_labs)
    ELEVENLABS_API_KEY: str
    ELEVENLABS_VOICE_IDS: str = "a52RveZOORPA9buQulXm,z6Kj0hecH20CdetSElRT,pb3lVZVjdFWbkhPKlelB" #daehyeok,jennie,harry
    ELEVENLABS_MODEL_ID: str = "eleven_flash_v2_5"

    @property
    def elevenlabs_voice_id_list(self) -> list[str]:
        """VOICE_IDS를 리스트로 변환"""
        return [v.strip() for v in self.ELEVENLABS_VOICE_IDS.split(",")]


    # LangSmith 설정
    LANGCHAIN_API_KEY: str | None = None
    LANGCHAIN_PROJECT: str | None = None
    LANGSMITH_ENDPOINT: str = "https://api.smith.langchain.com"
    LANGCHAIN_TRACING_V2: str = "true"

    @property
    def langchain_project_name(self) -> str:
        """환경별 LangSmith 프로젝트 이름 반환"""
        if self.LANGCHAIN_PROJECT:
            return self.LANGCHAIN_PROJECT
        
        # 환경별 기본값
        project_names = {
            "local": "qfeed-local",
            "production": "qfeed-prod",
        }
        return project_names.get(self.ENVIRONMENT, f"qfeed-{self.ENVIRONMENT}")

    def configure_langsmith(self, enabled: bool = True):
        """LangSmith 환경변수 설정"""
        if self.LANGCHAIN_API_KEY and enabled:
            os.environ["LANGCHAIN_TRACING_V2"] = self.LANGCHAIN_TRACING_V2
            os.environ["LANGCHAIN_API_KEY"] = self.LANGCHAIN_API_KEY
            os.environ["LANGCHAIN_PROJECT"] = self.langchain_project_name
            os.environ["LANGCHAIN_ENDPOINT"] = self.LANGSMITH_ENDPOINT
        else:
            os.environ["LANGCHAIN_TRACING_V2"] = "false"
    
    model_config = {
        "env_file": ".env",
        "extra": "ignore",  # 정의되지 않은 환경변수 무시 (E2E 테스트용 등)
    }

@lru_cache
def get_settings() -> Settings:
    """환경에 따라 설정 로드"""
    
    # production 환경이면 SSM에서 먼저 로드해서 환경 변수로 설정
    # (Settings() 초기화 전에 필수 필드가 있어야 하므로)
    environment = os.getenv("ENVIRONMENT", "local")
    if environment == "production":
        loader = get_ssm_loader()
        
        # SSM에서 시크릿 로드 후 환경 변수로 설정
        # pydantic_settings는 환경 변수 이름을 필드 이름과 매칭합니다
        # huggingface_api_key -> HUGGINGFACE_API_KEY 또는 huggingface_api_key
        ssm_mappings = {
            "HUGGINGFACE_API_KEY": "/qfeed/prod/ai/huggingface-api-key",
            "GEMINI_API_KEY": "/qfeed/prod/ai/gemini-api-key",
            "AWS_S3_AUDIO_BUCKET": "/qfeed/prod/ai/aws-s3-audio-bucket",
            "LANGCHAIN_API_KEY": "/qfeed/prod/ai/langchain-api-key",
            "ELEVENLABS_API_KEY": "/qfeed/prod/ai/elevenlabs-api-key"
        }
        
        for env_var, ssm_path in ssm_mappings.items():
            if env_var not in os.environ:
                value = loader.get_parameter(ssm_path, required=False)
                if value:
                    os.environ[env_var] = value
    
    settings = Settings()
    print(f"=== ENVIRONMENT: {settings.ENVIRONMENT} ===") 
    return settings
