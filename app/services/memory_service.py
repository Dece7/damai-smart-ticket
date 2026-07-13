"""会话记忆服务 - 对应原项目 ChatTypeHistoryAdvisor + MessageChatMemoryAdvisor"""

import logging
from sqlalchemy import desc, case
from app.core.database import SessionLocal
from app.models.conversation import Conversation, Message

logger = logging.getLogger(__name__)


class MemoryService:
    def create_conversation(self, chat_type: str = "assistant", user_id: int = None) -> Conversation:
        """创建新对话"""
        db = SessionLocal()
        try:
            conv = Conversation(chat_type=chat_type, user_id=user_id)
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

    def get_conversations(self, user_id: int = None) -> list[dict]:
        """获取对话列表（置顶优先），支持用户过滤"""
        db = SessionLocal()
        try:
            query = db.query(Conversation)
            # 如果提供了user_id，只返回该用户的对话
            if user_id is not None:
                query = query.filter(Conversation.user_id == user_id)
            else:
                # 如果没有提供user_id，只返回没有user_id的对话（兼容旧数据）
                query = query.filter(Conversation.user_id.is_(None))
            convs = query.order_by(desc(Conversation.pinned), desc(Conversation.updated_at)).all()
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


