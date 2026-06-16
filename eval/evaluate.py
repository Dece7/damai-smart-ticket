"""RAG 评估脚本

用法：
  .venv\Scripts\python.exe eval\evaluate.py [--reranker] [--rewrite] [--compare]

评估指标：
  - Recall@K（来源命中率）：答案来源是否在 Top-K 结果中
  - Precision@K（精确率）：Top-K 结果中有多少是相关的
  - MRR（平均倒数排名）：第一个相关结果排在第几位
  - 关键词命中率：检索结果是否包含预期关键词
  - 端到端延迟
"""

import sys
import json
import time
import argparse
from pathlib import Path

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.pipelines.rag_pipeline import get_hybrid_retriever, hybrid_retrieve, load_bm25_index, load_vectorstore, rewrite_query
from app.pipelines.document_pipeline import load_parent_chunks


def load_dataset(path: str = None) -> list[dict]:
    """加载评估数据集"""
    if path is None:
        path = Path(__file__).parent / "eval_dataset.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def evaluate_retrieval(dataset: list[dict], use_reranker: bool = True, use_rewrite: bool = False, k: int = 5) -> dict:
    """评估检索质量

    Args:
        dataset: 评估数据集
        use_reranker: 是否使用 Reranker
        use_rewrite: 是否使用查询改写
        k: Top-K
    """
    vectorstore = load_vectorstore()
    bm25, chunks = load_bm25_index()
    parent_dict = load_parent_chunks()  # Parent-Child 模式

    total = len(dataset)
    source_hits = 0
    keyword_hits = 0
    precision_sum = 0.0
    mrr_sum = 0.0
    latencies = []

    details = []

    for item in dataset:
        question = item["question"]
        expected_sources = item.get("expected_sources", [])
        expected_keywords = item.get("expected_keywords", [])

        # 查询改写
        query = question
        if use_rewrite:
            query = rewrite_query(question)

        # 检索
        start = time.time()
        docs = hybrid_retrieve(
            query, vectorstore, bm25, chunks,
            k=k, use_reranker=use_reranker,
            parent_dict=parent_dict,
        )
        latency = time.time() - start
        latencies.append(latency)

        # 检查来源命中（Recall）— 仅对有 expected_sources 的用例
        retrieved_sources = []
        seen = set()
        for doc in docs:
            source = Path(doc.metadata.get("source", "")).stem
            if source not in seen:
                seen.add(source)
                retrieved_sources.append(source)

        if expected_sources:
            source_hit = any(
                any(es in rs for rs in retrieved_sources)
                for es in expected_sources
            )
            if source_hit:
                source_hits += 1

            # Precision：Top-K 中有多少是相关的
            relevant_count = sum(
                1 for rs in retrieved_sources
                if any(es in rs for es in expected_sources)
            )
            precision = relevant_count / len(retrieved_sources) if retrieved_sources else 0.0
            precision_sum += precision

            # MRR：第一个相关结果排在第几位
            first_rank = 0
            for rank, rs in enumerate(retrieved_sources, 1):
                if any(es in rs for es in expected_sources):
                    first_rank = rank
                    break
            mrr = 1.0 / first_rank if first_rank > 0 else 0.0
            mrr_sum += mrr
        else:
            # 无 expected_sources 的用例（ticket/both），只检查关键词
            source_hit = True  # 不评估来源
            source_hits += 1
            precision = 1.0
            mrr = 1.0
            precision_sum += precision
            mrr_sum += mrr

        # 检查关键词命中
        retrieved_text = " ".join(doc.page_content for doc in docs)
        keyword_hit = any(kw in retrieved_text for kw in expected_keywords)
        if keyword_hit:
            keyword_hits += 1

        detail = {
            "id": item["id"],
            "question": question,
            "source_hit": source_hit,
            "keyword_hit": keyword_hit,
            "precision": round(precision, 2),
            "mrr": round(mrr, 2),
            "first_rank": first_rank,
            "latency": round(latency * 1000),
            "retrieved_sources": retrieved_sources,
            "expected_sources": expected_sources,
        }
        if use_rewrite and query != question:
            detail["rewritten"] = query
        details.append(detail)

    return {
        "total": total,
        "recall_at_k": round(source_hits / total * 100, 1),
        "precision_at_k": round(precision_sum / total * 100, 1),
        "mrr": round(mrr_sum / total, 3),
        "keyword_hit_rate": round(keyword_hits / total * 100, 1),
        "avg_latency_ms": round(sum(latencies) / len(latencies) * 1000),
        "max_latency_ms": round(max(latencies) * 1000),
        "min_latency_ms": round(min(latencies) * 1000),
        "use_reranker": use_reranker,
        "use_rewrite": use_rewrite,
        "details": details,
    }


def print_report(result: dict):
    """打印评估报告"""
    modes = []
    if result.get("use_rewrite"):
        modes.append("查询改写")
    if result.get("use_reranker"):
        modes.append("Reranker")
    mode = " + ".join(modes) if modes else "基础模式"

    print(f"\n{'='*55}")
    print(f"  评估报告 ({mode})")
    print(f"{'='*55}")
    print(f"  测试用例数:       {result['total']}")
    print(f"  Recall@5 (召回):  {result.get('recall_at_k', result.get('source_hit_rate', 0))}%")
    print(f"  Precision@5 (精确): {result.get('precision_at_k', 0)}%")
    print(f"  MRR (平均倒数排名): {result.get('mrr', 0)}")
    print(f"  关键词命中率:     {result['keyword_hit_rate']}%")
    print(f"  平均延迟:         {result['avg_latency_ms']}ms")
    print(f"  最大延迟:         {result['max_latency_ms']}ms")
    print(f"  最小延迟:         {result['min_latency_ms']}ms")
    print(f"{'='*55}")

    # 打印未命中的用例
    missed = [d for d in result["details"] if not d["source_hit"]]
    if missed:
        print(f"\n  未命中来源的用例 ({len(missed)}):")
        for d in missed[:10]:
            print(f"    [{d['id']}] {d['question']}")
            if "rewritten" in d:
                print(f"         改写: {d['rewritten']}")
            print(f"         期望: {d['expected_sources']}")
            print(f"         实际: {d['retrieved_sources']}")

    # Precision 分布
    precisions = [d.get("precision", 0) for d in result["details"]]
    low_precision = [d for d in result["details"] if d.get("precision", 0) < 0.5 and d["source_hit"]]
    if low_precision:
        print(f"\n  Precision < 50% 的用例 ({len(low_precision)}):")
        for d in low_precision[:5]:
            print(f"    [{d['id']}] {d['question']}  Precision={d['precision']}  排名={d.get('first_rank', '?')}")


def print_comparison(label_a: str, result_a: dict, label_b: str, result_b: dict):
    """打印对比报告"""
    print(f"\n{'='*65}")
    print(f"  对比摘要")
    print(f"{'='*65}")
    print(f"  {'指标':<18} {label_a:>12} {label_b:>12} {'差异':>8}")
    print(f"  {'-'*55}")
    print(f"  {'Recall@5':<18} {result_a.get('recall_at_k', result_a.get('source_hit_rate',0)):>10}% {result_b.get('recall_at_k', result_b.get('source_hit_rate',0)):>10}% {result_b.get('recall_at_k',0) - result_a.get('recall_at_k',0):>+7.1f}%")
    print(f"  {'Precision@5':<18} {result_a.get('precision_at_k',0):>10}% {result_b.get('precision_at_k',0):>10}% {result_b.get('precision_at_k',0) - result_a.get('precision_at_k',0):>+7.1f}%")
    print(f"  {'MRR':<18} {result_a.get('mrr',0):>11} {result_b.get('mrr',0):>11} {result_b.get('mrr',0) - result_a.get('mrr',0):>+8.3f}")
    print(f"  {'关键词命中率':<16} {result_a['keyword_hit_rate']:>10}% {result_b['keyword_hit_rate']:>10}% {result_b['keyword_hit_rate'] - result_a['keyword_hit_rate']:>+7.1f}%")
    print(f"  {'平均延迟':<18} {result_a['avg_latency_ms']:>10}ms {result_b['avg_latency_ms']:>10}ms {result_b['avg_latency_ms'] - result_a['avg_latency_ms']:>+7}ms")
    print(f"  {'='*55}")


def main():
    parser = argparse.ArgumentParser(description="RAG 评估脚本")
    parser.add_argument("--no-reranker", action="store_true", default=True, help="不使用 Reranker（默认关闭，英文 Reranker 对中文效果差）")
    parser.add_argument("--reranker", action="store_true", help="启用 Reranker")
    parser.add_argument("--rewrite", action="store_true", help="使用查询改写")
    parser.add_argument("--compare", action="store_true", help="对比模式")
    parser.add_argument("--output", type=str, help="输出 JSON 文件路径")
    args = parser.parse_args()

    dataset = load_dataset()
    print(f"加载了 {len(dataset)} 条测试用例")

    if args.compare:
        # 对比模式：有/无查询改写
        print("\n[1/2] 评估无查询改写...")
        result_without = evaluate_retrieval(dataset, use_reranker=args.reranker, use_rewrite=False)
        print_report(result_without)

        print("\n[2/2] 评估有查询改写...")
        result_with = evaluate_retrieval(dataset, use_reranker=args.reranker, use_rewrite=True)
        print_report(result_with)

        print_comparison("无改写", result_without, "有改写", result_with)

        if args.output:
            output = {
                "without_rewrite": result_without,
                "with_rewrite": result_with,
            }
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(output, f, ensure_ascii=False, indent=2)
            print(f"\n结果已保存到: {args.output}")
    else:
        # 单次评估
        result = evaluate_retrieval(
            dataset,
            use_reranker=args.reranker,
            use_rewrite=args.rewrite,
        )
        print_report(result)

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"\n结果已保存到: {args.output}")


if __name__ == "__main__":
    main()
