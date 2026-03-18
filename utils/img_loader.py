# utils/img_loader.py

"""이미지 URL에서 다운로드하는 유틸리티

포트폴리오 아키텍처 이미지를 Gemini 멀티모달 입력으로 사용하기 위해
URL에서 이미지를 다운로드한다. base64 인코딩 없이 바이트 그대로 반환하여
Gemini의 Part.from_bytes()에 직접 전달할 수 있다.
"""

import httpx

from core.logging import get_logger

logger = get_logger(__name__)

# 지원하는 이미지 MIME 타입
SUPPORTED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
}


async def download_image(
    url: str,
    timeout: float = 30.0,
) -> tuple[bytes, str] | None:
    """URL에서 이미지를 다운로드하여 (bytes, mime_type) 반환

    Args:
        url: 이미지 URL
        timeout: 다운로드 타임아웃 (초)

    Returns:
        (image_bytes, mime_type) 또는 실패 시 None
    """

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url)
            response.raise_for_status()

        # MIME 타입 결정: Content-Type 헤더 우선, 없으면 URL 확장자로 추론
        content_type = response.headers.get("content-type", "").split(";")[0].strip()

        if content_type in SUPPORTED_MIME_TYPES:
            mime_type = content_type
        else:
            mime_type = _infer_mime_from_url(url)
            if mime_type is None:
                logger.warning(
                    f"Unsupported image type | url={url} | content_type={content_type}"
                )
                return None

        logger.debug(
            f"Image downloaded | url={url} | "
            f"mime_type={mime_type} | size={len(response.content)} bytes"
        )

        return response.content, mime_type

    except httpx.TimeoutException:
        logger.warning(f"Image download timeout | url={url}")
        return None
    except httpx.HTTPStatusError as e:
        logger.warning(f"Image download HTTP error | url={url} | status={e.response.status_code}")
        return None
    except Exception as e:
        logger.warning(f"Image download failed | url={url} | {type(e).__name__}: {e}")
        return None


def _infer_mime_from_url(url: str) -> str | None:
    """URL 확장자에서 MIME 타입 추론"""
    url_lower = url.lower().split("?")[0]  # 쿼리 파라미터 제거

    if url_lower.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    elif url_lower.endswith(".png"):
        return "image/png"

    return None