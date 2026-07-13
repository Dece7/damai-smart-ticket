from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from scalar_fastapi import get_scalar_api_reference
from app.api.chat import router as chat_router
from app.api.conversation import router as conv_router
from app.api.agent import router as agent_router
from app.api.admin import router as admin_router
from app.api.knowledge import router as knowledge_router
from app.api.mcp import router as mcp_router
from app.api.router_skill import router as router_skill_router
from app.core.database import init_db

STATIC_DIR = Path(__file__).parent.parent / "static"

app = FastAPI(title="大麦智能票务助手", version="0.1.0", docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router, prefix="/api")
app.include_router(conv_router, prefix="/api")
app.include_router(agent_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(knowledge_router, prefix="/api")
app.include_router(mcp_router, prefix="/api")
app.include_router(router_skill_router, prefix="/api")


@app.on_event("startup")
async def startup():
    init_db()


@app.get("/scalar", include_in_schema=False)
async def scalar_docs():
    return get_scalar_api_reference(openapi_url=app.openapi_url, title=app.title)


# 静态资源目录（构建产物）
app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="assets")


# SPA 兜底：所有非 API、非静态路由返回 index.html
@app.get("/{full_path:path}", include_in_schema=False)
async def spa_catchall(request: Request, full_path: str):
    # 尝试返回静态文件，不存在则返回 index.html
    file_path = STATIC_DIR / full_path
    if full_path and file_path.is_file():
        return FileResponse(file_path)
    return FileResponse(STATIC_DIR / "index.html")

