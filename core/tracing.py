# core/tracing.py
from langfuse import get_client
from typing import Any

#
_langfuse = None  # Langfuse 클라이언트 싱글톤 인스턴스

def _get_client():
    """Langfuse 클라이언트 lazy singleton"""
    global _langfuse
    if _langfuse is None:
        _langfuse = get_client()
    return _langfuse


def update_trace(
    user_id: str | None = None,
    session_id: str | None = None,
    metadata: dict | None = None,
    tags: list[str] | None = None,
) -> None:
    """현재 trace 메타데이터 업데이트"""
    _get_client().update_current_trace(
        user_id=user_id,
        session_id=session_id,
        metadata=metadata,
        tags=tags,
    )


def update_observation(
    input: Any = None,
    output: Any = None,
    metadata: dict | None = None,
    model: str | None = None,
    usage_details: dict | None = None,
) -> None:
    """현재 observation(span/generation) 업데이트"""
    kwargs = {}
    if input is not None:
        kwargs["input"] = input
    if output is not None:
        kwargs["output"] = output
    if metadata is not None:
        kwargs["metadata"] = metadata
    if model is not None:
        kwargs["model"] = model
    if usage_details is not None:
        kwargs["usage_details"] = usage_details
    
    _get_client().update_current_generation(**kwargs)  


def update_span(
    input: Any = None,
    output: Any = None,
    metadata: dict | None = None,
) -> None:
    """현재 span observation 업데이트 (STT/TTS 등 비-LLM 파이프라인용)"""
    kwargs = {}
    if input is not None:
        kwargs["input"] = input
    if output is not None:
        kwargs["output"] = output
    if metadata is not None:
        kwargs["metadata"] = metadata

    _get_client().update_current_span(**kwargs)


def add_score(
    name: str,
    value: float | int,
    comment: str | None = None,
) -> None:
    """현재 trace에 점수 추가"""
    client = _get_client()
    trace_id = client.get_current_trace_id()
    if trace_id:
        client.score(
            trace_id=trace_id,
            name=name,
            value=value,
            comment=comment,
        )


def flush() -> None:
    """남은 이벤트 전송 (shutdown 시 호출)"""
    _get_client().flush()