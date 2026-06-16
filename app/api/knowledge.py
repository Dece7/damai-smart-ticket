"""知识库管理 API"""

import shutil
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/knowledge", tags=["知识库管理"])

RAG_DOCS_DIR = Path(__file__).parent.parent.parent / "docs" / "rag"


class DocumentInfo(BaseModel):
    name: str
    size: int
    chunks: int


class RebuildResult(BaseModel):
    documents: int
    chunks: int


def _count_chunks(filepath: Path) -> int:
    """估算文档分块数（粗略按标题段落拆分）"""
    try:
        text = filepath.read_text(encoding="utf-8")
        # 简单估算：按 800 字一块（与 split_documents 默认 chunk_size 一致）
        return max(1, len(text) // 800)
    except Exception:
        return 0


@router.get("/documents", response_model=list[DocumentInfo])
async def list_documents():
    """获取知识库文档列表"""
    if not RAG_DOCS_DIR.exists():
        return []

    docs = []
    for f in sorted(RAG_DOCS_DIR.glob("*.md")):
        docs.append(DocumentInfo(
            name=f.name,
            size=f.stat().st_size,
            chunks=_count_chunks(f),
        ))
    return docs


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """上传文档到知识库"""
    if not file.filename:
        raise HTTPException(400, "文件名为空")

    # 只允许 .md 文件
    if not file.filename.endswith(".md"):
        raise HTTPException(400, "仅支持 .md 格式的 Markdown 文件")

    RAG_DOCS_DIR.mkdir(parents=True, exist_ok=True)
    dest = RAG_DOCS_DIR / file.filename

    if dest.exists():
        raise HTTPException(409, f"文件 {file.filename} 已存在")

    content = await file.read()
    dest.write_bytes(content)

    return {"message": f"上传成功: {file.filename}", "name": file.filename}


@router.delete("/documents/{name}")
async def delete_document(name: str):
    """删除知识库文档"""
    filepath = RAG_DOCS_DIR / name

    if not filepath.exists():
        raise HTTPException(404, f"文件 {name} 不存在")

    filepath.unlink()
    return {"message": f"已删除: {name}"}


@router.post("/rebuild", response_model=RebuildResult)
async def rebuild_index():
    """重建向量索引（向量库 + BM25 索引 + Parent chunks）"""
    from app.pipelines.document_pipeline import (
        load_documents, split_documents_with_parents,
        build_vectorstore, save_parent_chunks,
    )
    from app.pipelines.rag_pipeline import build_bm25_index

    docs = load_documents(RAG_DOCS_DIR)
    if not docs:
        raise HTTPException(400, "知识库为空，请先上传文档")

    child_chunks, parent_dict = split_documents_with_parents(docs)
    save_parent_chunks(parent_dict)
    build_vectorstore(child_chunks)
    build_bm25_index(child_chunks)

    return RebuildResult(documents=len(docs), chunks=len(child_chunks))
