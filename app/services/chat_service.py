import json
import logging
from pathlib import Path
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from app.core.config import get_settings
from app.core.prompts import SYSTEM_PROMPT_ASSISTANT
from app.chains.tools import search_program, get_program_detail, get_ticket_info, create_order
from app.services.memory_service import memory_service

logger = logging.getLogger(__name__)

TOOLS = [search_program, get_program_detail, get_ticket_info, create_order]
TOOLS_MAP = {t.name: t for t in TOOLS}

MAX_TOOL_ROUNDS = 5


class ChatService:
    def __init__(self):
        settings = get_settings()
        self.llm = ChatOpenAI(
            api_key=settings.mimo_api_key,
            base_url=settings.mimo_base_url,
            model=settings.mimo_model,
            streaming=True,
            stream_usage=True,
        ).bind_tools(TOOLS)

    async def chat(self, message: str, conversation_id: str | None, chat_type: str):
        """流式对话（支持 assistant / rag 两种模式）"""
        if not conversation_id:
            conv = memory_service.create_conversation(chat_type)
            conversation_id = str(conv.id)
            yield f'data: {json.dumps({"type": "conversation_id", "content": conversation_id}, ensure_ascii=False)}\n\n'

        memory_service.save_message(int(conversation_id), "user", message)

        saved_sources = None
        saved_usage = None
        full_response = ""

        try:
            if chat_type == "rag":
                # RAG 模式：检索知识库 + 生成回答
                async for chunk in self._rag_chat(message):
                    if chunk.get("type") == "sources":
                        saved_sources = chunk["content"]
                    elif chunk.get("type") == "usage":
                        saved_usage = chunk["content"]
                    elif chunk.get("type") == "token":
                        full_response += chunk["content"]
                    yield f'data: {json.dumps(chunk, ensure_ascii=False)}\n\n'
            else:
                # Assistant 模式：Function Calling
                async for chunk in self._assistant_chat(message, int(conversation_id)):
                    if chunk.get("type") == "usage":
                        saved_usage = chunk["content"]
                    elif chunk.get("type") == "token":
                        full_response += chunk["content"]
                    yield f'data: {json.dumps(chunk, ensure_ascii=False)}\n\n'

            memory_service.save_message(int(conversation_id), "assistant", full_response, sources=saved_sources, token_usage=saved_usage)

        except Exception as e:
            logger.error(f"对话异常: {e}")
            yield f'data: {json.dumps({"type": "error", "content": str(e)}, ensure_ascii=False)}\n\n'

        yield "data: [DONE]\n\n"

    async def _rag_chat(self, message: str):
        """RAG 模式：混合检索知识库 + 生成回答"""
        from app.pipelines.rag_pipeline import get_rag_chain, get_hybrid_retriever

        chain, retriever, llm = get_rag_chain()
        hybrid_retrieve = get_hybrid_retriever()

        # 混合检索（BM25 + 向量）
        docs = hybrid_retrieve(message)
        sources = []
        seen = set()
        for doc in docs:
            src = Path(doc.metadata.get("source", "")).stem
            if src and src not in seen:
                seen.add(src)
                sources.append({"doc": src, "excerpt": doc.page_content[:100]})
        if sources:
            yield {"type": "sources", "content": sources}

        # 流式生成
        full_response = ""
        async for chunk in chain.astream(message):
            if chunk:
                full_response += chunk
                yield {"type": "token", "content": chunk}

        # 用 LLM 的 token 计数方法估算用量
        try:
            prompt_tokens = llm.get_num_tokens(message)
            completion_tokens = llm.get_num_tokens(full_response)
            total_tokens = prompt_tokens + completion_tokens
            yield {"type": "usage", "content": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            }}
        except Exception as e:
            logger.warning(f"Token 统计失败: {e}")

        # 保存（调用方负责）
        self._last_sources = sources
        self._last_response = full_response

    async def _assistant_chat(self, message: str, conversation_id: int):
        """Assistant 模式：Function Calling + 多轮工具调用"""
        history = memory_service.get_history(conversation_id, max_messages=20)
        messages = [SystemMessage(content=SYSTEM_PROMPT_ASSISTANT)]
        for h in history:
            if h["role"] == "user":
                messages.append(HumanMessage(content=h["content"]))
            elif h["role"] == "assistant":
                messages.append(AIMessage(content=h["content"]))

        total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        # 多轮工具调用
        for _ in range(MAX_TOOL_ROUNDS):
            response = await self.llm.ainvoke(messages)
            messages.append(response)

            # 累计工具调用轮次的 token
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                u = response.usage_metadata
                total_usage["prompt_tokens"] += u.get("input_tokens", 0)
                total_usage["completion_tokens"] += u.get("output_tokens", 0)
                total_usage["total_tokens"] += u.get("total_tokens", 0)

            if not response.tool_calls:
                break

            tool_names = [tc["name"] for tc in response.tool_calls]
            tools_str = ", ".join(tool_names)
            yield {"type": "thinking", "content": f"正在调用工具: {tools_str}"}

            for tool_call in response.tool_calls:
                tool_func = TOOLS_MAP.get(tool_call["name"])
                if tool_func:
                    result = tool_func.invoke(tool_call["args"])
                    yield {"type": "tool_result", "tool": tool_call["name"], "content": result}
                    messages.append(ToolMessage(
                        content=json.dumps(result, ensure_ascii=False),
                        tool_call_id=tool_call["id"],
                    ))

        # 流式生成最终回答
        full_response = ""
        async for chunk in self.llm.astream(messages):
            if chunk.content:
                full_response += chunk.content
                yield {"type": "token", "content": chunk.content}
            # 流式最后一帧可能携带 usage_metadata
            if hasattr(chunk, "usage_metadata") and chunk.usage_metadata:
                u = chunk.usage_metadata
                total_usage["prompt_tokens"] += u.get("input_tokens", 0)
                total_usage["completion_tokens"] += u.get("output_tokens", 0)
                total_usage["total_tokens"] += u.get("total_tokens", 0)

        # 发送 token 统计
        if total_usage["total_tokens"] > 0:
            yield {"type": "usage", "content": total_usage}

        self._last_response = full_response
        self._last_sources = None


chat_service = ChatService()
