# core/tracing.py
from langsmith.run_helpers import get_current_run_tree


def record_llm_metrics(
    *,
    provider: str,
    model: str,
    task: str,
    prompt_tokens: int,
    completion_tokens: int,
    latency_ms: float,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> None:
    """LLM 호출 메트릭 기록"""
    run_tree = get_current_run_tree()
    if not run_tree:
        return

    total_tokens = prompt_tokens + completion_tokens
    tps = (completion_tokens / (latency_ms / 1000)) if latency_ms > 0 and completion_tokens > 0 else 0

    run_tree.extra["llm_output"] = {
        "token_usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        },
        "model_name": model,
    }

    run_tree.extra["metadata"] = {
        "provider": provider,
        "model": model,
        "task": task,
        "latency_ms": round(latency_ms, 2),
        "tokens_per_second": round(tps, 2),
        "temperature": temperature,
        "max_tokens": max_tokens,
    }


def record_stt_metrics(
    *,
    provider: str,
    model: str,
    latency_ms: float,
    audio_duration_sec: float | None = None,
    transcribed_text_length: int,
    language: str = "ko",
) -> None:
    """STT 호출 메트릭 기록"""
    run_tree = get_current_run_tree()
    if not run_tree:
        return

    metadata = {
        "provider": provider,
        "model": model,
        "language": language,
        "latency_ms": round(latency_ms, 2),
        "transcribed_length": transcribed_text_length,
    }

    if audio_duration_sec:
        metadata["audio_duration_sec"] = audio_duration_sec
        metadata["real_time_factor"] = round(latency_ms / 1000 / audio_duration_sec, 2)

    run_tree.extra["metadata"] = metadata

def record_tts_metrics(
    *,
    model: str,
    latency_ms: float,
    text_length: int,
    audio_size_bytes: int,
    voice_id: str,
    language: str = "ko",
) -> None:
    """TTS 호출 메트릭 기록"""
    run_tree = get_current_run_tree()
    if not run_tree:
        return

    # 문자당 처리 시간 (ms/char)
    ms_per_char = (latency_ms / text_length) if text_length > 0 else 0
    # 바이트당 처리 시간 추정
    bytes_per_second = (audio_size_bytes / (latency_ms / 1000)) if latency_ms > 0 else 0

    run_tree.extra["metadata"] = {
        "model": model,
        "voice_id": voice_id,
        "language": language,
        "latency_ms": round(latency_ms, 2),
        "text_length": text_length,
        "audio_size_bytes": audio_size_bytes,
        "ms_per_char": round(ms_per_char, 2),
        "bytes_per_second": round(bytes_per_second, 2),
    }


def record_embedding_metrics(
    *,
    provider: str,
    model: str,
    latency_ms: float,
    input_count: int,
    similarity_score: float | None = None,
) -> None:
    """임베딩 호출 메트릭 기록"""
    run_tree = get_current_run_tree()
    if not run_tree:
        return

    run_tree.extra["metadata"] = {
        "provider": provider,
        "model": model,
        "latency_ms": round(latency_ms, 2),
        "input_count": input_count,
        "similarity_score": round(similarity_score, 4) if similarity_score else None,
    }


def record_tool_metrics(
    *,
    tool_name: str,
    latency_ms: float,
    success: bool = True,
    **extra_metadata,
) -> None:
    """일반 도구 메트릭 기록"""
    run_tree = get_current_run_tree()
    if not run_tree:
        return

    run_tree.extra["metadata"] = {
        "tool": tool_name,
        "latency_ms": round(latency_ms, 2),
        "success": success,
        **extra_metadata,
    }