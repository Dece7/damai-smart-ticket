from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from app.services.chat_service import ChatService
from app.utils.token_util import get_user_id_from_token
from app.core.security import check_injection, sanitize_input

router = APIRouter(prefix="/chat", tags=["对话"])

chat_service = ChatService()


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="用户消息")
    conversation_id: str | None = Field(None, description="对话ID，新建对话不传")
    chat_type: str = Field("assistant", description="对话类型: assistant | rag")


@router.post("")
async def chat(request: ChatRequest, req: Request):
    """流式对话接口（SSE）

    - chat_type=assistant: 贴心助手（Function Calling）
    - chat_type=rag: 规则助手（RAG 知识库问答）
    """
    message = sanitize_input(request.message)
    is_inject, reason = check_injection(message)
    if is_inject:
        return JSONResponse(
            status_code=400,
            content={"detail": f"输入被拒绝：{reason}"},
        )
    
    # 从请求头获取Token
    token = req.headers.get("Authorization", "").replace("Bearer ", "")
    
    # 验证Token（必须登录才能使用）
    if not token:
        return JSONResponse(
            status_code=401,
            content={"detail": "请先登录后再使用AI客服"},
        )
    
    # 解析用户ID
    user_id = get_user_id_from_token(token)
    
    # 验证用户ID是否有效
    if not user_id:
        return JSONResponse(
            status_code=401,
            content={"detail": "Token无效，请重新登录"},
        )

    generator = chat_service.chat(
        message=message,
        conversation_id=request.conversation_id,
        chat_type=request.chat_type,
        user_id=user_id,
    )

    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


