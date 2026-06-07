from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from scalar_fastapi import get_scalar_api_reference
from app.api.chat import router as chat_router
from app.api.conversation import router as conv_router
from app.api.agent import router as agent_router
from app.api.admin import router as admin_router
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


@app.on_event("startup")
async def startup():
    init_db()


@app.get("/", include_in_schema=False)
async def root():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/scalar", include_in_schema=False)
async def scalar_docs():
    return get_scalar_api_reference(openapi_url=app.openapi_url, title=app.title)


@app.get("/admin", include_in_schema=False)
async def admin_page():
    return FileResponse(STATIC_DIR / "admin.html")


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
