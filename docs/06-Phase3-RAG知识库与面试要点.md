# Phase 3：RAG 知识库 — 知识点与面试要点

> 文档加载、分块、Embedding、向量检索、RAG 问答链的技术细节和面试准备。

---

## 做了什么

将购票规则文档（Markdown）加载、分块、向量化存入 ChromaDB，用户提问时先检索相关文档片段，再让 LLM 基于文档生成回答（而非瞎编）。

---

## 核心知识点

### 1. RAG 是什么（Retrieval-Augmented Generation）

```
用户问题: "怎么退票？"
       │
       ▼
┌──────────────┐
│  1. 检索      │  从知识库中找到与问题相关的文档片段
│  (Retrieval) │
└──────┬───────┘
       ▼
┌──────────────┐
│  2. 增强      │  将检索到的文档片段注入到 Prompt 中
│ (Augmented)  │
└──────┬───────┘
       ▼
┌──────────────┐
│  3. 生成      │  LLM 基于增强后的 Prompt 生成回答
│ (Generation) │
└──────────────┘
       │
       ▼
回答: "退票政策如下：1. 查看演出详情页..."
```

**面试要点：**
- RAG 解决 LLM 的两大问题：**知识过时**（训练数据有截止日期）和**幻觉**（编造不存在的信息）
- RAG 让 LLM 基于**你提供的文档**回答，而非依赖训练数据
- RAG 是企业级 AI 应用的**核心架构模式**

**面试问：** RAG 和微调（Fine-tuning）的区别？
**答：** RAG 是在推理时注入知识，成本低、更新快、可追溯来源；微调是修改模型参数，成本高、需要训练数据、适合改变模型行为模式。大多数场景优先用 RAG。

---

### 2. 文档加载（Document Loading）

```python
from langchain_community.document_loaders import DirectoryLoader, TextLoader

loader = DirectoryLoader(
    "docs/rag/",
    glob="**/*.md",
    loader_cls=TextLoader,
    loader_kwargs={"encoding": "utf-8"},
)
documents = loader.load()
```

**面试要点：**
- LangChain 支持多种文档格式：PDF、Word、Markdown、HTML、CSV 等
- 每个文档是一个 `Document` 对象，包含 `page_content`（文本）和 `metadata`（元数据）
- `DirectoryLoader` 可以批量加载目录下的文件

---

### 3. 文档分块（Text Splitting）

```python
from langchain_text_splitters import RecursiveCharacterTextSplitter, MarkdownHeaderTextSplitter

# 第一步：按 Markdown 标题切分（Parent-Child 模式）
md_splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=[("#", "h1"), ("##", "h2"), ("###", "h3")],
    strip_headers=False,
)

# 第二步：对超大块做二次切分
splitter = RecursiveCharacterTextSplitter(
    chunk_size=800,      # Parent 块最大字符数
    chunk_overlap=150,   # 分块之间的重叠字符数
    separators=["\n\n", "\n", "。", "！", "？", ".", "!", "?"],
)
# Parent-Child 模式：child_chunk_size=400, child_chunk_overlap=80
```

**面试要点：**
- 为什么要分块？LLM 的上下文窗口有限，不能把整个文档塞进去
- 分块太大 → 检索不精确；分块太小 → 丢失上下文
- `chunk_overlap` 确保分块边界处的语义不丢失
- `separators` 按优先级尝试在自然边界处分割（段落 > 句子 > 词）

**面试问：** chunk_size 和 chunk_overlap 怎么选？
**答：** chunk_size 一般 300-1000，取决于文档结构；chunk_overlap 一般 10-20% 的 chunk_size。需要根据实际检索效果调优。

---

### 4. Embedding（向量化）

```python
# 方式 1：使用远程 API（DeepSeek/OpenAI）
embeddings = OpenAIEmbeddings(api_key="...", model="text-embedding-v3")

# 方式 2：使用本地模型（ChromaDB 默认）
# ChromaDB 内置 all-MiniLM-L6-v2 模型，首次需下载 ~80MB

# 方式 3：使用哈希函数（demo 用，精度低但无需模型）
class HashEmbeddingFunction:
    def embed_documents(self, texts): ...
    def embed_query(self, text): ...
```

**面试要点：**
- Embedding 将文本转为**高维向量**（如 384 维、1024 维）
- 语义相似的文本，向量距离近；语义不同的文本，向量距离远
- 常用相似度算法：余弦相似度、欧氏距离
- Embedding 模型选择：中文场景推荐 BGE-M3、M3E；英文推荐 OpenAI text-embedding-3

**面试问：** Embedding 和 one-hot 编码的区别？
**答：** one-hot 是稀疏高维、无语义信息；Embedding 是稠密低维、包含语义信息。"猫"和"狗"的 Embedding 向量很接近，但 one-hot 完全正交。

---

### 5. 向量数据库（Vector Store）

```python
import chromadb
from langchain_chroma import Chroma

client = chromadb.PersistentClient(path="./chroma_db")

vectorstore = Chroma.from_documents(
    documents=chunks,
    embedding=embedding_fn,
    client=client,
    collection_name="damai_rag",
)
```

**面试要点：**
- 向量数据库专门存储和检索向量，支持高效的相似度搜索
- 常见向量数据库：ChromaDB（轻量）、Milvus（生产级）、Pinecone（托管）、Pgvector（PostgreSQL 扩展）
- ChromaDB 适合开发和小规模场景，Milvus 适合大规模生产环境
- `PersistentClient` 数据持久化到磁盘，重启不丢失

**面试问：** 为什么不用 MySQL 存向量？
**答：** MySQL 的 B-tree 索引不适合高维向量的相似度搜索。向量数据库使用 ANN（近似最近邻）算法，检索速度比暴力搜索快几个数量级。

---

### 6. RAG 检索问答链（LangChain LCEL）

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough

prompt = ChatPromptTemplate.from_messages([
    ("system", "根据上下文回答问题：\n{context}"),
    ("human", "{question}"),
])

chain = (
    {"context": retriever | format_docs, "question": RunnablePassthrough()}
    | prompt
    | llm
    | StrOutputParser()
)

answer = chain.invoke("怎么退票？")
```

**面试要点：**
- LCEL（LangChain Expression Language）用 `|` 管道符连接组件
- `retriever | format_docs`：检索 → 格式化为字符串
- `RunnablePassthrough`：透传原始输入
- 整个链：输入 → 检索上下文 → 组装 Prompt → LLM 生成 → 解析输出

---

## 完整 RAG 流程代码模式

```python
# 1. 加载文档
documents = DirectoryLoader("docs/", glob="**/*.md").load()

# 2. 分块（Markdown 标题感知 + Parent-Child 模式）
chunks = split_documents_with_parents(documents)  # parent: 800/150, child: 400/80

# 3. 存入向量数据库
vectorstore = Chroma.from_documents(chunks, embedding_fn, collection_name="my_rag")

# 4. 创建检索器
retriever = vectorstore.as_retriever(search_kwargs={"k": 4})

# 5. 构建 RAG 链
chain = {"context": retriever | format_docs, "question": RunnablePassthrough()} | prompt | llm | StrOutputParser()

# 6. 查询
answer = chain.invoke("用户问题")
```

---

## 面试高频问题

| 问题 | 回答要点 |
|------|---------|
| 什么是 RAG？ | 检索增强生成：先检索相关文档，再让 LLM 基于文档回答 |
| 为什么需要 RAG？ | 解决 LLM 知识过时和幻觉问题，让回答可追溯 |
| RAG vs 微调？ | RAG 成本低、更新快、可追溯；微调适合改变模型行为 |
| 文档分块策略？ | chunk_size 300-1000，overlap 10-20%，按自然边界分割 |
| 怎么选择 Embedding 模型？ | 中文推荐 BGE-M3，英文推荐 OpenAI text-embedding-3 |
| 向量数据库选型？ | 开发用 ChromaDB，生产用 Milvus/Pinecone，已有 PG 用 Pgvector |
| 检索结果不好怎么优化？ | 调 chunk_size、换 Embedding 模型、加 Reranker 重排序、混合检索 |

---

## 与原项目（Spring AI）对比

| 原项目 (Spring AI) | Python 版 (LangChain) | 知识点 |
|-------------------|----------------------|--------|
| `MarkdownDocumentReader` | `DirectoryLoader + TextLoader` | 文档加载 |
| `SimpleVectorStore` | `ChromaDB + Chroma` | 向量数据库 |
| `OpenAiEmbeddingModel` | `OpenAIEmbeddings` / 自定义 | Embedding |
| `QuestionAnswerAdvisor` | LCEL RAG Chain | 检索问答 |
| `SearchRequest(topK=8)` | `search_kwargs={"k": 4}` | 检索参数 |
| `similarityThreshold(0.3)` | 可配置 | 相似度阈值 |

---

## 引用溯源（Citation）

RAG 回答标注信息来源，让用户可以验证回答的准确性。

### 实现方式

```python
# 1. 检索时保留文档元数据
docs = retriever.invoke(question)

# 2. 格式化时附带来源
def format_docs_with_source(docs):
    parts = []
    for doc in docs:
        source = Path(doc.metadata["source"]).stem
        parts.append(f"[文档] 来源：{source}\n{doc.page_content}")
    return "\n\n".join(parts)

# 3. Prompt 中要求 LLM 标注来源
prompt = "...在回答末尾标注信息来源，格式为：【来源：文档名】"
```

**面试要点：**
- 引用溯源是 RAG 应用的**核心差异化**，让回答可验证
- 实现方式：检索时保留 metadata → Prompt 要求标注来源 → 前端展示来源卡片
- 生产环境还可以做：段落级引用、高亮原文、点击跳转原文

---

## 混合检索（BM25 + 向量）

### 为什么需要混合检索

| 检索方式 | 擅长 | 不擅长 |
|----------|------|--------|
| 向量检索 | 语义理解（"退款"≈"退票"） | 精确关键词匹配 |
| BM25 | 关键词精确匹配（"手续费"） | 同义词理解 |

单独用任何一种都有盲区，混合互补效果最好。

### 实现方案

```python
from rank_bm25 import BM25Okapi

# 1. 构建 BM25 索引（与向量库同步构建）
tokenized = [list(doc.page_content) for doc in chunks]  # 字符级分词
bm25 = BM25Okapi(tokenized)

# 2. 混合检索 + RRF 融合排序
def hybrid_retrieve(query, vectorstore, bm25, chunks, k=4, bm25_weight=0.9):
    # BM25 检索
    bm25_scores = bm25.get_scores(list(query))
    bm25_ranked = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)

    # 向量检索
    vector_results = vectorstore.similarity_search_with_relevance_scores(query, k=k*2)

    # RRF 融合
    rrf_scores = {}
    for rank, idx in enumerate(bm25_ranked):
        rrf_scores[id(chunks[idx])] += bm25_weight / (60 + rank + 1)
    for rank, (doc, _) in enumerate(vector_results):
        rrf_scores[id(doc)] += (1 - bm25_weight) / (60 + rank + 1)

    # 按 RRF 分数排序返回 Top-K
    return sorted(all_docs, key=lambda d: rrf_scores.get(id(d), 0), reverse=True)[:k]
```

### RRF（Reciprocal Rank Fusion）公式

```
score(doc) = Σ weight_i / (k + rank_i)

其中：
- weight_i：第 i 个检索器的权重
- k=60：常数，防止排名靠前的文档分数过高
- rank_i：文档在第 i 个检索器中的排名
```

### 面试高频问题

| 问题 | 回答要点 |
|------|---------|
| 为什么需要混合检索？ | 向量擅长语义，BM25 擅长关键词，互补覆盖更多场景 |
| RRF 是什么？ | 基于排名的融合算法，不依赖原始分数，鲁棒性好 |
| BM25 的分词方式？ | 中文按字符级（`list(text)`），生产环境用 jieba |
| 权重怎么调？ | BM25 0.3-0.5，根据场景调优，精确匹配场景提高 BM25 权重 |
| BM25 索引怎么持久化？ | pickle 序列化，随向量库同步更新 |

### 与原项目对比

| 原项目 (Spring AI) | Python 版 |
|-------------------|-----------|
| SimpleVectorStore（纯向量） | BM25 + 向量混合检索 |
| 无融合排序 | RRF 融合排序 |
| 内存存储，重启丢失 | ChromaDB 持久化 + BM25 pickle 持久化 |

**面试问：** 怎么让 RAG 回答更可信？
**答：** 引用溯源。每个回答标注来源文档和段落，用户可以点击验证。同时可以做置信度评分，低于阈值时提示"信息可能不准确"。
