"""对话管理接口"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from app.services.memory_service import memory_service
from app.utils.token_util import get_user_id_from_token
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from app.core.config import get_settings

router = APIRouter(prefix="/conversations", tags=["对话管理"])


@router.get("")
async def list_conversations(request: Request):
    """获取对话列表（只返回当前用户的对话）"""
    # 从请求头获取Token
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    
    # 验证Token（必须登录才能查看对话列表）
    if not token:
        return JSONResponse(
            status_code=401,
            content={"detail": "请先登录后再查看对话列表"},
        )
    
    # 解析用户ID
    user_id = get_user_id_from_token(token)
    
    # 验证用户ID是否有效
    if not user_id:
        return JSONResponse(
            status_code=401,
            content={"detail": "Token无效，请重新登录"},
        )
    
    # 获取当前用户的对话
    return memory_service.get_conversations(user_id=user_id)


@router.get("/{conversation_id}/messages")
async def get_messages(conversation_id: int):
    """获取对话历史消息"""
    return memory_service.get_history(conversation_id, max_messages=100)


@router.delete("/{conversation_id}")
async def delete_conversation(conversation_id: int):
    """删除对话"""
    memory_service.delete_conversation(conversation_id)
    return {"message": "已删除"}


class UpdateTitleRequest(BaseModel):
    title: str


@router.put("/{conversation_id}/title")
async def update_title(conversation_id: int, request: UpdateTitleRequest):
    """更新对话标题"""
    memory_service.update_title(conversation_id, request.title)
    return {"message": "已更新"}


@router.post("/{conversation_id}/pin")
async def toggle_pin(conversation_id: int):
    """切换置顶状态"""
    new_state = memory_service.toggle_pin(conversation_id)
    return {"pinned": new_state}


@router.post("/{conversation_id}/generate-title")
async def generate_title(conversation_id: int):
    """根据对话内容自动生成标题"""
    history = memory_service.get_history(conversation_id, max_messages=2)
    if not history:
        return {"title": "新对话"}

    first_msg = history[0]["content"]
    settings = get_settings()
    llm = ChatOpenAI(
        api_key=settings.mimo_api_key,
        base_url=settings.mimo_base_url,
        model=settings.mimo_model,
    )
    prompt = f"请根据以下用户消息生成一个简短的对话标题（不超过15个字，不要引号和标点）：\n{first_msg}"
    try:
        resp = await llm.ainvoke([HumanMessage(content=prompt)])
        title = resp.content.strip().replace('"', '').replace("'", "").replace("。", "")
        if len(title) > 20:
            title = title[:20]
        memory_service.update_title(conversation_id, title)
        return {"title": title}
    except Exception:
        return {"title": first_msg[:15]}


