"""Router-Skill 智能助手接口"""

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from app.services.router_skill_service import router_skill_service
from app.utils.token_util import get_user_id_from_token
from app.utils.java_api_client import java_api
from app.core.security import check_injection, sanitize_input

router = APIRouter(prefix="/router-skill", tags=["Router-Skill智能助手"])


class RouterSkillRequest(BaseModel):
    message: str = Field(..., min_length=1, description="用户消息")
    conversation_id: str | None = Field(None, description="对话ID")


@router.post("")
async def router_skill_chat(request: RouterSkillRequest, req: Request):
    """Router-Skill 对话（SSE 流式）"""
    message = sanitize_input(request.message)
    is_inject, reason = check_injection(message)
    if is_inject:
        return JSONResponse(
            status_code=400,
            content={"detail": f"输入被拒绝：{reason}"},
        )
    
    # 从请求头获取Token
    token = req.headers.get("Authorization", "").replace("Bearer ", "")
    
    # 设置Token
    java_api.set_token(None)
    if token:
        java_api.set_token(token)
    
    # 获取用户ID
    user_id = java_api.get_user_id()

    return StreamingResponse(
        router_skill_service.chat(
            message=message,
            conversation_id=request.conversation_id,
            user_id=user_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
