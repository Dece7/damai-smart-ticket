"""LangGraph 优化版测试

验证：
1. 图结构正确（节点、边、条件边）
2. 状态流转正确（结构化字段）
3. 路由准确性（4 种意图）
4. 节点独立可测
5. 异常兜底
"""

import asyncio
import json
import logging
import sys
import io

# Windows 控制台 UTF-8 编码（仅直接运行时）
if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


def test_graph_structure():
    """测试 1：图结构验证"""
    print("=" * 60)
    print("【1】图结构验证")
    print("=" * 60)

    from app.chains.multi_agent import build_multi_agent_graph

    graph = build_multi_agent_graph()

    # 检查节点
    nodes = set(graph.get_graph().nodes)
    expected_nodes = {"intent_classifier", "router", "ticket_agent", "knowledge_agent",
                      "answer_generator", "fallback", "__start__", "__end__"}
    print(f"节点: {sorted(nodes)}")
    missing = expected_nodes - nodes
    if missing:
        print(f"  [FAIL] 缺少节点: {missing}")
    else:
        print(f"  [OK] 所有 {len(expected_nodes)} 个节点都存在")

    # 检查边
    edges = list(graph.get_graph().edges)
    print(f"边数: {len(edges)}")
    for edge in edges:
        print(f"  {edge.source} → {edge.target}")

    return len(missing) == 0


def test_state_definition():
    """测试 2：状态定义验证"""
    print("\n" + "=" * 60)
    print("【2】状态定义验证")
    print("=" * 60)

    from app.chains.multi_agent import AgentState

    required_fields = ["messages", "intent", "route", "current_agent",
                       "agent_results", "error", "final_answer"]

    annotations = AgentState.__annotations__
    print(f"State 字段: {list(annotations.keys())}")

    missing = [f for f in required_fields if f not in annotations]
    if missing:
        print(f"  [FAIL] 缺少字段: {missing}")
        return False
    else:
        print(f"  [OK] 所有 {len(required_fields)} 个字段都存在")
        for field in required_fields:
            print(f"    {field}: {annotations[field]}")
        return True


def test_intent_classifier():
    """测试 3：意图分类节点独立测试"""
    print("\n" + "=" * 60)
    print("【3】意图分类节点测试")
    print("=" * 60)

    from app.chains.multi_agent import intent_classifier_node
    from langchain_core.messages import HumanMessage

    test_cases = [
        ("帮我查一下周杰伦演唱会", "ticket"),
        ("退票政策是什么", "knowledge"),
        ("帮我订票，顺便告诉我退票规则", "both"),
        ("你好", "chat"),
    ]

    all_pass = True
    for query, expected in test_cases:
        state = {"messages": [HumanMessage(content=query)]}
        result = intent_classifier_node(state)
        intent = result.get("intent", "?")
        status = "[OK]" if intent == expected else "[FAIL]"
        if intent != expected:
            all_pass = False
        print(f"  {status} 「{query}」 → {intent} (期望: {expected})")

    return all_pass


def test_router():
    """测试 4：路由节点独立测试"""
    print("\n" + "=" * 60)
    print("【4】路由节点测试")
    print("=" * 60)

    from app.chains.multi_agent import router_node, route_after_router

    test_cases = [
        ("ticket", "ticket_agent"),
        ("knowledge", "knowledge_agent"),
        ("both", "ticket_agent"),
        ("chat", "answer_generator"),
    ]

    all_pass = True
    for intent, expected_route in test_cases:
        state = {"intent": intent}
        router_result = router_node(state)
        actual_route = route_after_router({**state, **router_result})
        status = "[OK]" if actual_route == expected_route else "[FAIL]"
        if actual_route != expected_route:
            all_pass = False
        print(f"  {status} intent={intent} → {actual_route} (期望: {expected_route})")

    # 测试错误路由
    state = {"intent": "ticket", "error": "some error"}
    route = route_after_router(state)
    status = "[OK]" if route == "fallback" else "[FAIL]"
    if route != "fallback":
        all_pass = False
    print(f"  {status} intent=ticket + error → {route} (期望: fallback)")

    return all_pass


def test_ticket_to_knowledge_chain():
    """测试 5：ticket → knowledge 链式路由"""
    print("\n" + "=" * 60)
    print("【5】ticket → knowledge 链式路由测试")
    print("=" * 60)

    from app.chains.multi_agent import route_after_ticket

    # both 意图：ticket 后应该链到 knowledge
    state = {"route": "both", "agent_results": {"ticket": "some result"}}
    result = route_after_ticket(state)
    status1 = "[OK]" if result == "knowledge_agent" else "[FAIL]"

    # ticket 意图：ticket 后应该到 answer_generator
    state = {"route": "ticket", "agent_results": {"ticket": "some result"}}
    result = route_after_ticket(state)
    status2 = "[OK]" if result == "answer_generator" else "[FAIL]"

    # 错误：应该到 fallback
    state = {"route": "both", "error": "something failed"}
    result = route_after_ticket(state)
    status3 = "[OK]" if result == "fallback" else "[FAIL]"

    print(f"  {status1} route=both → knowledge_agent")
    print(f"  {status2} route=ticket → answer_generator")
    print(f"  {status3} route=both + error → fallback")

    all_pass = "[FAIL]" not in (status1 + status2 + status3)
    return all_pass


def test_answer_generator():
    """测试 6：回答生成节点独立测试"""
    print("\n" + "=" * 60)
    print("【6】回答生成节点测试")
    print("=" * 60)

    from app.chains.multi_agent import answer_generator_node
    from langchain_core.messages import HumanMessage, AIMessage

    # 测试 1：单 Agent 结果
    state = {
        "messages": [HumanMessage(content="退票政策")],
        "intent": "knowledge",
        "agent_results": {"knowledge": "退票需要在演出前48小时申请。"},
        "error": None,
    }
    result = answer_generator_node(state)
    has_answer = result.get("final_answer") is not None
    print(f"  {'[OK]' if has_answer else '[FAIL]'} 单 Agent 结果 → 有 final_answer")

    # 测试 2：多 Agent 结果
    state = {
        "messages": [HumanMessage(content="查演唱会和退票政策")],
        "intent": "both",
        "agent_results": {
            "ticket": "周杰伦演唱会 2024年3月 北京",
            "knowledge": "退票需要在演出前48小时申请。",
        },
        "error": None,
    }
    result = answer_generator_node(state)
    has_answer = result.get("final_answer") is not None
    print(f"  {'[OK]' if has_answer else '[FAIL]'} 多 Agent 结果 → 有 final_answer")

    # 测试 3：错误 + 无结果 → 应该返回 None（让 fallback 处理）
    state = {
        "messages": [HumanMessage(content="test")],
        "intent": "ticket",
        "agent_results": {},
        "error": "something failed",
    }
    result = answer_generator_node(state)
    no_answer = result.get("final_answer") is None
    print(f"  {'[OK]' if no_answer else '[FAIL]'} 错误+无结果 → final_answer=None（交给 fallback）")

    return has_answer and no_answer


def test_fallback():
    """测试 7：兜底节点测试"""
    print("\n" + "=" * 60)
    print("【7】兜底节点测试")
    print("=" * 60)

    from app.chains.multi_agent import fallback_node

    state = {"error": "测试错误"}
    result = fallback_node(state)

    has_answer = result.get("final_answer") is not None
    is_friendly = "亲" in (result.get("final_answer") or "")
    print(f"  {'[OK]' if has_answer else '[FAIL]'} 有 final_answer")
    print(f"  {'[OK]' if is_friendly else '[FAIL]'} 友好提示（含'亲'）")

    return has_answer and is_friendly


async def test_e2e_ticket():
    """测试 8：端到端 - 票务查询"""
    print("\n" + "=" * 60)
    print("【8】端到端测试 - 票务查询")
    print("=" * 60)

    from app.chains.multi_agent import run_multi_agent

    full_response = ""
    steps = []
    async for chunk in run_multi_agent("帮我查一下北京的演唱会"):
        if chunk.startswith("data: ") and chunk != "data: [DONE]\n\n":
            try:
                d = json.loads(chunk[6:])
                if d.get("type") == "token":
                    full_response += d["content"]
                elif d.get("type") == "step":
                    steps.append(d)
                elif d.get("type") == "error":
                    print(f"  [FAIL] 错误: {d['content']}")
                    return False
            except:
                pass

    has_response = len(full_response) > 0
    has_steps = len(steps) > 0
    print(f"  {'[OK]' if has_response else '[FAIL]'} 有回复 ({len(full_response)} 字)")
    print(f"  {'[OK]' if has_steps else '[FAIL]'} 有执行步骤 ({len(steps)} 步)")
    if full_response:
        print(f"  回复预览: {full_response[:100]}...")

    return has_response


async def test_e2e_knowledge():
    """测试 9：端到端 - 知识库查询"""
    print("\n" + "=" * 60)
    print("【9】端到端测试 - 知识库查询")
    print("=" * 60)

    from app.chains.multi_agent import run_multi_agent

    full_response = ""
    async for chunk in run_multi_agent("退票政策是什么"):
        if chunk.startswith("data: ") and chunk != "data: [DONE]\n\n":
            try:
                d = json.loads(chunk[6:])
                if d.get("type") == "token":
                    full_response += d["content"]
                elif d.get("type") == "error":
                    print(f"  [FAIL] 错误: {d['content']}")
                    return False
            except:
                pass

    has_response = len(full_response) > 0
    print(f"  {'[OK]' if has_response else '[FAIL]'} 有回复 ({len(full_response)} 字)")
    if full_response:
        print(f"  回复预览: {full_response[:100]}...")

    return has_response


async def test_e2e_chat():
    """测试 10：端到端 - 闲聊"""
    print("\n" + "=" * 60)
    print("【10】端到端测试 - 闲聊")
    print("=" * 60)

    from app.chains.multi_agent import run_multi_agent

    full_response = ""
    async for chunk in run_multi_agent("你好呀"):
        if chunk.startswith("data: ") and chunk != "data: [DONE]\n\n":
            try:
                d = json.loads(chunk[6:])
                if d.get("type") == "token":
                    full_response += d["content"]
                elif d.get("type") == "error":
                    print(f"  [FAIL] 错误: {d['content']}")
                    return False
            except:
                pass

    has_response = len(full_response) > 0
    print(f"  {'[OK]' if has_response else '[FAIL]'} 有回复 ({len(full_response)} 字)")
    if full_response:
        print(f"  回复预览: {full_response[:100]}...")

    return has_response


async def main():
    print("LangGraph 优化版测试")
    print("=" * 60)

    results = {}

    # 单元测试（不需要 LLM 调用）
    results["图结构"] = test_graph_structure()
    results["状态定义"] = test_state_definition()
    results["路由节点"] = test_router()
    results["链式路由"] = test_ticket_to_knowledge_chain()
    results["兜底节点"] = test_fallback()

    # 需要 LLM 调用的测试
    results["意图分类"] = test_intent_classifier()
    results["回答生成"] = test_answer_generator()

    # 端到端测试
    results["E2E-票务"] = await test_e2e_ticket()
    results["E2E-知识库"] = await test_e2e_knowledge()
    results["E2E-闲聊"] = await test_e2e_chat()

    # 汇总
    print("\n" + "=" * 60)
    print("测试汇总")
    print("=" * 60)
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    for name, ok in results.items():
        print(f"  {'[OK]' if ok else '[FAIL]'} {name}")
    print(f"\n通过: {passed}/{total}")

    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
