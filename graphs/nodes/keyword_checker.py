import re
from sentence_transformers.util import cos_sim

from graphs.feedback.state import FeedbackGraphState
from schemas.feedback import KeywordCheckResult
from providers.embedding.sentence_transformer import get_embedding_provider
from core.logging import get_logger
from core.tracing import update_observation
from langfuse import observe


logger = get_logger(__name__)

def _clean_stt_text(text: str) -> str:
    """STT 결과에서 불필요한 추임새나 중복 공백 제거"""
    fillers = ["음", "어", "그", "저", "아"]
    for f in fillers:
        text = re.sub(rf"(^|\s){f}+(\.\.|…|\s)", " ", text)
    
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _get_sliding_windows(text: str, window_size: int = 30, stride: int = 15) -> list[str]:
    """
    텍스트를 슬라이딩 윈도우로 분할
    
    Args:
        text: 분할할 텍스트
        window_size: 윈도우 크기 (글자 수)
        stride: 이동 간격
    
    Returns:
        분할된 텍스트 조각 리스트
    """
    if len(text) <= window_size:
        return [text]
    
    windows = []
    for i in range(0, len(text), stride):
        chunk = text[i:i + window_size]
        if len(chunk) < 10:
            continue
        windows.append(chunk)
    
    return windows

@observe(name="keyword_checker", as_type="tool")
async def keyword_checker(state: FeedbackGraphState, similarity_threshold: float = 0.5) -> dict:
    """키워드 커버리지 체크 노드 (슬라이딩 윈도우 방식)"""
    logger.debug(f"keyword checker start | interview_type={state['interview_type']}")

    # 실전모드의 경우 필수키워드 체크 안함
    if state["interview_type"] == "REAL_INTERVIEW":
        return {
            "keyword_result": KeywordCheckResult(
                covered_keywords=[],
                missing_keywords=[],
                coverage_ratio=1.0,
            ),
            "current_step": "keyword_checker",
        }
    
    # 키워드 없으면 스킵
    keywords = state.get("keywords") or []
    if not keywords:
        logger.debug("No keywords - skip")
        return {
            "keyword_result": KeywordCheckResult(
                covered_keywords=[],
                missing_keywords=[],
                coverage_ratio=1.0,
            ),
            "current_step": "keyword_checker",
        }
    
    model = get_embedding_provider()
    
    # 연습모드 답변 텍스트 전처리
    answer = state["interview_history"][0].answer_text
    cleaned_answer = _clean_stt_text(answer)
    
    # 슬라이딩 윈도우로 텍스트 분할
    answer_chunks = _get_sliding_windows(cleaned_answer, window_size=20, stride=10)
    
    # 임베딩 생성
    chunk_embeddings = model.encode(answer_chunks)
    keyword_embeddings = model.encode(keywords)
    
    covered = []
    missing = []
    
    # Max Score Strategy: 각 키워드에 대해 가장 높은 유사도를 가진 청크와 비교
    for keyword, kw_emb in zip(state["keywords"], keyword_embeddings):
        similarities = cos_sim(kw_emb, chunk_embeddings)[0]
        max_score = similarities.max().item()
        
        if max_score >= similarity_threshold:
            covered.append(keyword)
        else:
            missing.append(keyword)
    
    coverage = len(covered) / len(state["keywords"])

    update_observation(
        output={"matched_keywords": covered, "missing_keywords": missing}
    )
    logger.info(f"keyword check success | covered={len(covered)}/{len(keywords)}, coverage={coverage:.2%}")
    
    return {
        "keyword_result": KeywordCheckResult(
            covered_keywords=covered,
            missing_keywords=missing,
            coverage_ratio=coverage,
        ),
        "current_step": "keyword_checker",
    }