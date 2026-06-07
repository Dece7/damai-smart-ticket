"""对话数据模型 - 对应原项目 ChatTypeHistory / ChatHistoryMapper"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.core.database import Base


class Conversation(Base):
    """对话表"""
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), default="新对话")
    chat_type = Column(String(20), default="assistant")  # assistant / rag / agent
    pinned = Column(Integer, default=0)  # 0=未置顶, 1=置顶
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    """消息表"""
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    role = Column(String(20), nullable=False)  # user / assistant / system
    content = Column(Text, nullable=False)
    sources = Column(JSON, nullable=True)  # RAG 引用来源
    steps = Column(JSON, nullable=True)  # Agent 推理步骤 [{step, action, content}]
    token_usage = Column(JSON, nullable=True)  # {"prompt_tokens": N, "completion_tokens": N, "total_tokens": N}
    created_at = Column(DateTime, default=datetime.now)

    conversation = relationship("Conversation", back_populates="messages")
