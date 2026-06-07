"""文档处理管线 - 对应原项目 MarkdownLoader.java

流程：Markdown 文件 → 加载 → 分块 → Embedding → 存入 ChromaDB

使用 ChromaDB 默认 Embedding（首次需下载 ~80MB 模型）
若网络慢，可改用 HashEmbedding（demo 用，精度低但无需下载）
"""

import hashlib
import logging
from pathlib import Path
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

RAG_DOCS_DIR = Path(__file__).parent.parent.parent / "docs" / "rag"
CHROMA_PERSIST_DIR = str(Path(__file__).parent.parent.parent / "chroma_db")


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


def split_documents(documents: list[Document], chunk_size: int = 500, chunk_overlap: int = 100) -> list[Document]:
    """文档分块"""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", "。", "！", "？", ".", "!", "?", " "],
    )
    chunks = splitter.split_documents(documents)
    logger.info(f"分块完成：{len(documents)} 个文档 → {len(chunks)} 个分块")
    return chunks


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


def build_vectorstore(chunks: list[Document]):
    """将分块存入 ChromaDB"""
    import chromadb
    from langchain_chroma import Chroma

    client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
    embedding_fn = HashEmbeddingFunction()

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
    embedding_fn = HashEmbeddingFunction()

    return Chroma(
        embedding_function=embedding_fn,
        client=client,
        collection_name="damai_rag",
    )
