"""RAG 查询管线 - 对应原项目 QuestionAnswerAdvisor

流程：用户问题 → 混合检索（BM25 + 向量） → 融合排序 → 组装 Prompt → LLM 生成回答
"""

import logging
import pickle
from pathlib import Path
from rank_bm25 import BM25Okapi
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_openai import ChatOpenAI
from app.core.config import get_settings
from app.core.prompts import SYSTEM_PROMPT_RAG
from app.pipelines.document_pipeline import load_vectorstore, load_documents, split_documents

logger = logging.getLogger(__name__)

BM25_INDEX_PATH = Path(__file__).parent.parent.parent / "data" / "bm25_index.pkl"

RAG_PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT_RAG),
    ("human", "{question}"),
])


def build_bm25_index(chunks=None):
    """构建 BM25 索引并持久化"""
    if chunks is None:
        docs = load_documents()
        chunks = split_documents(docs)
    tokenized = [list(doc.page_content) for doc in chunks]
    bm25 = BM25Okapi(tokenized)
    BM25_INDEX_PATH.parent.mkdir(exist_ok=True)
    with open(BM25_INDEX_PATH, "wb") as f:
        pickle.dump({"bm25": bm25, "chunks": chunks}, f)
    logger.info(f"BM25 索引构建完成，共 {len(chunks)} 个分块")
    return bm25, chunks


def load_bm25_index():
    """加载 BM25 索引"""
    if not BM25_INDEX_PATH.exists():
        return build_bm25_index()
    with open(BM25_INDEX_PATH, "rb") as f:
        data = pickle.load(f)
    return data["bm25"], data["chunks"]


def hybrid_retrieve(query: str, vectorstore, bm25, chunks, k: int = 4, bm25_weight: float = 0.4):
    """混合检索：BM25 + 向量，RRF 融合排序

    Args:
        query: 用户查询
        vectorstore: ChromaDB 向量库
        bm25: BM25 索引
        chunks: 文档分块列表
        k: 返回结果数
        bm25_weight: BM25 权重（0-1），向量权重 = 1 - bm25_weight
    """
    # BM25 检索
    tokenized_query = list(query)
    bm25_scores = bm25.get_scores(tokenized_query)
    bm25_ranked = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)[:k * 2]

    # 向量检索
    vector_results = vectorstore.similarity_search_with_relevance_scores(query, k=k * 2)
    vector_ranked = [(doc, score) for doc, score in vector_results]

    # RRF 融合（Reciprocal Rank Fusion）
    rrf_scores = {}
    rrf_k = 60  # RRF 常数

    for rank, idx in enumerate(bm25_ranked):
        doc_id = id(chunks[idx])
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + bm25_weight / (rrf_k + rank + 1)

    for rank, (doc, _) in enumerate(vector_ranked):
        doc_id = id(doc)
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + (1 - bm25_weight) / (rrf_k + rank + 1)

    # 合并去重
    all_docs = {}
    for idx in bm25_ranked:
        doc = chunks[idx]
        all_docs[id(doc)] = doc
    for doc, _ in vector_ranked:
        all_docs[id(doc)] = doc

    # 按 RRF 分数排序
    ranked = sorted(all_docs.items(), key=lambda x: rrf_scores.get(x[0], 0), reverse=True)
    return [doc for _, doc in ranked[:k]]


def format_docs_with_source(docs) -> str:
    """将检索到的文档格式化为带来源的字符串"""
    parts = []
    for i, doc in enumerate(docs, 1):
        source = Path(doc.metadata.get("source", "未知文档")).stem
        parts.append(f"[文档{i}] 来源：{source}\n{doc.page_content}")
    return "\n\n".join(parts)


def get_rag_chain():
    """构建 RAG 检索问答链（混合检索）"""
    settings = get_settings()
    vectorstore = load_vectorstore()
    bm25, chunks = load_bm25_index()

    retriever = vectorstore.as_retriever(search_kwargs={"k": 4})

    llm = ChatOpenAI(
        api_key=settings.mimo_api_key,
        base_url=settings.mimo_base_url,
        model=settings.mimo_model,
        streaming=True,
    )

    chain = (
        {"context": retriever | format_docs_with_source, "question": RunnablePassthrough()}
        | RAG_PROMPT
        | llm
        | StrOutputParser()
    )

    return chain, retriever, llm


def get_hybrid_retriever():
    """获取混合检索器（供 chat_service 使用）"""
    vectorstore = load_vectorstore()
    bm25, chunks = load_bm25_index()
    return lambda query: hybrid_retrieve(query, vectorstore, bm25, chunks)
