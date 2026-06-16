"""LangGraph 量化测试

测试指标：
1. 意图分类准确率（标注数据集）
2. 端到端成功率 + 回答质量
3. 响应延迟
"""

import asyncio
import json
import time
import sys
import io

if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import logging
logging.basicConfig(level=logging.WARNING)

# ==================== 标注数据集 ====================

INTENT_TEST_CASES = [
    # ticket 意图
    ("帮我查一下周杰伦演唱会", "ticket"),
    ("北京有什么演出", "ticket"),
    ("我想买一张德云社的票", "ticket"),
    ("帮我看看3月有什么演唱会", "ticket"),
    ("查一下我的订单状态", "ticket"),
    ("推荐一下好看的演出", "ticket"),
    ("余票还有吗", "ticket"),
    ("票价多少钱", "ticket"),

    # knowledge 意图
    ("退票政策是什么", "knowledge"),
    ("怎么退票", "knowledge"),
    ("入场需要带什么证件", "knowledge"),
    ("支持哪些支付方式", "knowledge"),
    ("会员有什么权益", "knowledge"),
    ("儿童票怎么买", "knowledge"),
    ("演出取消了怎么办", "knowledge"),
    ("取票方式有哪些", "knowledge"),

    # both 意图
    ("帮我查演唱会，顺便告诉我退票规则", "both"),
    ("我想买德云社的票，退票怎么退", "both"),
    ("查一下北京的演出，再看看儿童票政策", "both"),
    ("帮我订票，入场要带什么", "both"),

    # chat 意图
    ("你好", "chat"),
    ("谢谢", "chat"),
    ("你是谁", "chat"),
    ("今天天气怎么样", "chat"),
    ("帮我写个作文", "chat"),
]

# E2E 测试用例（带期望的关键词检查）
E2E_TEST_CASES = [
    {
        "query": "帮我查一下北京的演唱会",
        "intent": "ticket",
        "expected_keywords": ["演唱会", "北京"],
        "min_length": 50,
    },
    {
        "query": "退票政策是什么",
        "intent": "knowledge",
        "expected_keywords": ["退票"],
        "min_length": 50,
    },
    {
        "query": "入场需要带什么证件",
        "intent": "knowledge",
        "expected_keywords": ["证件", "入场"],
        "min_length": 30,
    },
    {
        "query": "你好呀",
        "intent": "chat",
        "expected_keywords": ["麦小蜜", "服务"],
        "min_length": 20,
    },
    {
        "query": "支持哪些支付方式",
        "intent": "knowledge",
        "expected_keywords": ["支付"],
        "min_length": 30,
    },
    {
        "query": "推荐一下好看的演出",
        "intent": "ticket",
        "expected_keywords": ["推荐", "演出"],
        "min_length": 50,
    },
    {
        "query": "儿童票怎么买",
        "intent": "knowledge",
        "expected_keywords": ["儿童"],
        "min_length": 30,
    },
    {
        "query": "会员有什么权益",
        "intent": "knowledge",
        "expected_keywords": ["会员"],
        "min_length": 30,
    },
    {
        "query": "帮我查演唱会和退票规则",
        "intent": "both",
        "expected_keywords": ["退票"],
        "min_length": 50,
    },
    {
        "query": "谢谢",
        "intent": "chat",
        "expected_keywords": [],
        "min_length": 10,
    },
]


# ==================== 测试函数 ====================

async def test_intent_accuracy():
    """测试 1：意图分类准确率"""
    print("=" * 60)
    print("【1】意图分类准确率测试")
    print("=" * 60)

    from app.chains.multi_agent import intent_classifier_node
    from langchain_core.messages import HumanMessage

    results = {"correct": 0, "total": 0, "by_intent": {}}
    errors = []

    for query, expected in INTENT_TEST_CASES:
        state = {"messages": [HumanMessage(content=query)]}
        result = intent_classifier_node(state)
        predicted = result.get("intent", "?")

        is_correct = predicted == expected
        results["total"] += 1
        if is_correct:
            results["correct"] += 1
        else:
            errors.append((query, expected, predicted))

        # 按意图统计
        if expected not in results["by_intent"]:
            results["by_intent"][expected] = {"correct": 0, "total": 0}
        results["by_intent"][expected]["total"] += 1
        if is_correct:
            results["by_intent"][expected]["correct"] += 1

    accuracy = results["correct"] / results["total"] * 100
    print(f"\n  总体准确率: {results['correct']}/{results['total']} = {accuracy:.1f}%")

    print(f"\n  分类准确率:")
    for intent, stats in results["by_intent"].items():
        acc = stats["correct"] / stats["total"] * 100
        print(f"    {intent}: {stats['correct']}/{stats['total']} = {acc:.1f}%")

    if errors:
        print(f"\n  错误案例:")
        for query, expected, predicted in errors:
            print(f"    「{query}」 期望={expected}, 实际={predicted}")

    return accuracy >= 80  # 80% 以上算通过


async def test_e2e_quality():
    """测试 2：端到端成功率 + 回答质量"""
    print("\n" + "=" * 60)
    print("【2】端到端成功率 + 回答质量测试")
    print("=" * 60)

    from app.chains.multi_agent import run_multi_agent

    results = {"success": 0, "total": 0, "quality_scores": []}
    failures = []

    for case in E2E_TEST_CASES:
        query = case["query"]
        full_response = ""
        has_error = False

        start_time = time.time()
        async for chunk in run_multi_agent(query):
            if chunk.startswith("data: ") and chunk != "data: [DONE]\n\n":
                try:
                    d = json.loads(chunk[6:])
                    if d.get("type") == "token":
                        full_response += d["content"]
                    elif d.get("type") == "error":
                        has_error = True
                except:
                    pass
        elapsed = time.time() - start_time

        results["total"] += 1

        # 质量检查
        checks = {
            "has_response": len(full_response) > 0,
            "no_error": not has_error,
            "min_length": len(full_response) >= case["min_length"],
            "keywords_hit": all(kw in full_response for kw in case["expected_keywords"]),
        }
        score = sum(checks.values()) / len(checks) * 100
        results["quality_scores"].append(score)

        is_success = checks["has_response"] and checks["no_error"]
        if is_success:
            results["success"] += 1

        status = "OK" if is_success else "FAIL"
        print(f"\n  [{status}] 「{query}」 ({elapsed:.1f}s)")
        print(f"    回复: {full_response[:80]}..." if len(full_response) > 80 else f"    回复: {full_response}")
        print(f"    质量: {score:.0f}% | 长度={len(full_response)} | 关键词={checks['keywords_hit']}")

        if not is_success:
            failures.append((query, checks))

    success_rate = results["success"] / results["total"] * 100
    avg_quality = sum(results["quality_scores"]) / len(results["quality_scores"])

    print(f"\n  端到端成功率: {results['success']}/{results['total']} = {success_rate:.1f}%")
    print(f"  平均回答质量: {avg_quality:.1f}%")

    if failures:
        print(f"\n  失败案例:")
        for query, checks in failures:
            failed_checks = [k for k, v in checks.items() if not v]
            print(f"    「{query}」 失败项: {failed_checks}")

    return success_rate >= 80 and avg_quality >= 70


async def test_latency():
    """测试 3：响应延迟"""
    print("\n" + "=" * 60)
    print("【3】响应延迟测试")
    print("=" * 60)

    from app.chains.multi_agent import run_multi_agent

    test_queries = [
        ("你好", "chat"),
        ("退票政策是什么", "knowledge"),
        ("帮我查北京演唱会", "ticket"),
    ]

    latencies = []

    for query, intent in test_queries:
        start = time.time()
        first_token_time = None
        full_response = ""

        async for chunk in run_multi_agent(query):
            if chunk.startswith("data: ") and chunk != "data: [DONE]\n\n":
                try:
                    d = json.loads(chunk[6:])
                    if d.get("type") == "token" and first_token_time is None:
                        first_token_time = time.time()
                        full_response += d["content"]
                    elif d.get("type") == "token":
                        full_response += d["content"]
                except:
                    pass

        total_time = time.time() - start
        ttft = (first_token_time - start) if first_token_time else None

        latencies.append({
            "query": query,
            "intent": intent,
            "total": total_time,
            "ttft": ttft,
            "response_len": len(full_response),
        })

        ttft_str = f"{ttft:.2f}s" if ttft else "N/A"
        print(f"\n  「{query}」 (intent={intent})")
        print(f"    首 token 延迟 (TTFT): {ttft_str}")
        print(f"    总耗时: {total_time:.2f}s")
        print(f"    回复长度: {len(full_response)} 字")

    avg_total = sum(l["total"] for l in latencies) / len(latencies)
    avg_ttft = sum(l["ttft"] for l in latencies if l["ttft"]) / max(1, sum(1 for l in latencies if l["ttft"]))

    print(f"\n  平均总耗时: {avg_total:.2f}s")
    print(f"  平均首 token 延迟: {avg_ttft:.2f}s")

    # 延迟基准：TTFT < 15s（多 Agent 架构需 3 次 LLM 调用），总耗时 < 45s
    return avg_ttft < 15 and avg_total < 45


# ==================== 主函数 ====================

async def main():
    print("LangGraph 量化测试")
    print("=" * 60)

    results = {}

    results["意图分类准确率"] = await test_intent_accuracy()
    results["端到端成功率+质量"] = await test_e2e_quality()
    results["响应延迟"] = await test_latency()

    # 汇总
    print("\n" + "=" * 60)
    print("量化测试汇总")
    print("=" * 60)
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    for name, ok in results.items():
        status = "[PASS]" if ok else "[FAIL]"
        print(f"  {status} {name}")
    print(f"\n通过: {passed}/{total}")


if __name__ == "__main__":
    asyncio.run(main())
