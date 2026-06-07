"""构建 RAG 向量数据库

运行方式：
  .venv\Scripts\python.exe build_rag.py
"""

import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def main():
    from app.pipelines.document_pipeline import load_documents, split_documents, build_vectorstore
    from app.pipelines.rag_pipeline import build_bm25_index

    logger.info("=== 开始构建 RAG 向量数据库 ===")

    docs = load_documents()
    if not docs:
        logger.error("未找到文档，请检查 docs/rag/ 目录")
        sys.exit(1)

    chunks = split_documents(docs)
    vectorstore = build_vectorstore(chunks)
    build_bm25_index(chunks)

    logger.info("=== RAG 向量数据库构建完成 ===")
    logger.info(f"文档数: {len(docs)}, 分块数: {len(chunks)}")

    results = vectorstore.similarity_search("退票", k=2)
    logger.info(f"测试检索 '退票' 返回 {len(results)} 条结果")
    for i, doc in enumerate(results):
        logger.info(f"  [{i+1}] {doc.page_content[:80]}...")


if __name__ == "__main__":
    main()
