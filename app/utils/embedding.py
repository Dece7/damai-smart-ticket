"""Embedding 封装 - 对接 DeepSeek Embedding API"""

from langchain_openai import OpenAIEmbeddings
from app.core.config import get_settings


def get_embedding_model() -> OpenAIEmbeddings:
    """获取 Embedding 模型（DeepSeek）"""
    settings = get_settings()
    return OpenAIEmbeddings(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        model=settings.embedding_model,
    )
