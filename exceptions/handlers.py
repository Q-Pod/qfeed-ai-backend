# exceptions/handlers.py
from fastapi import Request
from fastapi.responses import JSONResponse

from exceptions.exceptions import AppException
from core.logging import get_logger

logger = get_logger(__name__)

async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    # 에러 레벨 결정
    if exc.status_code >= 500:
        logger.error(f"서버 에러 | status={exc.status_code} | {exc.message}")
    else:
        logger.warning(f"클라이언트 에러 | status={exc.status_code} | {exc.message}")

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "message": exc.message,
            "data": None
        }
    )

async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """예상치 못한 에러 - 동일한 포맷 유지"""

    logger.exception(f"처리되지 않은 예외 | {type(exc).__name__}: {exc}")
    
    return JSONResponse(
        status_code=500,
        content={
            "message": "exc.message",
            "data": None
        }
    )
