# Phase 8：功能扩展

> Reranker 精排、离线评估体系、Function Calling 扩展、前端工程化、知识库管理 API。

---

## 做了什么

三个方向的深度优化：① 检索质量（Reranker 精排 + 评估体系）、② 工具能力（9 个工具 + 推荐系统）、③ 前端工程化（Vue 3 + Vite + Element Plus 重构）。

---

## 核心知识点

### 1. Reranker 精排

```
原有流程：查询 → BM25 + 向量 → RRF → Top-K → LLM

增强流程：查询 → BM25 + 向量 → RRF → Top-20 → Reranker 精排 → Top-5 → LLM
                                                          ↑
                                                       新增环节
```

| 方案 | 优点 | 缺点 |
|------|------|------|
| BGE-Reranker（本地） | 免费、中文效果好 | 需要 GPU 或 CPU 推理慢 |
| Cohere Rerank（API） | 效果最好 | 付费、需联网 |
| FlashRank（轻量） | CPU 友好、~30MB | 效果略差 |

**项目选择 FlashRank**，模型 `ms-marco-TinyBERT-L-2-v2`（~3MB），单次推理 ~80ms。

**面试要点：**
- Reranker 是交叉编码器（Cross-Encoder），联合编码 query 和 doc，计算交互特征，精度比双塔 Embedding 更高
- 粗排（向量+BM25）效率高但精度有限，精排（Reranker）精度高但慢，分阶段过滤是最佳实践
- 实测来源命中率从 23.6% 提升到 32.7%（+9.1%）

**面试问：** Reranker 和 Embedding 的区别？
**答：** Embedding 是双塔模型，query 和 doc 独立编码成向量，用余弦相似度比较，速度快但精度有限；Reranker 是交叉编码器，query 和 doc 联合编码，计算 token 级别交互特征，精度更高但速度慢。最佳实践是先用 Embedding 粗排取 Top-20，再用 Reranker 精排取 Top-5。

---

### 2. 离线评估体系

```python
eval_dataset = [
    {
        "question": "怎么退票？",
        "expected_sources": ["节目取消和退票-相关问题与回答.md"],
        "keywords": ["退票", "手续费"],
        "difficulty": "easy"
    },
    # ... 65 条（55 knowledge + 5 ticket + 5 both），覆盖所有 15 份文档
]
```

| 指标 | 计算方式 | 说明 |
|------|----------|------|
| Recall@5（来源命中率） | 答案文档是否在 Top-5 检索结果中 | 衡量检索召回 |
| Precision@5（精确率） | Top-5 结果中有多少是相关的 | 衡量检索精度 |
| MRR（平均倒数排名） | 第一个相关结果排在第几位 | 衡量排序质量 |
| 关键词命中率 | 回答是否包含预期关键词 | 衡量生成质量 |
| LLM Judge | 用 LLM 对回答做相关性/忠实度/完整性评分 | 衡量回答质量 |
| 端到端延迟 | 从提问到返回的时间 | 衡量性能 |

**评估结果（Parent-Child + DashScope Embedding）：**

| 指标 | 值 |
|------|-----|
| Recall@5 | 100% |
| Precision@5 | 55.7% |
| MRR | 0.992 |
| 关键词命中率 | 98.5% |
| LLM Judge 综合 | 4.9/5（相关性 5.0、忠实度 5.0、完整性 4.7） |
| 端到端延迟 | 320ms |

**关键发现**：英文 Reranker（ms-marco-TinyBERT-L-2-v2）在中文内容上效果反而变差（100% → 81.8%），已默认关闭。生产环境需换中文 Reranker。

**面试要点：**
- 离线评估是 RAG 系统迭代优化的基础，没有量化指标就无法说"优化了 X%"
- 测试集要覆盖简单/复杂/边界场景，50-100 条足够
- A/B 测试：同一测试集跑优化前后，对比命中率和准确率

**面试问：** RAG 系统怎么评估？
**答：** 分层评估：① 检索质量（Recall@5、Precision@5、MRR）— 检索结果是否包含正确文档、是否排在前面；② 生成质量（LLM Judge 相关性/忠实度/完整性）— 回答是否准确、有没有幻觉；③ 端到端（延迟、成功率）— 用户体验。先优化检索命中率，再优化生成质量。

---

### 3. Function Calling 扩展

工具从 5 个扩展到 9 个，覆盖查询、计算、推荐全场景：

| 工具 | 类型 | 功能 | 参数 |
|------|------|------|------|
| `search_program` | 查询 | 搜索演出信息 | city, category, actor |
| `get_program_detail` | 查询 | 查节目详情 | program_id |
| `get_ticket_info` | 查询 | 查票档信息 | program_id |
| `create_order` | 操作 | 生成订单 | program_id, ticket_price, ticket_count, mobile |
| `query_ticket_status` | 查询 | 查实时余票 | program_id |
| `check_order_status` | 查询 | 查订单状态 | order_number |
| `calculate_price` | 计算 | 算票价含折扣 | program_id, ticket_price, ticket_count, mobile |
| `get_recommendations` | 推荐 | 推荐演出 | city, category, budget |
| `search_knowledge_base` | RAG | 检索知识库 | query（内部调用 RAG 管线，不做查询改写） |

**各模式的工具分配：**

| 模式 | 工具 | 说明 |
|------|------|------|
| 规则助手 | 无（直接调 RAG 管线） | 不经过 tool 机制 |
| 贴心助手 | 8 个业务工具 | 不含 search_knowledge_base |
| Agent | 全部 9 个 | LangGraph ReAct 控制循环 |
| 多 Agent | ticket 8 个 + knowledge 1 个 | 按分工分配 |

**search_knowledge_base 说明**：内部调用 RAG 管线（BM25 + 向量混合检索 + Parent-Child 映射），不做查询改写（LLM 调用工具时的 query 已经足够精准，只有规则助手才有查询改写的环节）。

**会员折扣系统：**
```python
MEMBER_DISCOUNTS = {"普通": 1.0, "银卡": 0.95, "金卡": 0.9, "钻石": 0.85}
```

**面试要点：**
- 工具描述写清楚用途和参数是关键，LLM 靠描述决定调用哪个工具
- 查询类和操作类工具要区分，操作类工具需要更严格的确认机制
- 不同模式分配不同工具，避免功能重叠（贴心助手不含知识库工具）
- Agent 可以自动编排多个工具的调用顺序（先查节目→再查票档→最后下单）

**面试问：** 工具多了 LLM 怎么选择？
**答：** LLM 根据工具的 `name` 和 `description` 语义匹配用户意图。描述写得越清晰，选择越准确。最佳实践：① 工具名用动词短语（search_program）；② 描述包含适用场景和参数说明；③ 参数加类型注解和枚举约束。不同模式分配不同工具，避免功能重叠。

---

### 4. 前端工程化

从 CDN 单文件重构为 Vite 工程化项目：

```
frontend/
├── src/
│   ├── api/          # axios 封装 + SSE 流式调用
│   ├── stores/       # Pinia 状态管理
│   ├── router/       # Vue Router（/, /knowledge, /admin）
│   ├── views/        # 页面级组件
│   │   ├── ChatView.vue         # 对话主界面
│   │   ├── KnowledgeView.vue    # 知识库管理
│   │   └── AdminView.vue        # 管理仪表盘
│   ├── components/   # 通用组件
│   │   ├── ChatMessage.vue      # 消息气泡
│   │   ├── ReasoningTimeline.vue # 推理时间线
│   │   └── SourceCard.vue       # 来源卡片
│   └── styles/       # 全局样式
├── vite.config.ts    # API proxy + 构建输出
└── package.json
```

**技术栈：** Vue 3 + TypeScript + Vite 6 + Element Plus + Pinia + Vue Router + ECharts

**关键设计决策：**

| 决策 | 选择 | 原因 |
|------|------|------|
| 构建输出 | `static/` 目录 | FastAPI 直接服务，无需 nginx |
| API 代理 | Vite dev server proxy | 开发时自动转发 /api 到 FastAPI |
| 状态管理 | Pinia | 管理会话列表、当前对话、流式状态 |
| 图表库 | ECharts 替代 Chart.js | 中文生态更好，配置更灵活 |
| 路由模式 | History 模式 | URL 更干净，后端 SPA 兜底 |

**面试要点：**
- 前后端分离：开发时 Vite dev server（5173）+ FastAPI（8000），生产时 FastAPI 服务编译后的静态文件
- 组件化拆分提高可维护性：ChatMessage 负责单条消息渲染，ReasoningTimeline 负责推理步骤展示
- Pinia 集中管理状态，避免组件间 prop drilling

**面试问：** 前后端分离后怎么部署？
**答：** `npm run build` 编译前端到 `static/` 目录，FastAPI 用 `StaticFiles` 服务静态文件，SPA 兜底路由返回 `index.html`。开发时用 Vite proxy 转发 API 请求，不需要跨域配置。

---

### 5. 知识库管理 API

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/knowledge/documents` | GET | 获取文档列表（名称、大小、预估分块数） |
| `/api/knowledge/upload` | POST | 上传 .md 文件到 docs/rag/ |
| `/api/knowledge/documents/{name}` | DELETE | 删除指定文档 |
| `/api/knowledge/rebuild` | POST | 重建向量库 + BM25 索引 |

**面试要点：**
- 上传后需要重建索引才能生效，因为向量库是离线构建的
- 文档管理与索引构建解耦，支持批量操作后统一重建
- 只允许 .md 格式，防止二进制文件污染知识库

---

### 面试高频问题

| 问题 | 回答要点 |
|------|---------|
| 粗排 + 精排的好处？ | 粗排（向量+BM25）快速筛选候选集，精排（Reranker）精确排序，平衡延迟和精度 |
| 测试集怎么构造？ | 人工编写标准问答对，覆盖所有文档，包含简单/复杂/边界场景 |
| 工具描述怎么写？ | 动词短语命名、描述包含适用场景、参数加类型注解和枚举约束 |
| Vite 和 Webpack 的区别？ | Vite 基于 ESBuild 原生 ESM，开发启动秒级；Webpack 需要打包，启动慢 |
| Pinia 和 Vuex 的区别？ | Pinia 是 Vuex 5，支持 TypeScript、组合式 API、去 mutations |
