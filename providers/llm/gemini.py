# providers/llm/gemini.py
#
# 수정 사항:
# 1. _call_api의 prompt 파라미터를 str | list로 확장하여 멀티모달에서도 재사용
# 2. generate_multimodal_structured가 _call_api를 직접 사용
# 3. 중복 API 호출 버그 수정

import json
from typing import Type, TypeVar, Any

from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError, TypeAdapter
from langfuse import observe

from core.config import get_settings
from core.logging import get_logger
from core.tracing import update_observation
from exceptions.exceptions import AppException
from exceptions.error_messages import ErrorMessage


T = TypeVar("T", bound=BaseModel)
settings = get_settings()
logger = get_logger(__name__)


def _get_schema_and_validator(response_model: Any) -> tuple[dict, TypeAdapter]:
    """response_model에서 JSON schema와 validator를 추출한다.

    BaseModel이든 Union이든 TypeAdapter로 통일 처리한다.
    TypeAdapter는 BaseModel에 대해서도 model_json_schema()와
    동일한 결과를 반환하므로 기존 동작과 완전히 호환된다.
    """
    adapter = TypeAdapter(response_model)
    schema = adapter.json_schema()
    return schema, adapter


class GeminiProvider:
    """Google Gemini Provider"""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        thinking_budget: int = 0,
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
        completion_tokens = (
            getattr(usage, "candidates_token_count", 0) if usage else 0
        )
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
        response_model: Any,
        *,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 5000,
    ) -> Any:
        """Structured Output 생성 - JSON 파싱하여 Pydantic 모델로 반환"""
        full_prompt = self._build_prompt(prompt, system_prompt)
        schema, adapter = _get_schema_and_validator(response_model)
        task_name = getattr(response_model, "__name__", str(response_model))

        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens + self.thinking_budget,
            response_mime_type="application/json",
            response_schema=schema,
            thinking_config=types.ThinkingConfig(
                thinking_budget=self.thinking_budget
            ),
        )

        response = await self._call_api(full_prompt, task_name, config)
        return self._parse_structured_response(response, adapter, task_name)

    @observe(name="gemini_generate_multimodal", as_type="generation")
    async def generate_multimodal_structured(
        self,
        contents: list,
        response_model: Any,
        *,
        temperature: float = 0.3,
        max_tokens: int = 5000,
    ) -> Any:
        """멀티모달 Structured Output 생성 - 텍스트 + 이미지 입력 지원

        Args:
            contents: Gemini contents 리스트
                      [types.Part.from_text("..."), types.Part.from_bytes(data, mime_type), ...]
            response_model: Pydantic 모델 또는 Union 타입
            temperature: 생성 온도
            max_tokens: 최대 출력 토큰

        Returns:
            파싱된 Pydantic 모델 인스턴스
        """
        schema, adapter = _get_schema_and_validator(response_model)
        task_name = getattr(response_model, "__name__", str(response_model))

        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens + self.thinking_budget,
            response_mime_type="application/json",
            response_schema=schema,
            thinking_config=types.ThinkingConfig(
                thinking_budget=self.thinking_budget
            ),
        )

        # _call_api에 contents(list)를 그대로 전달
        response = await self._call_api(contents, task_name, config)
        return self._parse_structured_response(response, adapter, task_name)

    # ============================================================
    # 내부 메서드
    # ============================================================

    async def _call_api(
        self,
        contents: str | list,
        task: str,
        config: types.GenerateContentConfig,
    ):
        """Gemini API 호출 - 공통 에러 처리

        Args:
            contents: 텍스트(str) 또는 멀티모달 Part 리스트(list)
            task: 태스크명 (로깅용)
            config: Gemini 생성 설정
        """

        logger.debug(f"Gemini API 호출 시작 | task={task} | model={self.model}")
        try:
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=contents,
                config=config,
            )
            logger.debug(f"Gemini response : {response}")
            logger.debug(f"Gemini API 완료 | task={task}")

            return response

        except TimeoutError as e:
            logger.error(f"Gemini API 타임아웃 | task={task}")
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

            logger.error(
                f"Gemini API 에러 | task={task} | {type(e).__name__}: {e}"
            )
            raise AppException(ErrorMessage.LLM_SERVICE_UNAVAILABLE) from e

    def _parse_structured_response(
        self,
        response,
        adapter: TypeAdapter,
        task_name: str,
    ) -> Any:
        """Gemini 응답을 JSON 파싱 + Pydantic 검증하여 반환

        generate_structured와 generate_multimodal_structured에서 공통으로 사용.
        """

        usage = getattr(response, "usage_metadata", None)
        prompt_tokens = getattr(usage, "prompt_token_count", 0) if usage else 0
        completion_tokens = (
            getattr(usage, "candidates_token_count", 0) if usage else 0
        )

        update_observation(
            model=self.model,
            usage_details={
                "input_tokens": prompt_tokens,
                "output_tokens": completion_tokens,
            },
        )

        try:
            parsed_data = json.loads(response.text)
            result = adapter.validate_python(parsed_data)
            logger.debug(f"JSON 파싱 성공 | model={task_name}")
            return result
        except json.JSONDecodeError as e:
            logger.error(f"JSON 파싱 실패 | model={task_name} | error={e}")
            raise AppException(ErrorMessage.LLM_RESPONSE_PARSE_FAILED) from e
        except ValidationError as e:
            logger.error(f"Pydantic 검증 실패 | model={task_name} | error={e}")
            raise AppException(ErrorMessage.LLM_RESPONSE_PARSE_FAILED) from e
        except Exception as e:
            logger.error(
                f"응답 처리 실패 | model={task_name} | {type(e).__name__}: {e}"
            )
            raise AppException(ErrorMessage.LLM_RESPONSE_PARSE_FAILED) from e

    def _build_prompt(
        self,
        prompt: str,
        system_prompt: str | None,
    ) -> str:
        """프롬프트 구성"""
        if system_prompt:
            return f"{system_prompt}\n\n{prompt}"
        return prompt