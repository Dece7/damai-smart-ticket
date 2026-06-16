"""文档处理管线 - 对应原项目 MarkdownLoader.java

流程：Markdown 文件 → 加载 → 分块 → Embedding → 存入 ChromaDB

支持三种 Embedding：
- hash: HashEmbedding（demo 用，精度低但无需 API）
- deepseek: DeepSeek Embedding API（生产推荐）
- local: 本地模型（需下载）
"""

import hashlib
import logging
import pickle
from pathlib import Path
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter, MarkdownHeaderTextSplitter
from langchain_core.documents import Document
from app.core.config import get_settings

logger = logging.getLogger(__name__)

RAG_DOCS_DIR = Path(__file__).parent.parent.parent / "docs" / "rag"
CHROMA_PERSIST_DIR = str(Path(__file__).parent.parent.parent / "chroma_db")
PARENT_CHUNKS_PATH = Path(__file__).parent.parent.parent / "data" / "parent_chunks.pkl"


def load_documents(doc_dir: Path = RAG_DOCS_DIR) -> list[Document]:
    """加载目录下所有 Markdown 文件"""
    loader = DirectoryLoader(
        str(doc_dir),
        glob="**/*.md",
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"},
    )
    documents = loader.load()
    logger.info(f"加载了 {len(documents)} 个文档")
    return documents


# Markdown 标题切分配置
MARKDOWN_HEADERS = [
    ("#", "h1"),
    ("##", "h2"),
    ("###", "h3"),
]


def _inject_header_context(chunk: Document) -> Document:
    """将标题层级信息注入 chunk 内容，提升 embedding 和 BM25 检索效果"""
    metadata = chunk.metadata
    parts = []
    # 按标题层级拼接前缀：h1 > h2 > h3
    for key in ("h1", "h2", "h3"):
        if metadata.get(key):
            parts.append(metadata[key])
    if parts:
        prefix = " > ".join(parts)
        chunk.page_content = f"{prefix}\n{chunk.page_content}"
    return chunk


def split_documents(documents: list[Document], chunk_size: int = 800, chunk_overlap: int = 150) -> list[Document]:
    """文档分块 - Markdown 标题感知 + 二次切分

    1. 先按 Markdown 标题层级（#/##/###）切分，保留标题元数据
    2. 将标题信息注入 chunk 内容，增强 embedding 语义
    3. 对超大块做二次切分，确保不超过 chunk_size
    """
    md_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=MARKDOWN_HEADERS,
        strip_headers=False,
    )

    all_chunks = []
    for doc in documents:
        # 第一步：按标题切分
        md_chunks = md_splitter.split_text(doc.page_content)
        # 继承源文档的 metadata（如 source 文件路径）
        for chunk in md_chunks:
            chunk.metadata.update({k: v for k, v in doc.metadata.items() if k not in chunk.metadata})

        # 第二步：注入标题上下文到内容
        md_chunks = [_inject_header_context(c) for c in md_chunks]

        # 第三步：对超大块做二次切分
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", "。", "！", "？", ".", "!", "?", " "],
        )
        final_chunks = text_splitter.split_documents(md_chunks)
        all_chunks.extend(final_chunks)

    logger.info(f"分块完成：{len(documents)} 个文档 → {len(all_chunks)} 个分块")
    return all_chunks


def _make_parent_id(content: str, source: str) -> str:
    """生成 parent chunk 的唯一 ID"""
    return hashlib.md5(f"{source}:{content[:200]}".encode()).hexdigest()[:12]


def split_documents_with_parents(
    documents: list[Document],
    child_chunk_size: int = 400,
    child_chunk_overlap: int = 80,
) -> tuple[list[Document], dict[str, Document]]:
    """Parent-Child 分块：小块检索，大块返回给 LLM

    1. 按 Markdown 标题切分 → parent chunks（完整 Q&A 章节）
    2. 注入标题上下文到 parent
    3. 对每个 parent 切出 child chunks（小块，用于检索）
    4. child metadata 中记录 parent_id

    Returns:
        (child_chunks, parent_dict)
        - child_chunks: 用于 embedding 和 BM25 检索的小块
        - parent_dict: {parent_id: parent_chunk} 用于检索后回查大块
    """
    md_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=MARKDOWN_HEADERS,
        strip_headers=False,
    )

    child_splitter = RecursiveCharacterTextSplitter(
        chunk_size=child_chunk_size,
        chunk_overlap=child_chunk_overlap,
        separators=["\n\n", "\n", "。", "！", "？", ".", "!", "?", " "],
    )

    all_children = []
    parent_dict = {}

    for doc in documents:
        # 第一步：按标题切分 → parent chunks
        md_chunks = md_splitter.split_text(doc.page_content)
        for chunk in md_chunks:
            chunk.metadata.update({k: v for k, v in doc.metadata.items() if k not in chunk.metadata})

        # 第二步：注入标题上下文
        md_chunks = [_inject_header_context(c) for c in md_chunks]

        # 第三步：每个 parent 切出 child chunks
        for parent in md_chunks:
            parent_id = _make_parent_id(parent.page_content, doc.metadata.get("source", ""))
            parent.metadata["parent_id"] = parent_id
            parent_dict[parent_id] = parent

            children = child_splitter.split_documents([parent])
            for child in children:
                child.metadata["parent_id"] = parent_id
            all_children.extend(children)

    logger.info(f"Parent-Child 分块：{len(documents)} 个文档 → {len(parent_dict)} 个 parent → {len(all_children)} 个 child")
    return all_children, parent_dict


def save_parent_chunks(parent_dict: dict[str, Document]):
    """持久化 parent chunks 到 pickle 文件"""
    PARENT_CHUNKS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PARENT_CHUNKS_PATH, "wb") as f:
        pickle.dump(parent_dict, f)
    logger.info(f"Parent chunks 已保存：{PARENT_CHUNKS_PATH} ({len(parent_dict)} 个)")


def load_parent_chunks() -> dict[str, Document] | None:
    """加载 parent chunks，不存在则返回 None"""
    if not PARENT_CHUNKS_PATH.exists():
        return None
    with open(PARENT_CHUNKS_PATH, "rb") as f:
        parent_dict = pickle.load(f)
    logger.info(f"Parent chunks 已加载：{len(parent_dict)} 个")
    return parent_dict


class HashEmbeddingFunction:
    """基于哈希的 Embedding（demo 用，无需下载模型）"""

    def _embed(self, text: str, dim: int = 384) -> list[float]:
        hash_bytes = hashlib.md5(text.encode()).digest()
        vec = []
        for i in range(dim):
            byte_val = hash_bytes[i % len(hash_bytes)]
            vec.append((byte_val / 128.0) - 1.0)
        return vec

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


class DashScopeMultiModalEmbedding:
    """阿里云多模态 Embedding（支持 tongyi-embedding-vision 系列）

    使用 MultiModalEmbedding.call() 接口，而非 TextEmbedding.call()
    """

    def __init__(self, model: str, api_key: str, dimensions: int = None):
        import dashscope
        dashscope.api_key = api_key
        self.model = model
        self.dimensions = dimensions

    def _call_api(self, texts: list[str]) -> list[list[float]]:
        import dashscope
        from http import HTTPStatus

        results = []
        # 逐条调用（多模态接口不支持批量文本）
        for text in texts:
            input_data = [{"text": text}]
            params = {"model": self.model, "input": input_data}
            if self.dimensions:
                params["parameters"] = {"dimension": self.dimensions}

            resp = dashscope.MultiModalEmbedding.call(**params)
            if resp.status_code == HTTPStatus.OK:
                embedding = resp.output["embeddings"][0]["embedding"]
                results.append(embedding)
            else:
                raise ValueError(f"Embedding 失败: {resp.code} - {resp.message}")
        return results

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._call_api(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._call_api([text])[0]


def get_embedding_function():
    """根据配置获取 Embedding 函数"""
    settings = get_settings()
    provider = settings.embedding_provider

    if provider == "dashscope":
        logger.info(f"使用 DashScope 多模态 Embedding: {settings.embedding_model}")
        return DashScopeMultiModalEmbedding(
            model=settings.embedding_model,
            api_key=settings.dashscope_api_key,
            dimensions=settings.embedding_dimensions,
        )
    else:
        logger.info("使用 HashEmbedding（demo 模式）")
        return HashEmbeddingFunction()


def build_vectorstore(chunks: list[Document]):
    """将分块存入 ChromaDB"""
    import chromadb
    from langchain_chroma import Chroma

    client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
    embedding_fn = get_embedding_function()

    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embedding_fn,
        client=client,
        collection_name="damai_rag",
    )
    logger.info(f"向量数据库构建完成，共 {len(chunks)} 个分块")
    return vectorstore


def load_vectorstore():
    """加载已有的向量数据库"""
    import chromadb
    from langchain_chroma import Chroma

    client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
    embedding_fn = get_embedding_function()

    return Chroma(
        embedding_function=embedding_fn,
        client=client,
        collection_name="damai_rag",
    )
