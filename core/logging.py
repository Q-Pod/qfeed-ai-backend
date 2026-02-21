# core/logging.py
import logging
import sys
import uuid
import time
import asyncio
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from contextvars import ContextVar
from functools import wraps
from typing import Callable, Any, Optional
from dataclasses import dataclass

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# ============================================
# Context Variables (요청 추적용)
# ============================================

@dataclass
class RequestContext:
    """요청 컨텍스트 정보"""
    request_id: str = "-"
    method: str = "-"
    path: str = "-"
    user_id: Optional[str] = None

# Context Variable
request_context_var: ContextVar[RequestContext] = ContextVar(
    "request_context", 
    default=RequestContext()
)

# ============================================
# Logging Filter & Formatter
# ============================================

class RequestContextFilter(logging.Filter):
    """로그 레코드에 요청 컨텍스트 추가"""
    def filter(self, record: logging.LogRecord) -> bool:
        ctx = request_context_var.get()
        record.request_id = ctx.request_id
        record.method = ctx.method
        record.path = ctx.path
        record.user_id = ctx.user_id if ctx.user_id else "-"
        return True


class StandardLogFormatter(logging.Formatter):
    """
    표준화된 로그 포맷터
    
    출력 형식:
    [2026-02-03 12:41:27.123] [INFO] [ModuleName] [requestId] POST /api/xxx - userId: 17
    """
    
    def format(self, record: logging.LogRecord) -> str:
        # 밀리세컨드 포함 timestamp
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(record.created))
        timestamp += f".{int(record.msecs):03d}"
        
        # 기본 포맷 구성
        base = f"[{timestamp}] [{record.levelname}] [{record.name}] [{record.request_id}]"
        
        # HTTP 요청 정보가 있으면 추가
        if hasattr(record, 'method') and record.method != "-":
            base += f" {record.method} {record.path}"
        
        # userId가 있으면 추가
        if hasattr(record, 'user_id') and record.user_id != "-":
            base += f" - userId: {record.user_id}"
        
        # 메시지 추가
        if record.getMessage():
            # HTTP 정보가 있으면 구분자 추가
            if hasattr(record, 'method') and record.method != "-":
                base += f" | {record.getMessage()}"
            else:
                base += f" {record.getMessage()}"
        
        return base


# ============================================
# Middleware
# ============================================

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    요청별 컨텍스트 설정 및 HTTP 요청/응답 로깅 미들웨어
    
    - requestId 설정 (클라이언트 제공 or 자동 생성)
    - 요청 시작/완료 로깅
    - userId 추출 (요청 body에서)
    """
    
    async def dispatch(self, request: Request, call_next):
        # requestId 설정
        request_id = request.headers.get("X-Request-ID") or generate_request_id()
        
        # 컨텍스트 초기화
        ctx = RequestContext(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )
        set_request_context(ctx)
        
        logger = get_logger("http")
        
        # 요청 시작 로깅
        logger.info("요청 시작")
        
        start_time = time.perf_counter()

        try:
            response = await call_next(request)
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            
            # 요청 완료 로깅 (status 포함)
            logger.info(f"요청 완료 | status={response.status_code} | duration={elapsed_ms:.2f}ms")
            
            # 응답 헤더에 requestId 추가
            response.headers["X-Request-ID"] = request_id
            
            return response
            
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"요청 실패 | duration={elapsed_ms:.2f}ms | {type(e).__name__}: {e}")
            raise

def setup_logging(environment: str = "local", log_dir: str = "logs") -> None:
    """환경별 로깅 설정"""
    log_level = logging.DEBUG if environment == "local" else logging.INFO
    
    # 커스텀 포맷터 사용
    formatter = StandardLogFormatter()
    
    # 루트 로거 설정
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # 기존 핸들러 제거 (중복 방지)
    root_logger.handlers.clear()
    
    # 콘솔 핸들러
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)
    console_handler.addFilter(RequestContextFilter())
    root_logger.addHandler(console_handler)
    
    # 프로덕션: 파일 핸들러 추가
    if environment == "production":
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        
        # app.log (INFO 이상)
        app_handler = TimedRotatingFileHandler(
            log_path / "app.log",
            when="midnight",
            backupCount=30,
            encoding="utf-8"
        )
        app_handler.setFormatter(formatter)
        app_handler.setLevel(logging.INFO)
        app_handler.addFilter(RequestContextFilter())
        root_logger.addHandler(app_handler)
        
        # error.log (ERROR 이상)
        error_handler = TimedRotatingFileHandler(
            log_path / "error.log",
            when="midnight",
            backupCount=30,
            encoding="utf-8"
        )
        error_handler.setFormatter(formatter)
        error_handler.setLevel(logging.ERROR)
        error_handler.addFilter(RequestContextFilter())
        root_logger.addHandler(error_handler)
    
    # 메트릭 로거 (별도) - APM 연동용
    _setup_metrics_logger(environment, log_dir, formatter)
    
    logging.info(f"로깅 설정 완료 | env={environment}, level={logging.getLevelName(log_level)}")

def _setup_metrics_logger(environment: str, log_dir: str, formatter: logging.Formatter) -> None:
    """메트릭 로거 설정 (APM/모니터링용)"""
    metrics_logger = logging.getLogger("metrics")
    metrics_logger.setLevel(logging.INFO)
    metrics_logger.propagate = False
    
    metrics_console = logging.StreamHandler(sys.stdout)
    metrics_console.setFormatter(formatter)
    metrics_console.addFilter(RequestContextFilter())
    metrics_logger.addHandler(metrics_console)
    
    if environment == "production":
        log_path = Path(log_dir)
        metrics_handler = TimedRotatingFileHandler(
            log_path / "metrics.log",
            when="midnight",
            backupCount=30,
            encoding="utf-8"
        )
        metrics_handler.setFormatter(formatter)
        metrics_handler.addFilter(RequestContextFilter())
        metrics_logger.addHandler(metrics_handler)

# helper function

def get_logger(name: str) -> logging.Logger:
    """로거 인스턴스 반환"""
    return logging.getLogger(name)


def get_metrics_logger() -> logging.Logger:
    """메트릭 로거 반환 (APM 연동용)"""
    return logging.getLogger("metrics")


def generate_request_id() -> str:
    """새 requestId 생성 (8자리)"""
    return uuid.uuid4().hex[:8]


def set_request_context(ctx: RequestContext) -> None:
    """현재 컨텍스트 설정"""
    request_context_var.set(ctx)


def get_request_context() -> RequestContext:
    """현재 컨텍스트 반환"""
    return request_context_var.get()


def get_request_id() -> str:
    """현재 requestId 반환"""
    return request_context_var.get().request_id


def update_user_id(user_id: str) -> None:
    """컨텍스트에 userId 추가 (요청 body 파싱 후 호출)"""
    ctx = request_context_var.get()
    new_ctx = RequestContext(
        request_id=ctx.request_id,
        method=ctx.method,
        path=ctx.path,
        user_id=user_id,
    )
    request_context_var.set(new_ctx)


def log_execution_time(logger: logging.Logger):
    """
    함수 실행 시간 로깅 데코레이터
    
    Note: duration 측정은 APM으로 이관 예정이지만,
          디버그/개발 단계에서는 유용하므로 유지
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            start = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                elapsed_ms = (time.perf_counter() - start) * 1000
                logger.debug(f"{func.__name__} 완료 | duration={elapsed_ms:.2f}ms")
                return result
            except Exception as e:
                elapsed_ms = (time.perf_counter() - start) * 1000
                logger.error(f"{func.__name__} 실패 | duration={elapsed_ms:.2f}ms | {type(e).__name__}: {e}")
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                elapsed_ms = (time.perf_counter() - start) * 1000
                logger.debug(f"{func.__name__} 완료 | duration={elapsed_ms:.2f}ms")
                return result
            except Exception as e:
                elapsed_ms = (time.perf_counter() - start) * 1000
                logger.error(f"{func.__name__} 실패 | duration={elapsed_ms:.2f}ms | {type(e).__name__}: {e}")
                raise
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator