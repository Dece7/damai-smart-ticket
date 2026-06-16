"""RAG 召回质量测试 - Parent-Child 模式

验证：child 检索精准 → parent 返回完整
"""

import sys
import logging

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


def main():
    from app.pipelines.document_pipeline import (
        load_documents, split_documents_with_parents,
        load_parent_chunks,
    )
    from app.pipelines.rag_pipeline import hybrid_retrieve, load_bm25_index, load_vectorstore

    # --- 1. 验证分块质量 ---
    print("=" * 60)
    print("【1】Parent-Child 分块质量检查")
    print("=" * 60)

    docs = load_documents()
    child_chunks, parent_dict = split_documents_with_parents(docs)
    print(f"文档数: {len(docs)}")
    print(f"Parent chunks: {len(parent_dict)}")
    print(f"Child chunks: {len(child_chunks)}")

    # 检查 parent_id 映射
    children_with_parent = sum(1 for c in child_chunks if c.metadata.get("parent_id"))
    print(f"有 parent_id 的 child: {children_with_parent}/{len(child_chunks)}")

    # child 大小分布
    child_sizes = [len(c.page_content) for c in child_chunks]
    print(f"Child 大小: 最小={min(child_sizes)}, 最大={max(child_sizes)}, 平均={sum(child_sizes)//len(child_sizes)}")

    # parent 大小分布
    parent_sizes = [len(p.page_content) for p in parent_dict.values()]
    print(f"Parent 大小: 最小={min(parent_sizes)}, 最大={max(parent_sizes)}, 平均={sum(parent_sizes)//len(parent_sizes)}")

    # 打印一个 parent-child 样例
    print("\n--- Parent-Child 样例 ---")
    sample_parent_id = child_chunks[0].metadata.get("parent_id")
    if sample_parent_id and sample_parent_id in parent_dict:
        parent = parent_dict[sample_parent_id]
        print(f"Parent ({len(parent.page_content)}字): {parent.page_content[:150]}...")
        sample_children = [c for c in child_chunks if c.metadata.get("parent_id") == sample_parent_id]
        print(f"  → 包含 {len(sample_children)} 个 child:")
        for i, c in enumerate(sample_children):
            print(f"    Child {i+1} ({len(c.page_content)}字): {c.page_content[:80]}...")

    # --- 2. 混合检索 + Parent 映射测试 ---
    print("\n" + "=" * 60)
    print("【2】混合检索测试（child 检索 → parent 返回）")
    print("=" * 60)

    vectorstore = load_vectorstore()
    bm25, bm25_chunks = load_bm25_index()
    loaded_parent_dict = load_parent_chunks()

    test_queries = [
        "退票需要多久到账",
        "德云社门票能转让吗",
        "残疾人有什么服务",
        "怎么订票",
        "儿童票多少钱",
        "会员有什么权益",
        "支付方式有哪些",
        "入场需要带什么证件",
        "演出取消了怎么办",
        "怎么选座位",
    ]

    for query in test_queries:
        results = hybrid_retrieve(query, vectorstore, bm25, bm25_chunks, k=3, parent_dict=loaded_parent_dict)
        print(f"\n查询: 「{query}」")
        for i, doc in enumerate(results):
            first_line = doc.page_content.split("\n")[0]
            source = doc.metadata.get("source", "?").split("\\")[-1]
            has_parent = "parent_id" in doc.metadata
            size = len(doc.page_content)
            print(f"  [{i+1}] ({size}字) {first_line}  ({source})")

    # --- 3. 对比：child vs parent 返回内容 ---
    print("\n" + "=" * 60)
    print("【3】对比：child 检索 vs parent 返回")
    print("=" * 60)

    compare_query = "退票需要多久到账"
    # 不带 parent_dict（返回 child）
    child_results = hybrid_retrieve(compare_query, vectorstore, bm25, bm25_chunks, k=3, parent_dict=None)
    # 带 parent_dict（返回 parent）
    parent_results = hybrid_retrieve(compare_query, vectorstore, bm25, bm25_chunks, k=3, parent_dict=loaded_parent_dict)

    print(f"\n查询: 「{compare_query}」")
    print(f"\n  [Child 模式] 返回 {len(child_results)} 个 child chunks:")
    for i, doc in enumerate(child_results):
        print(f"    [{i+1}] ({len(doc.page_content)}字) {doc.page_content[:100]}...")

    print(f"\n  [Parent 模式] 返回 {len(parent_results)} 个 parent chunks:")
    for i, doc in enumerate(parent_results):
        print(f"    [{i+1}] ({len(doc.page_content)}字) {doc.page_content[:100]}...")

    # --- 4. 边界测试 ---
    print("\n" + "=" * 60)
    print("【4】边界测试")
    print("=" * 60)

    empty_children = sum(1 for c in child_chunks if not c.page_content.strip())
    empty_parents = sum(1 for p in parent_dict.values() if not p.page_content.strip())
    print(f"空 child chunks: {empty_children}")
    print(f"空 parent chunks: {empty_parents}")

    # parent 1:N 关系
    parent_id_counts = {}
    for c in child_chunks:
        pid = c.metadata.get("parent_id")
        if pid:
            parent_id_counts[pid] = parent_id_counts.get(pid, 0) + 1
    max_children = max(parent_id_counts.values()) if parent_id_counts else 0
    min_children = min(parent_id_counts.values()) if parent_id_counts else 0
    avg_children = sum(parent_id_counts.values()) // len(parent_id_counts) if parent_id_counts else 0
    print(f"Parent-Child 关系: 最多{max_children}个child, 最少{min_children}个, 平均{avg_children}个")

    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
