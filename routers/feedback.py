# routers/feedback.py
from fastapi import APIRouter

from schemas.feedback import FeedbackRequest, FeedbackResponse
from services.feedback_service import FeedbackService
from core.logging import get_logger, log_execution_time, update_user_id

router = APIRouter()
logger = get_logger(__name__)

@router.post("/interview/feedback/request", response_model=FeedbackResponse)
@log_execution_time(logger)
async def request_feedback(request: FeedbackRequest,):
    """
    면접 답변에 대한 피드백 생성
    """
    update_user_id(str(request.user_id))
    
    logger.info(
        f"feedback generate request | questionId={request.question_id}, "
        f"sessionId={request.session_id}, type={request.interview_type.value}"
    )
    service = FeedbackService()
    response = await service.generate_feedback(request)
    
    logger.info("feedback generate success")
    
    return response

