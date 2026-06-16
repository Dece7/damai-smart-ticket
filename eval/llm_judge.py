"""LLM Judge - 回答质量评估

用 Mimo 对 RAG 生成的回答做三维度评分：
- 相关性（Relevance）：回答是否回答了用户的问题
- 忠实度（Faithfulness）：回答是否基于检索文档，有无编造
- 完整性（Completeness）：回答是否覆盖了所有相关信息

用法：
  .venv\Scripts\python.exe eval\llm_judge.py
"""

import sys
import json
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.pipelines.rag_pipeline import hybrid_retrieve, load_bm25_index, load_vectorstore, get_rag_chain, rewrite_query
from app.pipelines.document_pipeline import load_parent_chunks
from app.core.config import get_settings
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

JUDGE_PROMPT = """你是一个 RAG 回答质量评估专家。请从以下三个维度对回答进行评分。

评分维度（每项 1-5 分）：
1. 相关性（Relevance）：回答是否回答了用户的问题
   - 5分：完全回答了问题
   - 3分：部分回答了问题
   - 1分：完全答非所问

2. 忠实度（Faithfulness）：回答是否基于提供的检索文档，有无编造
   - 5分：完全基于文档，没有编造
   - 3分：大部分基于文档，有少量推测
   - 1分：严重编造，文档中没有的信息

3. 完整性（Completeness）：回答是否覆盖了所有相关信息
   - 5分：覆盖了所有关键信息
   - 3分：覆盖了主要信息，遗漏了细节
   - 1分：严重遗漏

请只输出 JSON 格式，不要添加其他内容：
{{"relevance": 5, "faithfulness": 5, "completeness": 4, "reason": "简要说明"}}

用户问题: {question}

检索文档:
{context}

生成回答: {answer}"""


def load_dataset(path: str = None) -> list[dict]:
    if path is None:
        path = Path(__file__).parent / "eval_dataset.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


async def judge_single(question: str, context: str, answer: str, llm) -> dict:
    """对单个回答做 LLM Judge 评分"""
    prompt = JUDGE_PROMPT.format(
        question=question,
        context=context[:1500],  # 截断避免超 token
        answer=answer[:500],
    )
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        content = response.content.strip()
        # 提取 JSON
        if "{" in content:
            json_str = content[content.index("{"):content.rindex("}") + 1]
            return json.loads(json_str)
    except Exception as e:
        pass
    return {"relevance": 0, "faithfulness": 0, "completeness": 0, "reason": "评分失败"}


async def evaluate_judge(dataset: list[dict], sample_size: int = 10) -> dict:
    """对数据集做 LLM Judge 评估

    Args:
        dataset: 评估数据集
        sample_size: 采样数量（LLM Judge 成本较高，只采样评估）
    """
    settings = get_settings()
    llm = ChatOpenAI(
        api_key=settings.mimo_api_key,
        base_url=settings.mimo_base_url,
        model=settings.mimo_model,
        temperature=0,
    )

    vectorstore = load_vectorstore()
    bm25, chunks = load_bm25_index()
    parent_dict = load_parent_chunks()
    rag_chain, _ = get_rag_chain()

    # 采样
    import random
    sample = random.sample(dataset, min(sample_size, len(dataset)))

    results = []
    for i, item in enumerate(sample):
        question = item["question"]
        print(f"  [{i+1}/{len(sample)}] {question}")

        # 检索
        docs = hybrid_retrieve(question, vectorstore, bm25, chunks, k=5, parent_dict=parent_dict)
        context = "\n\n".join(d.page_content for d in docs)

        # 生成回答
        try:
            answer = rag_chain.invoke({"context": context, "question": question})
        except Exception as e:
            answer = f"生成失败: {e}"

        # LLM Judge 评分
        scores = await judge_single(question, context, answer, llm)

        results.append({
            "id": item["id"],
            "question": question,
            "answer": answer[:200],
            "scores": scores,
        })

    # 汇总
    valid = [r for r in results if r["scores"]["relevance"] > 0]
    if valid:
        avg_relevance = sum(r["scores"]["relevance"] for r in valid) / len(valid)
        avg_faithfulness = sum(r["scores"]["faithfulness"] for r in valid) / len(valid)
        avg_completeness = sum(r["scores"]["completeness"] for r in valid) / len(valid)
    else:
        avg_relevance = avg_faithfulness = avg_completeness = 0

    return {
        "sample_size": len(sample),
        "evaluated": len(valid),
        "avg_relevance": round(avg_relevance, 2),
        "avg_faithfulness": round(avg_faithfulness, 2),
        "avg_completeness": round(avg_completeness, 2),
        "avg_overall": round((avg_relevance + avg_faithfulness + avg_completeness) / 3, 2),
        "details": results,
    }


async def main():
    print("LLM Judge 评估")
    print("=" * 50)

    dataset = load_dataset()
    print(f"数据集: {len(dataset)} 条，采样 10 条评估")
    print()

    result = await evaluate_judge(dataset, sample_size=10)

    print()
    print("=" * 50)
    print("  LLM Judge 评估结果")
    print("=" * 50)
    print(f"  评估样本数:   {result['evaluated']}")
    print(f"  平均相关性:   {result['avg_relevance']} / 5")
    print(f"  平均忠实度:   {result['avg_faithfulness']} / 5")
    print(f"  平均完整性:   {result['avg_completeness']} / 5")
    print(f"  综合评分:     {result['avg_overall']} / 5")
    print("=" * 50)

    # 低分用例
    low_scores = [r for r in result["details"]
                  if r["scores"]["relevance"] > 0 and r["scores"]["faithfulness"] < 4]
    if low_scores:
        print(f"\n  忠实度 < 4 的用例:")
        for r in low_scores:
            s = r["scores"]
            print(f"    [{r['id']}] {r['question']}")
            print(f"         相关={s['relevance']} 忠实={s['faithfulness']} 完整={s['completeness']}")
            print(f"         原因: {s.get('reason', 'N/A')}")

    # 保存结果
    output_path = Path(__file__).parent / "results" / "llm_judge.json"
    output_path.parent.mkdir(exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n  结果已保存: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
