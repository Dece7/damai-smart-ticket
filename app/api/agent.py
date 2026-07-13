"""Agent 对话接口"""

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from app.services.agent_service import agent_service
from app.services.multi_agent_service import multi_agent_service
from app.core.security import check_injection, sanitize_input
from app.utils.java_api_client import java_api

router = APIRouter(prefix="/agent", tags=["Agent"])


class AgentRequest(BaseModel):
    message: str = Field(..., min_length=1, description="用户消息")
    conversation_id: str | None = Field(None, description="对话ID")


@router.post("")
async def agent_chat(request: AgentRequest, req: Request):
    """Agent 对话（自动选择工具，SSE 流式）"""
    message = sanitize_input(request.message)
    is_inject, reason = check_injection(message)
    if is_inject:
        return JSONResponse(
            status_code=400,
            content={"detail": f"输入被拒绝：{reason}"},
        )
    
    # 从请求头获取 Token
    token = req.headers.get("Authorization", "").replace("Bearer ", "")
    
    # 验证Token（必须登录才能使用）
    if not token:
        return JSONResponse(
            status_code=401,
            content={"detail": "请先登录后再使用AI客服"},
        )
    
    # 设置Token到Java API客户端
    java_api.set_token(token)
    
    # 获取用户ID
    user_id = java_api.get_user_id()
    
    # 验证用户ID是否有效
    if not user_id:
        return JSONResponse(
            status_code=401,
            content={"detail": "Token无效，请重新登录"},
        )

    return StreamingResponse(
        agent_service.chat(
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


@router.post("/multi")
async def multi_agent_chat(request: AgentRequest):
    """多 Agent 协作对话（Supervisor 模式，SSE 流式）"""
    message = sanitize_input(request.message)
    is_inject, reason = check_injection(message)
    if is_inject:
        return JSONResponse(
            status_code=400,
            content={"detail": f"输入被拒绝：{reason}"},
        )

    return StreamingResponse(
        multi_agent_service.chat(
            message=message,
            conversation_id=request.conversation_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )




