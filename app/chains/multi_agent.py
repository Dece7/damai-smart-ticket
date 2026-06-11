"""多 Agent 协作系统 - Supervisor 模式

架构：
  用户输入 → Supervisor（编排）→ 票务 Agent / 知识 Agent → 合并结果

Supervisor 分析用户意图，将任务分派给专业子 Agent，
子 Agent 独立执行后返回结果，Supervisor 汇总输出。
"""

import json
import logging
from typing import Annotated, TypedDict, Literal
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import create_react_agent
from app.core.config import get_settings
from app.core.prompts import (
    SUPERVISOR_PROMPT, TICKET_AGENT_PROMPT, KNOWLEDGE_AGENT_PROMPT,
)
from app.chains.tools import (
    search_program, get_program_detail, get_ticket_info,
    create_order, search_knowledge_base,
    query_ticket_status, check_order_status, calculate_price, get_recommendations,
)

logger = logging.getLogger(__name__)

# 工具分组
TICKET_TOOLS = [
    search_program, get_program_detail, get_ticket_info, create_order,
    query_ticket_status, check_order_status, calculate_price, get_recommendations,
]
KNOWLEDGE_TOOLS = [search_knowledge_base]


class AgentState(TypedDict):
    """多 Agent 共享状态"""
    messages: Annotated[list, "消息列表"]


def _create_llm():
    """创建 LLM 实例"""
    settings = get_settings()
    return ChatOpenAI(
        api_key=settings.mimo_api_key,
        base_url=settings.mimo_base_url,
        model=settings.mimo_model,
        streaming=True,
        stream_usage=True,
    )


def _create_ticket_agent():
    """创建票务 Agent"""
    return create_react_agent(
        model=_create_llm(),
        tools=TICKET_TOOLS,
        prompt=TICKET_AGENT_PROMPT,
    )


def _create_knowledge_agent():
    """创建知识库 Agent"""
    return create_react_agent(
        model=_create_llm(),
        tools=KNOWLEDGE_TOOLS,
        prompt=KNOWLEDGE_AGENT_PROMPT,
    )


def _create_supervisor():
    """创建 Supervisor 路由节点"""
    llm = _create_llm()

    def supervisor_node(state: AgentState) -> dict:
        """Supervisor 分析意图，决定路由"""
        messages = state["messages"]
        # 加入 Supervisor 提示词
        system_msg = SystemMessage(content=SUPERVISOR_PROMPT)
        response = llm.invoke([system_msg] + messages)

        content = response.content.strip()

        # 解析路由决策
        if "ticket_agent" in content and "knowledge_agent" in content:
            # 需要两个 Agent
            return {"messages": [AIMessage(content="__route__:both")]}
        elif "ticket_agent" in content:
            return {"messages": [AIMessage(content="__route__:ticket")]}
        elif "knowledge_agent" in content:
            return {"messages": [AIMessage(content="__route__:knowledge")]}
        else:
            # 直接回答（闲聊）
            return {"messages": [response]}

    return supervisor_node


def _filter_route_messages(messages: list) -> list:
    """过滤掉路由标记消息，避免干扰子 Agent"""
    return [m for m in messages if not (hasattr(m, "content") and "__route__" in m.content)]


def _create_ticket_node():
    """票务 Agent 节点"""
    agent = _create_ticket_agent()

    def ticket_node(state: AgentState) -> dict:
        filtered = _filter_route_messages(state["messages"])
        result = agent.invoke({"messages": filtered})
        return {"messages": result["messages"][-1:]}

    return ticket_node


def _create_knowledge_node():
    """知识库 Agent 节点"""
    agent = _create_knowledge_agent()

    def knowledge_node(state: AgentState) -> dict:
        filtered = _filter_route_messages(state["messages"])
        result = agent.invoke({"messages": filtered})
        return {"messages": result["messages"][-1:]}

    return knowledge_node


def _route_after_supervisor(state: AgentState) -> Literal["ticket", "knowledge", "end"]:
    """Supervisor 后的路由决策"""
    last_msg = state["messages"][-1]
    content = last_msg.content if hasattr(last_msg, "content") else ""

    if "__route__:both" in content:
        return "ticket"  # 先执行票务，再执行知识
    elif "__route__:ticket" in content:
        return "ticket"
    elif "__route__:knowledge" in content:
        return "knowledge"
    else:
        return "end"  # 直接回答


def _route_after_ticket(state: AgentState) -> Literal["knowledge", "end"]:
    """票务 Agent 后的路由：检查是否还需要知识库"""
    # 回溯历史，看 Supervisor 是否决定要两个 Agent
    for msg in state["messages"]:
        content = msg.content if hasattr(msg, "content") else ""
        if "__route__:both" in content:
            return "knowledge"
    return "end"


def build_multi_agent_graph():
    """构建多 Agent 图"""
    graph = StateGraph(AgentState)

    # 添加节点
    graph.add_node("supervisor", _create_supervisor())
    graph.add_node("ticket", _create_ticket_node())
    graph.add_node("knowledge", _create_knowledge_node())

    # 设置入口
    graph.set_entry_point("supervisor")

    # Supervisor 路由
    graph.add_conditional_edges(
        "supervisor",
        _route_after_supervisor,
        {
            "ticket": "ticket",
            "knowledge": "knowledge",
            "end": END,
        },
    )

    # 票务 Agent 后路由
    graph.add_conditional_edges(
        "ticket",
        _route_after_ticket,
        {
            "knowledge": "knowledge",
            "end": END,
        },
    )

    # 知识库 Agent 后结束
    graph.add_edge("knowledge", END)

    return graph.compile()


async def run_multi_agent(message: str, history: list[dict] | None = None):
    """运行多 Agent，流式返回结果"""
    agent = build_multi_agent_graph()

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
    inside_tool = False
    current_agent = "supervisor"
    sources = []
    seen_sources = set()

    try:
        async for event in agent.astream_events({"messages": messages}, version="v2"):
            kind = event.get("event", "")
            node = event.get("metadata", {}).get("langgraph_node", "")

            # 跟踪当前所在 Agent
            if node in ("ticket", "knowledge", "supervisor"):
                current_agent = node

            if kind == "on_chat_model_stream":
                # 工具执行期间和 Supervisor 节点的 LLM 流式事件不推送给前端
                if not inside_tool and current_agent != "supervisor":
                    content = event["data"]["chunk"].content
                    if content and "__route__" not in content:
                        yield f'data: {json.dumps({"type": "token", "content": content}, ensure_ascii=False)}\n\n'

            elif kind == "on_chat_model_end":
                output = event["data"].get("output")
                if output and hasattr(output, "usage_metadata") and output.usage_metadata:
                    u = output.usage_metadata
                    total_usage["prompt_tokens"] += u.get("input_tokens", 0)
                    total_usage["completion_tokens"] += u.get("output_tokens", 0)
                    total_usage["total_tokens"] += u.get("total_tokens", 0)

                # 推理步骤
                if output and hasattr(output, "tool_calls") and output.tool_calls:
                    step_num += 1
                    agent_label = {"ticket": "票务专家", "knowledge": "知识库专家", "supervisor": "调度中心"}.get(current_agent, current_agent)
                    for tc in output.tool_calls:
                        tool_name = tc["name"]
                        args_str = json.dumps(tc["args"], ensure_ascii=False)
                        if len(args_str) > 100:
                            args_str = args_str[:100] + "..."
                        yield f'data: {json.dumps({"type": "step", "step": step_num, "action": "reasoning", "content": f"[{agent_label}] 选择工具: {tool_name}({args_str})"}, ensure_ascii=False)}\n\n'

            elif kind == "on_tool_start":
                inside_tool = True
                tool_name = event.get("name", "")
                agent_label = {"ticket": "票务专家", "knowledge": "知识库专家"}.get(current_agent, current_agent)
                yield f'data: {json.dumps({"type": "step", "step": step_num, "action": "tool_start", "tool": tool_name, "content": f"[{agent_label}] 执行: {tool_name}"}, ensure_ascii=False)}\n\n'

            elif kind == "on_tool_end":
                inside_tool = False
                tool_name = event.get("name", "")
                output = event["data"].get("output", "")

                # 提取引用来源
                if tool_name == "search_knowledge_base":
                    try:
                        if hasattr(output, "content"):
                            text = output.content
                        elif isinstance(output, str):
                            text = output
                        else:
                            text = str(output)

                        lines = text.split("\n")
                        for i, line in enumerate(lines):
                            line = line.strip()
                            if line.startswith("[来源：") and line.endswith("]"):
                                src = line[4:-1]
                                if src and src not in seen_sources:
                                    seen_sources.add(src)
                                    excerpt = ""
                                    for j in range(i+1, min(i+3, len(lines))):
                                        if lines[j].strip() and not lines[j].strip().startswith("[来源："):
                                            excerpt = lines[j].strip()[:100]
                                            break
                                    sources.append({"doc": src, "excerpt": excerpt})
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
        logger.error(f"多 Agent 异常: {e}")
        yield f'data: {json.dumps({"type": "error", "content": str(e)}, ensure_ascii=False)}\n\n'

    # 发送引用来源
    if sources:
        yield f'data: {json.dumps({"type": "sources", "content": sources}, ensure_ascii=False)}\n\n'

    # 发送 token 统计
    if total_usage["total_tokens"] > 0:
        yield f'data: {json.dumps({"type": "usage", "content": total_usage}, ensure_ascii=False)}\n\n'

    yield "data: [DONE]\n\n"
