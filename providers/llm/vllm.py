# providers/llm/vllm.py

import json
import time
from typing import Type, TypeVar

import httpx
from pydantic import BaseModel, ValidationError
from langsmith import traceable

from core.config import get_settings
from core.logging import get_logger, get_metrics_logger
from core.tracing import record_llm_metrics, record_tool_metrics
from exceptions.exceptions import AppException
from exceptions.error_messages import ErrorMessage


T = TypeVar("T", bound=BaseModel)
settings = get_settings()
logger = get_logger(__name__)
metrics_logger = get_metrics_logger()


class VLLMProvider:
    """vLLM OpenAI 호환 API Provider"""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 120.0,
    ):
        self.base_url = base_url or settings.GPU_LLM_URL
        self.model = model or settings.LLM_MODEL_ID  
        self.timeout = timeout

    @property
    def provider_name(self) -> str:
        return "vllm"

    @traceable(run_type="llm", name="vllm_generate")
    async def generate(
        self,
        prompt: str,
        response_model: Type[T],
        *,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """일반 텍스트 생성"""
        messages = self._build_messages(prompt, system_prompt)
        task_name = response_model.__name__

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        result, latency_ms = await self._call_api(payload, task_name)

        # 메트릭 기록
        usage = result.get("usage", {})
        record_llm_metrics(
            provider="vllm",
            model=self.model,
            task=task_name,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            latency_ms=latency_ms,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return result["choices"][0]["message"]["content"]

    @traceable(run_type="llm", name="vllm_generate_structured")
    async def generate_structured(
        self,
        prompt: str,
        response_model: Type[T],
        *,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4000,
    ) -> T:
        """Structured Output 생성 - vLLM guided_json 사용"""
        messages = self._build_messages(prompt, system_prompt)
        schema = response_model.model_json_schema()
        task_name = response_model.__name__

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "structured_outputs": {
                "json": schema
            }
        }

        result, latency_ms = await self._call_api(payload, task_name)
        content = result["choices"][0]["message"]["content"]

        # 메트릭 기록
        usage = result.get("usage", {})
        record_llm_metrics(
            provider="vllm",
            model=self.model,
            task=task_name,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            latency_ms=latency_ms,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        try:
            parsed_data = json.loads(content)
            result = response_model.model_validate(parsed_data)
            logger.debug(f"JSON 파싱 성공 | model={task_name}")
            return result
        except json.JSONDecodeError as e:
            record_tool_metrics(
                tool_name="json_parse",
                latency_ms=0,
                success=False,
                task=task_name,
                error=str(e)[:200],
            )
            logger.error(f"JSON 파싱 실패 | model={task_name} | error={e} | content={content[:200]}")
            raise AppException(ErrorMessage.LLM_RESPONSE_PARSE_FAILED) from e
        except ValidationError as e:
            record_tool_metrics(
                tool_name="json_parse",
                latency_ms=0,
                success=False,
                task=task_name,
                error=str(e)[:200],
            )
            logger.error(f"Pydantic 검증 실패 | model={task_name} | error={e}")
            raise AppException(ErrorMessage.LLM_RESPONSE_PARSE_FAILED) from e
        except Exception as e:
            record_tool_metrics(
                tool_name="json_parse",
                latency_ms=0,
                success=False,
                task=task_name,
                error=str(e)[:200],
            )
            logger.error(f"응답 처리 실패 | model={task_name} | {type(e).__name__}: {e}")
            raise AppException(ErrorMessage.LLM_RESPONSE_PARSE_FAILED) from e
        

    async def _call_api(
        self,
        payload: dict,
        task: str,
    ) -> dict:
        """vLLM API 호출 - 공통 에러 처리"""
        start_time = time.perf_counter()
        url = f"{self.base_url}/v1/chat/completions"

        logger.debug(f"vLLM API 호출 시작 | task={task} | model={self.model}")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                result = response.json()
                logger.debug(f"vLLM raw response | task={task} | response={result}")

            elapsed_ms = (time.perf_counter() - start_time) * 1000

            logger.debug(f"vLLM API 완료 | task={task} | {elapsed_ms:.2f}ms")

            return result, elapsed_ms

        except httpx.TimeoutException as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"vLLM API 타임아웃 | task={task} | {elapsed_ms:.2f}ms")
            raise AppException(ErrorMessage.LLM_TIMEOUT) from e

        except httpx.ConnectError as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"vLLM 서버 연결 실패 | task={task} | url={url} | {elapsed_ms:.2f}ms")
            raise AppException(ErrorMessage.LLM_SERVICE_UNAVAILABLE) from e

        except httpx.HTTPStatusError as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            status_code = e.response.status_code
            
            # 에러 응답 파싱 시도
            try:
                error_detail = e.response.json()
            except Exception:
                error_detail = e.response.text[:200]

            logger.error(
                f"vLLM API 에러 | task={task} | status={status_code} | "
                f"{elapsed_ms:.2f}ms | detail={error_detail}"
            )

            if status_code == 503:
                raise AppException(ErrorMessage.LLM_SERVICE_UNAVAILABLE) from e
            if status_code == 429:
                raise AppException(ErrorMessage.RATE_LIMIT_EXCEEDED) from e

            raise AppException(ErrorMessage.LLM_SERVICE_UNAVAILABLE) from e

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"vLLM API 예외 | task={task} | {elapsed_ms:.2f}ms | {type(e).__name__}: {e}")
            raise AppException(ErrorMessage.LLM_SERVICE_UNAVAILABLE) from e

    def _build_messages(
        self,
        prompt: str,
        system_prompt: str | None,
    ) -> list[dict]:
        """OpenAI 형식의 messages 배열 구성"""
        messages = []
        
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt,
            })
        
        messages.append({
            "role": "user",
            "content": prompt,
        })
        
        return messages

    async def health_check(self) -> bool:
        """vLLM 서버 헬스체크"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except Exception as e:
            logger.warning(f"vLLM 헬스체크 실패 | {type(e).__name__}: {e}")
            return False