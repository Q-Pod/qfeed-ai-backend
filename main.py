from contextlib import asynccontextmanager
from fastapi import FastAPI
from routers import stt,feedback,question, tts, portfolio


from exceptions.handlers import app_exception_handler, global_exception_handler
from exceptions.exceptions import AppException
from core.config import get_settings
from core.logging import setup_logging, RequestLoggingMiddleware, get_logger
from core.tracing import flush
from providers.embedding.sentence_transformer import get_embedding_provider
from services.bad_case_checker import _get_kiwi

from prometheus_fastapi_instrumentator import Instrumentator

settings = get_settings()
setup_logging(environment=settings.ENVIRONMENT, log_dir=settings.log_directory)
logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    
    try:
        embedding_provider = get_embedding_provider()
        embedding_provider.encode(["warmup"])
        logger.info("embedding model loading success")
    except Exception as e:
        logger.error(f"embedding warmup failed: {e}")
    
    try:
        kiwi = _get_kiwi()
        kiwi.tokenize("warm up test")
        logger.info("kiwi loading success")
    except Exception as e:
        logger.error(f"kiwi warmup failed: {e}")
    
    # 웜업 완료 후 LangSmith 활성화
    
    logger.info("finish model loading")
    yield
    flush()
    logger.info("end of app")

app = FastAPI(lifespan=lifespan)
Instrumentator().instrument(app).expose(app)  # /metrics 엔드포인트 자동 생성
app.add_middleware(RequestLoggingMiddleware)

app.include_router(stt.router, prefix="/ai", tags=["stt"])
app.include_router(feedback.router, prefix="/ai", tags=["feedback"])
app.include_router(question.router, prefix="/ai", tags=["question"])
app.include_router(tts.router, prefix="/ai", tags=["tts"])
app.include_router(portfolio.router, prefix="/ai", tags=["portfolio"])

app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)

@app.get("/ai")
async def root():
    return {"message": "FastAPI is running"}