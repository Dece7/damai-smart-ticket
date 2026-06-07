"""RAG 问答服务 - 带引用溯源"""

import json
import logging
from pathlib import Path
from app.pipelines.rag_pipeline import get_rag_chain

logger = logging.getLogger(__name__)

_rag_chain = None
_retriever = None


def _get_rag():
    global _rag_chain, _retriever
    if _rag_chain is None:
        _rag_chain, _retriever, _ = get_rag_chain()
    return _rag_chain, _retriever


class RagService:
    async def chat(self, message: str):
        """RAG 问答（流式，带引用溯源）"""
        try:
            chain, retriever = _get_rag()

            # 检索相关文档，提取来源信息
            docs = retriever.invoke(message)
            sources = []
            seen = set()
            for doc in docs:
                source_path = doc.metadata.get("source", "")
                source_name = Path(source_path).stem if source_path else "未知文档"
                if source_name not in seen:
                    seen.add(source_name)
                    sources.append({
                        "doc": source_name,
                        "excerpt": doc.page_content[:150],
                    })
            yield f'data: {json.dumps({"type": "sources", "content": sources}, ensure_ascii=False)}\n\n'

            # 流式生成回答
            async for chunk in chain.astream(message):
                yield f'data: {json.dumps({"type": "token", "content": chunk}, ensure_ascii=False)}\n\n'

        except Exception as e:
            logger.error(f"RAG 问答异常: {e}")
            yield f'data: {json.dumps({"type": "error", "content": str(e)}, ensure_ascii=False)}\n\n'

        yield "data: [DONE]\n\n"


rag_service = RagService()
