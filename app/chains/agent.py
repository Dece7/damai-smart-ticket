"""LangGraph ReAct Agent - 对应原项目 Advisor 链编排

Agent 自动判断用户意图，选择合适的工具：
- 查节目/下单 → Function Calling 工具
- 问规则/政策 → RAG 知识库工具
- 简单闲聊 → 直接回答
"""

import json
import logging
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langgraph.prebuilt import create_react_agent
from app.core.config import get_settings
from app.core.prompts import SYSTEM_PROMPT_ASSISTANT
from app.chains.tools import (
    search_program, get_program_detail, get_ticket_info,
    create_order, search_knowledge_base,
)

logger = logging.getLogger(__name__)

ALL_TOOLS = [search_program, get_program_detail, get_ticket_info, create_order, search_knowledge_base]
TOOLS_MAP = {t.name: t for t in ALL_TOOLS}


def create_agent():
    """创建 LangGraph ReAct Agent"""
    settings = get_settings()
    llm = ChatOpenAI(
        api_key=settings.mimo_api_key,
        base_url=settings.mimo_base_url,
        model=settings.mimo_model,
        streaming=True,
        stream_usage=True,
    )
    agent = create_react_agent(
        model=llm,
        tools=ALL_TOOLS,
        prompt=SYSTEM_PROMPT_ASSISTANT,
    )
    return agent


async def run_agent(message: str, history: list[dict] | None = None):
    """运行 Agent，流式返回结果"""
    agent = create_agent()

    messages = []
    if history:
        for h in history:
            if h["role"] == "user":
                messages.append(HumanMessage(content=h["content"]))
            elif h["role"] == "assistant":
                messages.append(AIMessage(content=h["content"]))
    messages.append(HumanMessage(content=message))

    total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    step_num = 0

    try:
        async for event in agent.astream_events({"messages": messages}, version="v2"):
            kind = event.get("event", "")

            if kind == "on_chat_model_stream":
                content = event["data"]["chunk"].content
                if content:
                    yield f'data: {json.dumps({"type": "token", "content": content}, ensure_ascii=False)}\n\n'

            elif kind == "on_chat_model_end":
                output = event["data"].get("output")
                # 捕获 token 使用量
                if output and hasattr(output, "usage_metadata") and output.usage_metadata:
                    u = output.usage_metadata
                    total_usage["prompt_tokens"] += u.get("input_tokens", 0)
                    total_usage["completion_tokens"] += u.get("output_tokens", 0)
                    total_usage["total_tokens"] += u.get("total_tokens", 0)
                # 推理步骤：LLM 决定调用工具
                if output and hasattr(output, "tool_calls") and output.tool_calls:
                    step_num += 1
                    for tc in output.tool_calls:
                        tool_name = tc["name"]
                        args_str = json.dumps(tc["args"], ensure_ascii=False)
                        if len(args_str) > 100:
                            args_str = args_str[:100] + "..."
                        yield f'data: {json.dumps({"type": "step", "step": step_num, "action": "reasoning", "content": f"分析意图，选择工具: {tool_name}({args_str})"}, ensure_ascii=False)}\n\n'

            elif kind == "on_tool_start":
                tool_name = event.get("name", "")
                yield f'data: {json.dumps({"type": "step", "step": step_num, "action": "tool_start", "tool": tool_name, "content": f"执行工具: {tool_name}"}, ensure_ascii=False)}\n\n'

            elif kind == "on_tool_end":
                tool_name = event.get("name", "")
                output = event["data"].get("output", "")

                # RAG 工具返回时，提取引用来源
                if tool_name == "search_knowledge_base":
                    from pathlib import Path
                    try:
                        text = output if isinstance(output, str) else str(output)
                        from app.pipelines.document_pipeline import load_vectorstore
                        vs = load_vectorstore()
                        docs = vs.similarity_search(text[:200], k=3)
                        sources = []
                        seen = set()
                        for doc in docs:
                            src = Path(doc.metadata.get("source", "")).stem
                            if src and src not in seen:
                                seen.add(src)
                                sources.append({"doc": src, "excerpt": doc.page_content[:100]})
                        if sources:
                            yield f'data: {json.dumps({"type": "sources", "content": sources}, ensure_ascii=False)}\n\n'
                    except Exception as e:
                        logger.warning(f"提取引用来源失败: {e}")

                if not isinstance(output, str):
                    try:
                        output = json.dumps(output, ensure_ascii=False, default=str)
                    except Exception:
                        output = str(output)
                result_preview = output[:200] + "..." if len(output) > 200 else output
                yield f'data: {json.dumps({"type": "step", "step": step_num, "action": "tool_end", "tool": tool_name, "content": f"工具返回: {result_preview}"}, ensure_ascii=False)}\n\n'

    except Exception as e:
        logger.error(f"Agent 异常: {e}")
        yield f'data: {json.dumps({"type": "error", "content": str(e)}, ensure_ascii=False)}\n\n'

    # 发送 token 统计
    if total_usage["total_tokens"] > 0:
        yield f'data: {json.dumps({"type": "usage", "content": total_usage}, ensure_ascii=False)}\n\n'

    yield "data: [DONE]\n\n"
