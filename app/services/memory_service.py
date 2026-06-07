"""会话记忆服务 - 对应原项目 ChatTypeHistoryAdvisor + MessageChatMemoryAdvisor"""

import logging
from sqlalchemy import desc, case
from app.core.database import SessionLocal
from app.models.conversation import Conversation, Message

logger = logging.getLogger(__name__)


class MemoryService:
    def create_conversation(self, chat_type: str = "assistant") -> Conversation:
        """创建新对话"""
        db = SessionLocal()
        try:
            conv = Conversation(chat_type=chat_type)
            db.add(conv)
            db.commit()
            db.refresh(conv)
            return conv
        finally:
            db.close()

    def save_message(self, conversation_id: int, role: str, content: str, sources: list | None = None, steps: list | None = None, token_usage: dict | None = None):
        """保存消息"""
        db = SessionLocal()
        try:
            msg = Message(
                conversation_id=conversation_id,
                role=role,
                content=content,
                sources=sources,
                steps=steps,
                token_usage=token_usage,
            )
            db.add(msg)
            db.commit()
        finally:
            db.close()

    def get_history(self, conversation_id: int, max_messages: int = 20) -> list[dict]:
        """获取对话历史（最近 N 条）"""
        db = SessionLocal()
        try:
            messages = (
                db.query(Message)
                .filter(Message.conversation_id == conversation_id)
                .order_by(Message.id.desc())
                .limit(max_messages)
                .all()
            )
            return [{"role": m.role, "content": m.content, "sources": m.sources, "steps": m.steps} for m in reversed(messages)]
        finally:
            db.close()

    def get_conversations(self) -> list[dict]:
        """获取所有对话列表（置顶优先）"""
        db = SessionLocal()
        try:
            convs = (
                db.query(Conversation)
                .order_by(desc(Conversation.pinned), desc(Conversation.updated_at))
                .all()
            )
            return [
                {
                    "id": c.id,
                    "title": c.title,
                    "chat_type": c.chat_type,
                    "pinned": c.pinned,
                    "updated_at": str(c.updated_at),
                }
                for c in convs
            ]
        finally:
            db.close()

    def update_title(self, conversation_id: int, title: str):
        """更新对话标题"""
        db = SessionLocal()
        try:
            conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
            if conv:
                conv.title = title
                db.commit()
        finally:
            db.close()

    def toggle_pin(self, conversation_id: int) -> int:
        """切换置顶状态，返回新状态"""
        db = SessionLocal()
        try:
            conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
            if conv:
                conv.pinned = 0 if conv.pinned else 1
                db.commit()
                return conv.pinned
            return 0
        finally:
            db.close()

    def delete_conversation(self, conversation_id: int):
        """删除对话"""
        db = SessionLocal()
        try:
            conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
            if conv:
                db.delete(conv)
                db.commit()
        finally:
            db.close()


memory_service = MemoryService()
