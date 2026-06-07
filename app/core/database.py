"""数据库配置 - SQLite（轻量，无需额外安装）"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "data" / "damai.db"
DB_PATH.parent.mkdir(exist_ok=True)

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def migrate_db():
    """SQLite 增量迁移"""
    import sqlite3
    conn = sqlite3.connect(str(DB_PATH))
    columns = [row[1] for row in conn.execute("PRAGMA table_info(messages)").fetchall()]
    if "token_usage" not in columns:
        conn.execute("ALTER TABLE messages ADD COLUMN token_usage TEXT")
        conn.commit()
    if "steps" not in columns:
        conn.execute("ALTER TABLE messages ADD COLUMN steps TEXT")
        conn.commit()
    conn.close()


def init_db():
    Base.metadata.create_all(bind=engine)
    migrate_db()
