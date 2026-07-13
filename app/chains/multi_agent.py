"""多 Agent 协作系统 - 优化版 Supervisor 模式

架构：
  用户输入 → intent_classifier → router → 子 Agent(s) → answer_generator → END
                                                   ↓（异常）
                                              fallback → END

节点职责：
  - intent_classifier: 纯意图分类，输出结构化 intent + confidence
  - router: 读 state.intent 决定路由，纯逻辑无 LLM 调用
  - ticket_agent: 票务操作（ReAct 子 Agent）
  - knowledge_agent: 知识库检索（ReAct 子 Agent）
  - answer_generator: 统一格式化最终回答
  - fallback: 异常兜底，友好错误提示
"""

import json
import logging
from typing import Annotated, TypedDict
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from app.core.config import get_settings
from app.core.prompts import (
    SUPERVISOR_PROMPT, TICKET_AGENT_PROMPT, KNOWLEDGE_AGENT_PROMPT,
    SYSTEM_PROMPT_ASSISTANT,
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

# 意图分类提示词
INTENT_CLASSIFIER_PROMPT = """你是大麦智能客服的意图分类器。分析用户问题，输出意图分类。

分类规则：
1. 涉及查询演出、购票、下单、余票、订单、推荐 → 输出 ticket
2. 涉及退票政策、订票规则、入场须知、支付方式、会员权益、优惠活动、取票配送、无障碍服务、儿童票、演出变更 → 输出 knowledge
3. 同时涉及票务操作和规则查询（如"帮我查演唱会，顺便告诉我退票政策"）→ 输出 both
4. 简单闲聊（打招呼、感谢、无关话题）→ 输出 chat

只输出一个小写的分类词：ticket / knowledge / both / chat"""

ANSWER_GENERATOR_PROMPT = """你是大麦智能客服"麦小蜜"的回答整理专家。你的任务是将子 Agent 的执行结果整合为一条高质量的最终回复。

要求：
1. 用温柔、有礼貌的语气回答，以"亲"开头
2. 如果有多个 Agent 的结果，整合为一条连贯的回复，不要重复信息
3. 如果结果中包含来源标注，保留来源信息
4. 如果结果为空或执行失败，给出友好的替代回复
5. 不要提及任何内部标识（如"票务专家"、"知识库专家"等）
6. 直接回答用户的问题，不要重复用户的问题"""


# ==================== 状态定义 ====================

class AgentState(TypedDict):
    """多 Agent 共享状态 - 结构化字段"""
    messages: Annotated[list, add_messages]  # 对话消息（用 reducer 自动追加）
    intent: str           # 意图分类: "ticket" / "knowledge" / "both" / "chat"
    route: str            # 路由决策: "ticket" / "knowledge" / "both" / "chat"
    current_agent: str    # 当前执行的 agent 名称
    agent_results: dict   # {"ticket": "结果...", "knowledge": "结果..."}
    error: str | None     # 错误信息
    final_answer: str | None  # 最终回答


# ==================== 工厂函数 ====================

def _create_llm(streaming: bool = True):
    """创建 LLM 实例"""
    settings = get_settings()
    return ChatOpenAI(
        api_key=settings.mimo_api_key,
        base_url=settings.mimo_base_url,
        model=settings.mimo_model,
        streaming=streaming,
        stream_usage=True,
    )


def _create_ticket_agent():
    """创建票务 ReAct 子 Agent"""
    return create_react_agent(
        model=_create_llm(),
        tools=TICKET_TOOLS,
        prompt=TICKET_AGENT_PROMPT,
    )


def _create_knowledge_agent():
    """创建知识库 ReAct 子 Agent"""
    return create_react_agent(
        model=_create_llm(),
        tools=KNOWLEDGE_TOOLS,
        prompt=KNOWLEDGE_AGENT_PROMPT,
    )


# ==================== 节点函数 ====================

def intent_classifier_node(state: AgentState) -> dict:
    """意图分类节点 - 纯分类，输出结构化 intent"""
    llm = _create_llm(streaming=False)
    messages = state["messages"]
    system_msg = SystemMessage(content=INTENT_CLASSIFIER_PROMPT)

    try:
        response = llm.invoke([system_msg] + messages)
        content = response.content.strip().lower()

        # 解析意图
        valid_intents = ("ticket", "knowledge", "both", "chat")
        intent = "chat"  # 默认闲聊
        for valid in valid_intents:
            if valid in content:
                intent = valid
                break

        logger.info(f"意图分类: '{content}' → {intent}")
        return {"intent": intent, "current_agent": "intent_classifier"}

    except Exception as e:
        logger.error(f"意图分类失败: {e}")
        return {"intent": "chat", "error": f"意图分类失败: {e}", "current_agent": "intent_classifier"}


def router_node(state: AgentState) -> dict:
    """路由节点 - 读 state.intent 决定路由，纯逻辑无 LLM 调用"""
    intent = state.get("intent", "chat")
    logger.info(f"路由决策: intent={intent} → route={intent}")
    return {"route": intent, "current_agent": "router"}


def ticket_agent_node(state: AgentState) -> dict:
    """票务 Agent 节点"""
    agent = _create_ticket_agent()
    messages = state["messages"]

    try:
        result = agent.invoke({"messages": messages})
        last_msg = result["messages"][-1]
        answer = last_msg.content if hasattr(last_msg, "content") else str(last_msg)

        # 写入 agent_results，保留已有结果
        agent_results = dict(state.get("agent_results", {}))
        agent_results["ticket"] = answer

        return {
            "agent_results": agent_results,
            "current_agent": "ticket",
            "messages": [AIMessage(content=answer)],
        }

    except Exception as e:
        logger.error(f"票务 Agent 执行失败: {e}")
        return {
            "error": f"票务 Agent 执行失败: {e}",
            "current_agent": "ticket",
            "agent_results": dict(state.get("agent_results", {})),
        }


def knowledge_agent_node(state: AgentState) -> dict:
    """知识库 Agent 节点"""
    agent = _create_knowledge_agent()
    messages = state["messages"]

    try:
        result = agent.invoke({"messages": messages})
        last_msg = result["messages"][-1]
        answer = last_msg.content if hasattr(last_msg, "content") else str(last_msg)

        # 写入 agent_results，保留已有结果
        agent_results = dict(state.get("agent_results", {}))
        agent_results["knowledge"] = answer

        return {
            "agent_results": agent_results,
            "current_agent": "knowledge",
            "messages": [AIMessage(content=answer)],
        }

    except Exception as e:
        logger.error(f"知识库 Agent 执行失败: {e}")
        return {
            "error": f"知识库 Agent 执行失败: {e}",
            "current_agent": "knowledge",
            "agent_results": dict(state.get("agent_results", {})),
        }


def answer_generator_node(state: AgentState) -> dict:
    """回答生成节点 - 统一格式化最终回答

    单 Agent 结果直接透传（省一次 LLM 调用，降延迟）。
    多 Agent 结果用 LLM 整合。
    chat 意图用 LLM 直接生成回答。
    """
    agent_results = state.get("agent_results", {})
    error = state.get("error")

    # 如果有错误且没有有效结果，交给 fallback
    if error and not agent_results:
        return {"final_answer": None, "error": error}

    # 单 Agent 结果：直接透传，不过 LLM（省 ~5-10s）
    if len(agent_results) == 1:
        answer = list(agent_results.values())[0]
        logger.info("answer_generator: 单 Agent 结果，直接透传")
        return {"final_answer": answer, "current_agent": "answer_generator", "messages": [AIMessage(content=answer)]}

    # 多 Agent 结果：用 LLM 整合
    if len(agent_results) > 1:
        llm = _create_llm(streaming=True)
        user_question = ""
        for msg in reversed(state["messages"]):
            if isinstance(msg, HumanMessage):
                user_question = msg.content
                break
        results_text = "\n\n".join(
            f"【{name}的结果】\n{result}" for name, result in agent_results.items()
        )
        prompt = f"{ANSWER_GENERATOR_PROMPT}\n\n用户问题: {user_question}\n\n子 Agent 执行结果:\n{results_text}"
        try:
            response = llm.invoke([HumanMessage(content=prompt)])
            final = response.content.strip()
            return {"final_answer": final, "current_agent": "answer_generator", "messages": [AIMessage(content=final)]}
        except Exception as e:
            logger.error(f"回答生成失败: {e}")
            fallback_answer = "\n\n".join(agent_results.values())
            return {"final_answer": fallback_answer, "current_agent": "answer_generator", "messages": [AIMessage(content=fallback_answer)]}

    # chat 意图或无 agent_results：用 LLM 直接生成回答
    llm = _create_llm(streaming=True)
    system_msg = SystemMessage(content=SYSTEM_PROMPT_ASSISTANT)
    chat_messages = [system_msg] + list(state["messages"])
    try:
        response = llm.invoke(chat_messages)
        final = response.content.strip()
        return {"final_answer": final, "current_agent": "answer_generator", "messages": [AIMessage(content=final)]}
    except Exception as e:
        logger.error(f"回答生成失败: {e}")
        return {"final_answer": "亲，抱歉暂时无法处理您的请求，请稍后再试~", "current_agent": "answer_generator"}


def fallback_node(state: AgentState) -> dict:
    """兜底节点 - 异常处理，友好错误提示"""
    error = state.get("error", "未知错误")
    logger.warning(f"进入兜底节点: {error}")

    fallback_answer = "亲，抱歉系统暂时遇到了点问题，请稍后再试哦~如有紧急需求，可以联系人工客服为您处理。"
    return {
        "final_answer": fallback_answer,
        "current_agent": "fallback",
        "messages": [AIMessage(content=fallback_answer)],
    }


# ==================== 条件边路由函数 ====================

def route_after_router(state: AgentState) -> str:
    """router 后的路由决策 - 读 state 字段"""
    route = state.get("route", "chat")
    error = state.get("error")

    if error:
        return "fallback"

    routing_map = {
        "ticket": "ticket_agent",
        "knowledge": "knowledge_agent",
        "both": "ticket_agent",  # both 先走 ticket，ticket 后再链到 knowledge
        "chat": "answer_generator",
    }
    target = routing_map.get(route, "answer_generator")
    logger.info(f"路由: {route} → {target}")
    return target


def route_after_ticket(state: AgentState) -> str:
    """ticket_agent 后的路由 - 检查是否需要链到 knowledge"""
    error = state.get("error")
    if error:
        return "fallback"

    route = state.get("route", "ticket")
    if route == "both":
        return "knowledge_agent"
    return "answer_generator"


def route_after_answer(state: AgentState) -> str:
    """answer_generator 后的路由 - 检查是否有错误需要兜底"""
    if state.get("error") and not state.get("final_answer"):
        return "fallback"
    return "end"


# ==================== 图构建 ====================

def build_multi_agent_graph():
    """构建多 Agent 图 - 优化版"""
    graph = StateGraph(AgentState)

    # 添加节点
    graph.add_node("intent_classifier", intent_classifier_node)
    graph.add_node("router", router_node)
    graph.add_node("ticket_agent", ticket_agent_node)
    graph.add_node("knowledge_agent", knowledge_agent_node)
    graph.add_node("answer_generator", answer_generator_node)
    graph.add_node("fallback", fallback_node)

    # 设置入口
    graph.set_entry_point("intent_classifier")

    # intent_classifier → router（普通边）
    graph.add_edge("intent_classifier", "router")

    # router → 子 Agent / answer_generator / fallback（条件边）
    graph.add_conditional_edges(
        "router",
        route_after_router,
        {
            "ticket_agent": "ticket_agent",
            "knowledge_agent": "knowledge_agent",
            "answer_generator": "answer_generator",
            "fallback": "fallback",
        },
    )

    # ticket_agent → knowledge_agent / answer_generator / fallback（条件边）
    graph.add_conditional_edges(
        "ticket_agent",
        route_after_ticket,
        {
            "knowledge_agent": "knowledge_agent",
            "answer_generator": "answer_generator",
            "fallback": "fallback",
        },
    )

    # knowledge_agent → answer_generator（普通边）
    graph.add_edge("knowledge_agent", "answer_generator")

    # answer_generator → END / fallback（条件边）
    graph.add_conditional_edges(
        "answer_generator",
        route_after_answer,
        {
            "end": END,
            "fallback": "fallback",
        },
    )

    # fallback → END（普通边）
    graph.add_edge("fallback", END)

    return graph.compile(checkpointer=MemorySaver())


# ==================== 流式运行器 ====================

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
    current_agent = "intent_classifier"
    prev_agent = ""
    sources = []
    seen_sources = set()

    config = {"configurable": {"thread_id": "default"}}

    # 节点进入时的步骤提示
    NODE_ENTER_HINTS = {
        "intent_classifier": "正在分析您的问题...",
        "router": "正在分配任务...",
        "ticket_agent": "正在查询票务信息...",
        "knowledge_agent": "正在检索知识库...",
        "answer_generator": "正在整理回答...",
        "fallback": "正在处理异常...",
    }

    try:
        async for event in agent.astream_events({"messages": messages}, version="v2", config=config):
            kind = event.get("event", "")
            node = event.get("metadata", {}).get("langgraph_node", "")

            # 跟踪当前所在节点，检测节点切换
            if node and node != current_agent:
                prev_agent = current_agent
                current_agent = node
                # 进入新节点时，推送步骤提示
                hint = NODE_ENTER_HINTS.get(current_agent)
                if hint:
                    step_num += 1
                    yield f'data: {json.dumps({"type": "step", "step": step_num, "action": "node_enter", "content": hint}, ensure_ascii=False)}\n\n'

            # 跳过 intent_classifier 和 router 的 LLM 流式事件（不推送给前端）
            if current_agent in ("intent_classifier", "router"):
                if kind == "on_chat_model_stream":
                    continue

            if kind == "on_chat_model_stream":
                if not inside_tool:
                    content = event["data"]["chunk"].content
                    if content:
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
                    agent_label = {
                        "ticket_agent": "票务专家",
                        "knowledge_agent": "知识库专家",
                        "answer_generator": "回答整理",
                        "fallback": "兜底处理",
                    }.get(current_agent, current_agent)
                    for tc in output.tool_calls:
                        tool_name = tc["name"]
                        args_str = json.dumps(tc["args"], ensure_ascii=False)
                        if len(args_str) > 100:
                            args_str = args_str[:100] + "..."
                        yield f'data: {json.dumps({"type": "step", "step": step_num, "action": "reasoning", "content": f"[{agent_label}] 选择工具: {tool_name}({args_str})"}, ensure_ascii=False)}\n\n'

            elif kind == "on_tool_start":
                inside_tool = True
                tool_name = event.get("name", "")
                agent_label = {
                    "ticket_agent": "票务专家",
                    "knowledge_agent": "知识库专家",
                }.get(current_agent, current_agent)
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
                                    if len(sources) >= 3:
                                        break
                    except Exception as e:
                        logger.warning(f"提取引用来源失败: {e}")

                if not isinstance(output, str):
                    try:
                        output = json.dumps(output, ensure_ascii=False, default=str)
                    except Exception:
                        output = str(output)
                result_preview = output[:100] + "..." if len(output) > 100 else output
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
