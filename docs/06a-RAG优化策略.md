# RAG 优化策略 — 知识点与面试要点

> RAG 优化分为**检索优化**和**生成优化**两大类。检索是基础，检索不到正确文档，生成再好也是编造。

---

## RAG 全景图

```
用户查询 ──→ 【检索优化】 ──→ 【生成优化】 ──→ 最终回答

检索优化：
  预检索：查询改写 / HyDE / 多路召回
  索引构建：Chunk 切分 / Embedding / 元数据增强
  检索执行：混合检索（BM25 + 向量）/ Rerank
  后处理：Parent-Child 映射 / 上下文压缩

生成优化：
  Prompt 优化 / 引用溯源 / 回答格式化
```

---

## 一、检索优化策略

### 1. Chunk 切分优化

**问题**：切分质量直接决定检索精度。切太大，语义分散；切太小，上下文断裂。

| 策略 | 说明 | 适用场景 |
|------|------|---------|
| 固定字符切分 | `RecursiveCharacterTextSplitter(chunk_size=500)` | 通用，简单 |
| 标题感知切分 | `MarkdownHeaderTextSplitter` 按 `#/##/###` 切 | Markdown 文档 |
| 语义切分 | 按 embedding 相似度检测语义边界 | 长文档 |
| Parent-Child 切分 | 小块检索，大块返回给 LLM | 需要精准检索 + 完整上下文 |

**本项目实现**：Markdown 标题感知切分 + Parent-Child 分块

```python
# 第一步：按标题切分（Parent）
md_splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=[("#", "h1"), ("##", "h2"), ("###", "h3")],
    strip_headers=False,
)

# 第二步：对超大块二次切分（Child）
child_splitter = RecursiveCharacterTextSplitter(
    chunk_size=400,      # Child 块
    chunk_overlap=80,
)

# 检索用 child，返回给 LLM 用 parent
```

**参数设计**：

| 参数 | Parent | Child | 说明 |
|------|--------|-------|------|
| chunk_size | 800 | 400 | Parent 保持完整章节，Child 语义集中 |
| chunk_overlap | 150 | 80 | 防止语义断裂 |

**面试要点**：
- Parent-Child 的核心思想：小块语义集中适合检索，大块上下文完整适合生成
- chunk_size 不是越大越好，也不是越小越好，要根据文档特点调参
- 标题感知切分能保留文档结构，标题信息注入 chunk 能增强 embedding 语义

---

### 2. Embedding 模型升级

**问题**：Embedding 质量决定向量检索的语义理解能力。

| 模型 | 维度 | 特点 | 本项目 |
|------|------|------|--------|
| HashEmbedding | 384 | 无语义，仅哈希映射 | Demo 用，已替换 |
| DashScope tongyi-embedding-vision-plus | 1024 | 阿里云多模态，中文效果好 | ✅ 当前使用 |
| OpenAI text-embedding-3 | 3072 | 通用能力强 | 备选 |

**本项目实现**：HashEmbedding → DashScope tongyi-embedding-vision-plus

```python
class DashScopeMultiModalEmbedding:
    def _call_api(self, texts):
        for text in texts:
            resp = dashscope.MultiModalEmbedding.call(
                model=self.model,
                input=[{"text": text}],
                parameters={"dimension": self.dimensions},  # 1024 维
            )
```

**面试要点**：
- Embedding 模型选择要考虑：语言（中文/英文）、维度、延迟、成本
- 维度不是越高越好，3072 维的模型不一定比 1024 维好，要看具体场景
- 多模态 Embedding 支持文本+图片，但纯文本场景用纯文本 Embedding 就够了

---

### 3. 元数据增强

**问题**：chunk 切分后丢失了原始文档的结构信息（标题、章节）。

**本项目实现**：将标题层级注入 chunk 内容

```python
def _inject_header_context(chunk):
    """将标题层级信息注入 chunk 内容"""
    parts = []
    for key in ("h1", "h2", "h3"):
        if chunk.metadata.get(key):
            parts.append(chunk.metadata[key])
    if parts:
        prefix = " > ".join(parts)
        chunk.page_content = f"{prefix}\n{chunk.page_content}"
    return chunk

# 效果：
# 原始 chunk: "退票需要在演出前48小时申请..."
# 注入后:     "节目取消和退票 > 退票政策\n退票需要在演出前48小时申请..."
```

**面试要点**：
- 标题信息注入后，embedding 编码时就包含了标题语义
- BM25 检索时也能匹配到标题关键词
- 元数据还可以存文件路径、创建时间等，用于过滤

---

### 4. 查询改写（Query Rewrite）

**问题**：用户问题往往简短、模糊、口语化（"咋退"、"退票"），直接检索命中率低。

**本项目实现**：

```python
QUERY_REWRITE_PROMPT = """将用户的简短、模糊问题改写为适合知识库检索的完整查询。
改写规则：
1. 补充缺失的上下文（"退票"→"退票政策和退款流程"）
2. 将口语化表达转为正式表述（"咋退"→"退票流程和退款方式"）
3. 保留原始意图，不添加用户没有提到的信息
4. 如果问题已经足够清晰完整，直接返回原问题"""
```

**面试要点**：
- 查询改写是**成本最低、收益最高**的优化之一
- 改写后的查询用于检索，原始查询用于 Rerank（因为 Rerank 更接近用户真实意图）
- 可以用小模型做改写，不需要和生成用同一个大模型

---

### 5. HyDE（假设文档嵌入）

**问题**：用户问题和文档的语义风格差异大（问句 vs 陈述句），直接 embedding 匹配不准。

**原理**：先让 LLM 生成一个"假答案"，用假答案的 embedding 去检索，因为假答案的语义风格更接近真实文档。

```
用户问题: "怎么退票？"
  → LLM 生成假答案: "退票需要在演出前48小时申请，票款3个工作日退回"
  → 用假答案的 embedding 做向量检索
  → 命中真实文档: "退票政策\n若您想了解退票规则..."
```

**本项目**：未实现，可作为后续优化。

---

### 6. 多路召回（Multi-Query）

**问题**：一个问题只有一种表述，可能漏掉用不同说法写的文档。

**原理**：将一个问题改写成多个变体，分别检索，合并去重。

```
原始问题: "怎么退票？"
  → 变体1: "退票流程是什么"
  → 变体2: "如何申请退款"
  → 变体3: "取消订单怎么操作"
  → 分别检索，合并去重
```

**本项目**：未实现，可作为后续优化。

---

### 7. 混合检索（Hybrid Retrieval）

**问题**：纯向量检索语义理解强但关键词匹配弱；纯 BM25 关键词匹配强但语义理解弱。

**本项目实现**：BM25 + 向量检索，RRF 融合排序

```python
def hybrid_retrieve(query, vectorstore, bm25, chunks, k=5, bm25_weight=0.9):
    # BM25 检索（关键词匹配）
    bm25_scores = bm25.get_scores(tokenized_query)
    bm25_ranked = sorted(...)

    # 向量检索（语义匹配）
    vector_results = vectorstore.similarity_search_with_relevance_scores(query, k=k)

    # RRF 融合排序
    for rank, idx in enumerate(bm25_ranked):
        rrf_scores[id] += bm25_weight / (rrf_k + rank + 1)
    for rank, (doc, _) in enumerate(vector_results):
        rrf_scores[id] += (1 - bm25_weight) / (rrf_k + rank + 1)
```

**权重设置**：BM25 = 0.9，向量 = 0.1

**为什么 BM25 权重这么高？**
- DashScope Embedding 精度有限，向量检索效果一般
- 知识库是中文 Q&A 文档，关键词匹配更可靠
- 不同场景权重不同，需要根据实际效果调参

**面试要点**：
- RRF（Reciprocal Rank Fusion）基于排名融合，不需要归一化分数
- 公式：`score = Σ weight / (k + rank + 1)`，k 通常取 60
- 混合检索的核心是**互补**：BM25 补向量的关键词盲区，向量补 BM25 的语义盲区

---

### 8. Rerank 重排序

**问题**：粗排（BM25 + 向量）返回的候选集排序不够精准。

**原理**：用交叉编码器（Cross-Encoder）对 query-document 对做精排，比双塔模型更准但更慢。

**本项目实现**：FlashRank ms-marco-TinyBERT-L-2-v2

```python
from flashrank import Ranker, RerankRequest

ranker = Ranker(model_name="ms-marco-TinyBERT-L-2-v2", cache_dir="./models")
passages = [{"id": i, "text": doc.page_content} for i, doc in enumerate(docs)]
req = RerankRequest(query=query, passages=passages)
results = ranker.rerank(req)
```

**Reranker 对比**：

| 模型 | 大小 | 速度 | 精度 | 适用场景 |
|------|------|------|------|---------|
| FlashRank (TinyBERT) | ~30MB | ~80ms | 中 | 本项目，CPU 友好 |
| BGE-Reranker | ~1.1GB | ~500ms | 高 | 有 GPU 的场景 |
| Cohere Rerank | API | ~200ms | 高 | 不想本地部署 |

**本项目发现**：英文 Reranker 在中文内容上效果反而变差（100% → 81.8%），已默认关闭。生产环境需换中文 Reranker。

**面试要点**：
- Reranker 是**双塔 → 交叉编码器**的升级：双塔独立编码 query 和 doc，交叉编码器联合编码
- 交叉编码器精度高但慢，所以只对粗排的 Top-K 做精排（本项目 Top-20 → Top-5）
- Reranker 和 Embedding 模型可以不同，一个管精排一个管粗排

---

### 9. Parent-Child 映射

**问题**：小块检索精准但上下文不完整，大块上下文完整但检索不准。

**本项目实现**：child 用于检索，命中后映射回 parent 返回给 LLM

```python
def _resolve_parents(child_docs, parent_dict, k):
    """child 检索结果 → parent 返回给 LLM"""
    seen_parents = {}
    for doc in child_docs:
        parent_id = doc.metadata.get("parent_id")
        if parent_id and parent_id in parent_dict:
            if parent_id not in seen_parents:
                seen_parents[parent_id] = parent_dict[parent_id]
    return list(seen_parents.values())[:k]
```

**面试要点**：
- Parent-Child 解决的是**检索精度 vs 上下文完整性**的矛盾
- 实现时要注意 parent_id 的映射关系，多个 child 可能映射到同一个 parent
- 适合长文档场景；短文档（如本项目的 Q&A）每个 parent 只有 1 个 child，效果与单层相当

---

### 10. 上下文压缩

**问题**：检索结果太长，塞进 prompt 会超 token 限制，也会稀释关键信息。

**原理**：用 LLM 对检索结果做压缩，只保留与 query 相关的部分。

```
原始检索结果: "退票政策\n- 若您想了解退票规则...（500字）\n入场须知\n- 请携带身份证...（300字）"
用户问题: "怎么退票？"
压缩后: "退票政策\n- 若您想了解退票规则...（200字）"（只保留退票相关）
```

**本项目**：未实现，当前文档较短不需要。可作为后续优化。

---

## 二、生成优化策略

### 11. Prompt 优化

**本项目实现**：RAG 专用 Prompt，约束 LLM 只基于文档回答

```python
SYSTEM_PROMPT_RAG = """你是大麦购票项目的规则助手。请严格根据以下参考文档内容回答用户问题。
回答要求：
1. 只基于提供的文档内容回答，不要编造文档中没有的信息
2. 如果文档中没有相关内容，直接告知用户"抱歉，暂未找到相关信息"
3. 在回答末尾标注信息来源，格式为：【来源：文档名】
4. 引用具体条款时，尽量保留原文表述"""
```

**面试要点**：
- Prompt 约束是防止幻觉的最直接手段
- "只基于文档回答"比"尽量基于文档回答"约束力更强
- Prompt 里要求标注来源，可以让用户验证回答的可信度

---

### 12. 引用溯源

**本项目实现**：回答末尾标注来源文档，前端展示参考来源列表

```python
def format_docs_with_source(docs):
    parts = []
    for i, doc in enumerate(docs, 1):
        source = Path(doc.metadata.get("source", "未知文档")).stem
        parts.append(f"[文档{i}] 来源：{source}\n{doc.page_content}")
    return "\n\n".join(parts)
```

**面试要点**：
- 引用溯源增加用户信任，让用户知道 AI 不是在"瞎猜"
- 前端可以展示来源列表，用户点击可查看原始文档
- 引用溯源也是幻觉检测的一种手段——用户可以自己验证

---

## 三、本项目优化总结

| 类别 | 优化方式 | 本项目实现 | 效果 |
|------|---------|-----------|------|
| **检索优化** | Chunk 切分 | Markdown 标题感知 + Parent-Child | Recall@5 100% |
| | Embedding 升级 | Hash → DashScope 1024 维 | 来源命中率 23.6% → 100% |
| | 元数据增强 | 标题信息注入 chunk 内容 | 增强语义匹配 |
| | 查询改写 | LLM 自动改写模糊问题 | 提升模糊查询命中率 |
| | 混合检索 | BM25（0.9）+ 向量（0.1）+ RRF | 关键词 + 语义互补 |
| | Rerank | FlashRank（英文模型，已关闭） | 中文场景需换模型 |
| | Parent-Child 映射 | 小块检索 → 大块返回 | MRR 0.992 |
| **生成优化** | Prompt 优化 | RAG 专用 Prompt，约束只基于文档 | LLM Judge 4.9/5 |
| | 引用溯源 | 回答标注来源文档 | 用户可验证 |

---

## 四、本项目评测数据

| 指标 | 值 | 说明 |
|------|-----|------|
| Recall@5 | 100% | 65 条用例全部命中 |
| Precision@5 | 55.7% | Top-5 中相关文档占比 |
| MRR | 0.992 | 几乎全部排第 1 位 |
| 关键词命中率 | 98.5% | 64/65 命中 |
| LLM Judge 综合 | 4.9/5 | 相关性 5.0，忠实度 5.0，完整性 4.7 |
| 幻觉率 | 0% | 忠实度 5.0/5 |
| 平均延迟 | 320ms | BM25 + 向量混合检索 |

---

## 五、面试高频问题

| 问题 | 回答要点 |
|------|---------|
| RAG 检索不准怎么优化？ | 检索优化四步：切分、Embedding、检索方式、后处理 |
| RAG 回答不准怎么优化？ | 生成优化：Prompt 约束 + 引用溯源 + LLM Judge 评估 |
| BM25 和向量检索怎么混合？ | RRF 融合：`score = Σ weight / (k + rank + 1)`，按实际效果调权重 |
| Reranker 和 Embedding 有什么区别？ | Embedding 是双塔独立编码（粗排），Reranker 是交叉编码联合编码（精排） |
| chunk_size 怎么选？ | 根据文档特点：短问答 400-800，长文档 1000-1500，用 Parent-Child 两全其美 |
| 查询改写有什么用？ | 把用户的模糊问题变成适合检索的完整查询，成本低收益高 |
| Parent-Child 怎么实现？ | 小块做 embedding 和 BM25 检索，命中后映射回大块返回给 LLM |
| 怎么评估 RAG 效果？ | 检索质量（Recall/Precision/MRR）+ 生成质量（LLM Judge）+ 端到端（延迟） |
| 怎么检测幻觉？ | LLM Judge 忠实度评分，对比回答和检索文档内容 |
