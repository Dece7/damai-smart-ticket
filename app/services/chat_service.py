import json
import logging
from pathlib import Path
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from app.core.config import get_settings
from app.core.prompts import SYSTEM_PROMPT_ASSISTANT
from app.chains.tools import (
    search_program, get_program_detail, get_ticket_info, create_order, search_knowledge_base,
    query_ticket_status, check_order_status, calculate_price, get_recommendations,
)
from app.services.memory_service import memory_service

logger = logging.getLogger(__name__)

TOOLS = [
    search_program, get_program_detail, get_ticket_info, create_order,
    search_knowledge_base, query_ticket_status, check_order_status,
    calculate_price, get_recommendations,
]
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
        from app.pipelines.rag_pipeline import (
            get_rag_chain, get_hybrid_retriever, rewrite_query, format_docs_with_source,
        )

        chain, llm = get_rag_chain()
        hybrid_retrieve = get_hybrid_retriever()

        # 查询改写 + 混合检索（BM25 + 向量）
        rewritten = rewrite_query(message)
        if rewritten != message:
            yield {"type": "step", "step": 1, "action": "reasoning",
                   "content": f"查询改写：「{message}」→「{rewritten}」"}
        docs = hybrid_retrieve(rewritten, original_query=message)
        sources = []
        seen = set()
        for doc in docs:
            src = Path(doc.metadata.get("source", "")).stem
            if src and src not in seen:
                seen.add(src)
                sources.append({"doc": src, "excerpt": doc.page_content[:100]})
        if sources:
            yield {"type": "sources", "content": sources}

        # 用改写后的查询 + 检索到的文档生成回答
        context = format_docs_with_source(docs)
        chain_input = {"context": context, "question": rewritten}

        # 流式生成
        full_response = ""
        async for chunk in chain.astream(chain_input):
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
        step_num = 0

        # 多轮工具调用（最多 MAX_TOOL_ROUNDS 轮）
        for round_idx in range(MAX_TOOL_ROUNDS):
            response = await self.llm.ainvoke(messages)
            messages.append(response)

            # 累计工具调用轮次的 token
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                u = response.usage_metadata
                total_usage["prompt_tokens"] += u.get("input_tokens", 0)
                total_usage["completion_tokens"] += u.get("output_tokens", 0)
                total_usage["total_tokens"] += u.get("total_tokens", 0)

            # 如果没有工具调用，说明 LLM 要直接回答
            if not response.tool_calls:
                break

            # 执行工具调用
            for tool_call in response.tool_calls:
                step_num += 1
                tool_name = tool_call["name"]
                args_str = json.dumps(tool_call["args"], ensure_ascii=False)
                if len(args_str) > 100:
                    args_str = args_str[:100] + "..."
                yield {"type": "step", "step": step_num, "action": "reasoning", "content": f"分析意图，选择工具: {tool_name}({args_str})"}

                tool_func = TOOLS_MAP.get(tool_name)
                if tool_func:
                    yield {"type": "step", "step": step_num, "action": "tool_start", "tool": tool_name, "content": f"执行工具: {tool_name}"}
                    result = tool_func.invoke(tool_call["args"])

                    # 如果是知识库工具，提取来源
                    if tool_name == "search_knowledge_base":
                        text = result if isinstance(result, str) else str(result)
                        sources = []
                        seen = set()
                        lines = text.split("\n")
                        for i, line in enumerate(lines):
                            line = line.strip()
                            if line.startswith("[来源：") and line.endswith("]"):
                                src = line[4:-1]
                                if src and src not in seen:
                                    seen.add(src)
                                    # 取来源标记后面的内容作为摘要
                                    excerpt = ""
                                    for j in range(i+1, min(i+3, len(lines))):
                                        if lines[j].strip() and not lines[j].strip().startswith("[来源："):
                                            excerpt = lines[j].strip()[:100]
                                            break
                                    sources.append({"doc": src, "excerpt": excerpt})
                        if sources:
                            yield {"type": "sources", "content": sources}

                    result_preview = str(result)[:200] + "..." if len(str(result)) > 200 else str(result)
                    yield {"type": "step", "step": step_num, "action": "tool_end", "tool": tool_name, "content": f"工具返回: {result_preview}"}
                    messages.append(ToolMessage(
                        content=json.dumps(result, ensure_ascii=False),
                        tool_call_id=tool_call["id"],
                    ))

            # 工具调用后，下一轮 LLM 应该生成最终回答
            # 但为了防止 LLM 一直调用工具不回答，限制最多 2 轮工具调用
            if step_num >= 2:
                break

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
