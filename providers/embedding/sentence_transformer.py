import time
from functools import lru_cache
from sentence_transformers import SentenceTransformer
from langsmith import traceable

from exceptions.exceptions import AppException
from exceptions.error_messages import ErrorMessage
from core.logging import get_logger
from core.tracing import record_embedding_metrics

logger = get_logger(__name__)

class SentenceTransformerProvider:
    """CPU SentenceTransformer 임베딩 Provider"""
    def __init__(self, model_name: str = "jhgan/ko-sroberta-multitask"):
        try:
            logger.info(f"SentenceTransformer 모델 로딩 | model={model_name}")
            self._model = SentenceTransformer(model_name)
            self.model_name = model_name
            logger.info(f"SentenceTransformer 모델 로딩 완료 | model={model_name}")
        except Exception as e:
            logger.error(f"SentenceTransformer 모델 로딩 실패 | model={model_name} | {type(e).__name__}: {e}")
            raise AppException(ErrorMessage.SERVICE_TEMPORARILY_UNAVAILABLE) from e
    
    @traceable(run_type="embedding", name="sentence_transformer_encode")
    def encode(self, texts: list[str]):
        """텍스트 임베딩 생성 """
        start_time = time.perf_counter()

        try:
            logger.debug(f"임베딩 생성 | count={len(texts)}")
            embeddings = self._model.encode(texts)

            latency_ms = (time.perf_counter() - start_time) * 1000
            dim = embeddings.shape[-1] if hasattr(embeddings, "shape") else 0

            logger.debug(f"임베딩 생성 완료 | count={len(texts)}, dim={dim}")

            # 메트릭 기록
            record_embedding_metrics(
                provider="sentence_transformer",
                model=self.model_name,
                latency_ms=latency_ms,
                input_count=len(texts),
            )

            return embeddings
        except Exception as e:
            logger.error(f"임베딩 생성 실패 | count={len(texts)} | {type(e).__name__}: {e}")
            record_embedding_metrics(
                provider="sentence_transformer",
                model=self.model_name,
                latency_ms=latency_ms,
                input_count=len(texts),
            )
            raise AppException(ErrorMessage.INTERNAL_SERVER_ERROR) from e

@lru_cache(maxsize=1)
def get_embedding_provider() -> SentenceTransformerProvider:
    return SentenceTransformerProvider()