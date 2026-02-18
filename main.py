from contextlib import asynccontextmanager
from fastapi import FastAPI
from routers import stt,feedback,question, tts

from exceptions.handlers import app_exception_handler, global_exception_handler
from exceptions.exceptions import AppException
from core.config import get_settings
from core.logging import setup_logging, RequestLoggingMiddleware, get_logger
from providers.embedding.sentence_transformer import get_embedding_provider
from services.bad_case_checker import _get_kiwi
# from services.bad_case_checker import get_bad_case_checker

settings = get_settings()
settings.configure_langsmith() 
setup_logging(environment=settings.ENVIRONMENT, log_dir=settings.log_directory)

logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 시 실행되는 lifespan 컨텍스트"""

    settings.configure_langsmith(enabled=False)
    logger.info("embedding model loading start")

    # 1. Embedding 모델 로딩 (가장 오래 걸림)
    try:
        embedding_provider = get_embedding_provider()
        embedding_provider.encode(["warmup"])
        logger.info("embedding model loading success")
    except Exception as e:
        logger.error(f"embedding model loading failed: {e}")
    
    # 2. Kiwi 형태소 분석기 로딩
    try:
        
        kiwi = _get_kiwi()
        kiwi.tokenize("warm up test")
        logger.info("kiwi loading success")
    except Exception as e:
        logger.error(f"kiwi loading failed: {e}")
    
    # # 3. BadCaseChecker 초기화 (위 두 모델 사용)
    # try:
        
    #     checker = get_bad_case_checker()
    #     logger.info("✅ BadCaseChecker 초기화 완료")
    # except Exception as e:
    #     logger.error(f"❌ BadCaseChecker 초기화 실패: {e}")
    settings.configure_langsmith(enabled=True)
    logger.info("finish model loading")
    
    yield  
    logger.info("end of app")

app = FastAPI(lifespan=lifespan)
app.add_middleware(RequestLoggingMiddleware)

app.include_router(stt.router, prefix="/ai", tags=["stt"])
app.include_router(feedback.router, prefix="/ai", tags=["feedback"])
app.include_router(question.router, prefix="/ai", tags=["question"])
app.include_router(tts.router, prefix="/ai", tags=["tts"])

app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)

@app.get("/ai")
async def root():
    return {"message": "FastAPI is running"}