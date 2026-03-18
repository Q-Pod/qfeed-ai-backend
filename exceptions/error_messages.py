# exceptions/error_messages.py
from enum import Enum


class ErrorMessage(str, Enum):
    """API 에러 메시지 (응답 body의 message 필드로 전송)"""
    # STT 관련
    AUDIO_NOT_FOUND = "audio_not_found"
    STT_TIMEOUT = "stt_timeout"
    AUDIO_UNPROCESSABLE = "audio_unprocessable" 
    STT_CONVERSION_FAILED = "stt_conversion_failed"
    STT_SERVICE_UNAVAILABLE = "stt_service_unavailable"

    #S3 관련
    S3_ACCESS_FORBIDDEN = "s3_access_forbidden"
    AUDIO_DOWNLOAD_FAILED = "audio_download_failed"
    AUDIO_DOWNLOAD_TIMEOUT = "audio_download_timeout"

    # Feedback 관련
    EMPTY_QUESTION = "empty_question"
    EMPTY_ANSWER = "empty_answer"
    ANSWER_TOO_SHORT = "answer_too_short"
    ANSWER_TOO_LONG = "answer_too_long"
    INVALID_ANSWER_FORMAT = "invalid_answer_format"
    BAD_CASE_CHECK_FAILED = "bad_case_check_failed"
    FEEDBACK_ALREADY_IN_PROGRESS = "feedback_already_in_progress"
    RUBRIC_EVALUATION_FAILED = "rubric_evaluation_failed"
    FEEDBACK_GENERATION_FAILED = "feedback_generation_failed"

    #질문 생성 관련 
    QUESTION_GENERATION_FAILED = "question_generation_failed"
    QUESTION_POOL_EMPTY = "question_pool_empty"
    ANALYSIS_SAVE_FAILED = "analysis_save_failed"

    # LLM 관련
    LLM_SERVICE_UNAVAILABLE = "llm_service_unavailable"
    LLM_RESPONSE_PARSE_FAILED = "llm_response_parse_failed"
    LLM_TIMEOUT = "llm_timeout"

    # TTS 관련
    TTS_TIMEOUT = "tts_timeout"
    TTS_CONVERSION_FAILED = "tts_conversion_failed"
    TTS_SERVICE_UNAVAILABLE = "tts_service_unavailable"
    TTS_VOICE_NOT_FOUND = "tts_voice_not_found"

    # 공통
    SERVER_CONNECTION_FAILED = "server_connection_failed"
    API_KEY_INVALID = "api_key_invalid"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    INTERNAL_SERVER_ERROR = "internal_server_error"
    SERVICE_TEMPORARILY_UNAVAILABLE = "service_temporarily_unavailable"


# HTTP status code 매핑
ERROR_STATUS_CODE: dict[ErrorMessage, int] = {
    # 400 Bad Request
    ErrorMessage.EMPTY_QUESTION: 400,
    ErrorMessage.EMPTY_ANSWER: 400,
    ErrorMessage.ANSWER_TOO_SHORT: 400,
    ErrorMessage.ANSWER_TOO_LONG: 400,
    ErrorMessage.INVALID_ANSWER_FORMAT: 400,

    # 401 Bad Request
    ErrorMessage.API_KEY_INVALID: 401,

    # 403 Forbidden
    ErrorMessage.S3_ACCESS_FORBIDDEN: 403,
    ErrorMessage.AUDIO_DOWNLOAD_FAILED: 403,

    # 404 Not Found
    ErrorMessage.AUDIO_NOT_FOUND: 404,
    ErrorMessage.TTS_VOICE_NOT_FOUND: 404,
    ErrorMessage.QUESTION_POOL_EMPTY: 404,

    # 408 Request Timeout
    ErrorMessage.AUDIO_DOWNLOAD_TIMEOUT: 408,
    ErrorMessage.STT_TIMEOUT: 408,
    ErrorMessage.LLM_TIMEOUT: 408,
    ErrorMessage.TTS_TIMEOUT: 408,

    # 409 Conflict
    ErrorMessage.FEEDBACK_ALREADY_IN_PROGRESS: 409,

    # 422 Unprocessable Entity
    ErrorMessage.AUDIO_UNPROCESSABLE: 422,

    # 429 Too Many Requests
    ErrorMessage.RATE_LIMIT_EXCEEDED: 429,

    # 500 Internal Server Error
    ErrorMessage.BAD_CASE_CHECK_FAILED : 500,
    ErrorMessage.SERVER_CONNECTION_FAILED: 500,
    ErrorMessage.STT_CONVERSION_FAILED: 500,
    ErrorMessage.TTS_CONVERSION_FAILED: 500,
    ErrorMessage.FEEDBACK_GENERATION_FAILED: 500,
    ErrorMessage.RUBRIC_EVALUATION_FAILED: 500,
    ErrorMessage.INTERNAL_SERVER_ERROR: 500,
    ErrorMessage.QUESTION_GENERATION_FAILED: 500,
    ErrorMessage.ANALYSIS_SAVE_FAILED: 500,
    

    # 502 Bad Gateway
    ErrorMessage.SERVER_CONNECTION_FAILED: 502,
    ErrorMessage.STT_SERVICE_UNAVAILABLE: 502,
    ErrorMessage.LLM_SERVICE_UNAVAILABLE: 502,
    ErrorMessage.LLM_RESPONSE_PARSE_FAILED: 502,
    ErrorMessage.TTS_SERVICE_UNAVAILABLE: 502,

    # 503 Service Unavailable
    ErrorMessage.SERVICE_TEMPORARILY_UNAVAILABLE: 503,
}
