# routers/follow_up.py
from fastapi import APIRouter

from schemas.question import QuestionGenerateRequest, QuestionGenerateResponse
from services.question_generate_service import QuestionGenerateService
from core.logging import get_logger, log_execution_time, update_user_id

router = APIRouter()
logger = get_logger(__name__)

@router.post("/interview/follow-up/questions", response_model=QuestionGenerateResponse)
@log_execution_time(logger)
async def request_feedback(request: QuestionGenerateRequest,):
    """
    면접 질문 생성 및 꼬리 질문 생성
    """
    update_user_id(str(request.user_id))
    
    logger.info(
        f"question generate request | sessionId={request.session_id}"
    )
    service = QuestionGenerateService()
    response = await service.generate_question(request)
    
    logger.info(f"question generate completed | success={response.message}")
    
    return response

