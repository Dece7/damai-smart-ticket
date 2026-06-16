"""RAG 查询管线 - 对应原项目 QuestionAnswerAdvisor

流程：用户问题 → 混合检索（BM25 + 向量） → RRF 融合 → Reranker 精排 → 组装 Prompt → LLM 生成回答
"""

import logging
import pickle
import re
from pathlib import Path
from functools import lru_cache
from rank_bm25 import BM25Okapi
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_openai import ChatOpenAI
from app.core.config import get_settings
from app.core.prompts import SYSTEM_PROMPT_RAG, QUERY_REWRITE_PROMPT
from app.pipelines.document_pipeline import load_vectorstore, load_documents, split_documents, load_parent_chunks

logger = logging.getLogger(__name__)

BM25_INDEX_PATH = Path(__file__).parent.parent.parent / "data" / "bm25_index.pkl"


def _tokenize(text: str) -> list[str]:
    """中文分词：单字 + bigram，英文/数字整体保留"""
    segments = re.split(r'[^一-鿿a-zA-Z0-9]+', text)
    tokens = []
    for seg in segments:
        if not seg:
            continue
        if re.match(r'^[a-zA-Z0-9]+$', seg):
            tokens.append(seg)
        else:
            chars = list(seg)
            tokens.extend(chars)
            for i in range(len(chars) - 1):
                tokens.append(chars[i] + chars[i + 1])
    return tokens


def rewrite_query(question: str) -> str:
    """查询改写：将用户模糊/简短的问题改写为适合检索的完整查询

    Args:
        question: 用户原始问题

    Returns:
        改写后的查询（如果原始问题足够清晰则原样返回）
    """
    settings = get_settings()
    llm = ChatOpenAI(
        api_key=settings.mimo_api_key,
        base_url=settings.mimo_base_url,
        model=settings.mimo_model,
        temperature=0,
    )
    prompt = ChatPromptTemplate.from_messages([
        ("human", QUERY_REWRITE_PROMPT),
    ])
    chain = prompt | llm | StrOutputParser()
    try:
        rewritten = chain.invoke({"question": question}).strip()
        # 去掉可能的引号包裹
        if rewritten.startswith('"') and rewritten.endswith('"'):
            rewritten = rewritten[1:-1]
        if rewritten and rewritten != question:
            logger.info(f"查询改写: '{question}' → '{rewritten}'")
        return rewritten if rewritten else question
    except Exception as e:
        logger.warning(f"查询改写失败，使用原始问题: {e}")
        return question


@lru_cache
def get_ranker():
    """加载 FlashRank Reranker 模型（首次运行自动下载 ~30MB）"""
    from flashrank import Ranker
    settings = get_settings()
    # 使用项目目录下的 models 缓存，避免每次下载
    cache_dir = str(Path(__file__).parent.parent.parent / "models")
    Path(cache_dir).mkdir(exist_ok=True)
    logger.info(f"加载 Reranker 模型: {settings.reranker_model} (cache: {cache_dir})")
    return Ranker(model_name=settings.reranker_model, cache_dir=cache_dir)


def rerank(query: str, docs: list, top_n: int = 5) -> list:
    """Reranker 精排：粗排结果 → 交叉编码打分 → 取 Top-N

    Args:
        query: 用户查询
        docs: 粗排返回的文档列表
        top_n: 精排后返回的文档数
    """
    if not docs:
        return []
    from flashrank import RerankRequest
    ranker = get_ranker()
    passages = [{"id": i, "text": doc.page_content} for i, doc in enumerate(docs)]
    req = RerankRequest(query=query, passages=passages)
    results = ranker.rerank(req)
    ranked_indices = [r["id"] for r in results[:top_n]]
    return [docs[i] for i in ranked_indices]

RAG_PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT_RAG),
    ("human", "{question}"),
])


def build_bm25_index(chunks=None):
    """构建 BM25 索引并持久化"""
    if chunks is None:
        docs = load_documents()
        chunks = split_documents(docs)
    tokenized = [_tokenize(doc.page_content) for doc in chunks]
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


def _resolve_parents(child_docs: list, parent_dict: dict, k: int) -> list:
    """将 child chunks 映射为 parent chunks，去重后返回 Top-K

    多个 child 映射到同一 parent 时，保留 RRF 分数最高的那个 parent。
    """
    seen_parents = {}
    for doc in child_docs:
        parent_id = doc.metadata.get("parent_id")
        if parent_id and parent_id in parent_dict:
            if parent_id not in seen_parents:
                seen_parents[parent_id] = parent_dict[parent_id]
        else:
            # 没有 parent_id 或 parent_dict 为空时，直接返回 child（兼容旧模式）
            doc_id = id(doc)
            if doc_id not in seen_parents:
                seen_parents[doc_id] = doc
    return list(seen_parents.values())[:k]


def hybrid_retrieve(query: str, vectorstore, bm25, chunks, k: int = 5, bm25_weight: float = 0.9, use_reranker: bool = False, original_query: str = None, parent_dict: dict = None):
    """混合检索：BM25 + 向量，RRF 融合，Reranker 精排

    支持 Parent-Child 模式：用 child chunks 检索，返回 parent chunks 给 LLM。

    Args:
        query: 用户查询
        vectorstore: ChromaDB 向量库
        bm25: BM25 索引
        chunks: 文档分块列表（child chunks）
        k: 最终返回结果数
        bm25_weight: BM25 权重（0-1），向量权重 = 1 - bm25_weight
        use_reranker: 是否启用 Reranker 精排
        parent_dict: parent chunks 字典，启用 Parent-Child 模式
    """
    settings = get_settings()
    candidate_count = settings.reranker_candidate_count if use_reranker else k

    # BM25 检索
    tokenized_query = _tokenize(query)
    bm25_scores = bm25.get_scores(tokenized_query)
    bm25_ranked = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)[:candidate_count]

    # 向量检索
    vector_results = vectorstore.similarity_search_with_relevance_scores(query, k=candidate_count)
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
    coarse_results = [doc for _, doc in ranked[:candidate_count]]

    # Reranker 精排（用原始查询，不用改写后的查询）
    if use_reranker and len(coarse_results) > k:
        try:
            rerank_query = original_query if original_query else query
            final_results = rerank(rerank_query, coarse_results, top_n=k)
            logger.info(f"Reranker 精排: {len(coarse_results)} → {len(final_results)}")
            # Reranker 排序后再映射 parent
            if parent_dict:
                return _resolve_parents(final_results, parent_dict, k)
            return final_results
        except Exception as e:
            logger.warning(f"Reranker 精排失败，回退到粗排结果: {e}")

    # Parent-Child 映射：child → parent
    if parent_dict:
        return _resolve_parents(coarse_results, parent_dict, k)

    return coarse_results[:k]


def format_docs_with_source(docs) -> str:
    """将检索到的文档格式化为带来源的字符串"""
    parts = []
    for i, doc in enumerate(docs, 1):
        source = Path(doc.metadata.get("source", "未知文档")).stem
        parts.append(f"[文档{i}] 来源：{source}\n{doc.page_content}")
    return "\n\n".join(parts)


def get_rag_chain():
    """构建 RAG 问答链（不包含检索，由调用方提供 context）"""
    settings = get_settings()

    llm = ChatOpenAI(
        api_key=settings.mimo_api_key,
        base_url=settings.mimo_base_url,
        model=settings.mimo_model,
        streaming=True,
    )

    # 链只负责 Prompt + LLM 生成，context 由外部传入
    chain = RAG_PROMPT | llm | StrOutputParser()

    return chain, llm


def get_hybrid_retriever(use_reranker: bool = False):
    """获取混合检索器（供 chat_service 和 tools 使用）"""
    vectorstore = load_vectorstore()
    bm25, chunks = load_bm25_index()
    parent_dict = load_parent_chunks()  # 可能为 None（兼容旧模式）
    def _retrieve(query, original_query=None):
        return hybrid_retrieve(query, vectorstore, bm25, chunks, use_reranker=use_reranker, original_query=original_query, parent_dict=parent_dict)
    return _retrieve
