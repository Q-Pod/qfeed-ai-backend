# providers/llm/gemini.py

import json
from typing import Type, TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError
from langfuse import observe

from core.config import get_settings
from core.logging import get_logger
from core.tracing import update_observation
from exceptions.exceptions import AppException
from exceptions.error_messages import ErrorMessage


T = TypeVar("T", bound=BaseModel)
settings = get_settings()
logger = get_logger(__name__)


class GeminiProvider:
    """Google Gemini Provider"""
    

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        thinking_budget: int = 0
    ):
        self.client = genai.Client(api_key=api_key or settings.GEMINI_API_KEY)
        self.model = model or settings.GEMINI_MODEL_ID
        self.thinking_budget = thinking_budget

    @property
    def provider_name(self) -> str:
        return "gemini"
    
    @observe(name="gemini_generate", as_type="generation")
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
        full_prompt = self._build_prompt(prompt, system_prompt)
        task_name = response_model.__name__

        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        response = await self._call_api(full_prompt, task_name, config)

        usage = getattr(response, "usage_metadata", None)
        prompt_tokens = getattr(usage, "prompt_token_count", 0) if usage else 0
        completion_tokens = getattr(usage, "candidates_token_count", 0) if usage else 0
        update_observation(
            model=self.model,
            usage_details={
                "input_tokens": prompt_tokens,
                "output_tokens": completion_tokens,
            },
        )
    
    @observe(name="gemini_generate_structured", as_type="generation")
    async def generate_structured(
        self,
        prompt: str,
        response_model: Type[T],
        *,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4000,
    ) -> T:
        """Structured Output 생성 - JSON 파싱하여 Pydantic 모델로 반환"""
        full_prompt = self._build_prompt(prompt, system_prompt)
        schema = response_model.model_json_schema()
        task_name = response_model.__name__

        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            response_mime_type="application/json",
            response_schema=schema,
            thinking_config=types.ThinkingConfig(
                thinking_budget=self.thinking_budget  # 0이면 thinking 비활성화
            ),
        )

        response = await self._call_api(full_prompt, task_name, config)

        usage = getattr(response, "usage_metadata", None)
        prompt_tokens = getattr(usage, "prompt_token_count", 0) if usage else 0
        completion_tokens = getattr(usage, "candidates_token_count", 0) if usage else 0
        update_observation(
            model=self.model,
            usage_details={
                "input_tokens": prompt_tokens,
                "output_tokens": completion_tokens,
            },
        )

        try:
            parsed_data = json.loads(response.text)
            result = response_model.model_validate(parsed_data)
            logger.debug(f"JSON 파싱 성공 | model={task_name}")
            return result
        except json.JSONDecodeError as e:
            logger.error(f"JSON 파싱 실패 | model={task_name} | error={e}")
            raise AppException(ErrorMessage.LLM_RESPONSE_PARSE_FAILED) from e
        except ValidationError as e:
            logger.error(f"Pydantic 검증 실패 | model={task_name} | error={e}")
            raise AppException(ErrorMessage.LLM_RESPONSE_PARSE_FAILED) from e
        except Exception as e:
            logger.error(f"응답 처리 실패 | model={task_name} | {type(e).__name__}: {e}")
            raise AppException(ErrorMessage.LLM_RESPONSE_PARSE_FAILED) from e
        

    async def _call_api(
        self,
        prompt: str,
        task: str,
        config: types.GenerateContentConfig,
    ):
        """Gemini API 호출 - 공통 에러 처리"""
        
        logger.debug(f"Gemini API 호출 시작 | task={task} | model={self.model}")
        try:
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config,
            )
            logger.debug(f"Gemini response : {response}")
            logger.debug(f"Gemini API 완료 | task={task}")
            
            return response
        
        except TimeoutError as e:
            logger.error(f"Gemini API 타임아웃 | task={task} ")
            raise AppException(ErrorMessage.LLM_TIMEOUT) from e
        except ConnectionError as e:
            logger.error(f"Gemini API 연결 실패 | task={task}")
            raise AppException(ErrorMessage.LLM_SERVICE_UNAVAILABLE) from e
        except Exception as e:
            error_message = str(e).lower()
            
            if "timeout" in error_message:
                logger.error(f"Gemini API 타임아웃 | task={task}")
                raise AppException(ErrorMessage.LLM_TIMEOUT) from e
            if "connection" in error_message or "unavailable" in error_message:
                logger.error(f"Gemini API 연결 실패 | task={task}")
                raise AppException(ErrorMessage.LLM_SERVICE_UNAVAILABLE) from e
            
            logger.error(f"Gemini API 에러 | task={task} | {type(e).__name__}: {e}")
            raise AppException(ErrorMessage.LLM_SERVICE_UNAVAILABLE) from e

    def _build_prompt(
        self,
        prompt: str,
        system_prompt: str | None,
    ) -> str:
        """프롬프트 구성"""
        if system_prompt:
            return f"{system_prompt}\n\n{prompt}"
        return prompt