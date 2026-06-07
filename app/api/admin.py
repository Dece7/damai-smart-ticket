"""管理员统计接口"""

from fastapi import APIRouter
from sqlalchemy import text
from app.core.database import SessionLocal

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/stats/summary")
def stats_summary():
    """总览：总消息数、总对话数、总 token、平均 token"""
    db = SessionLocal()
    try:
        row = db.execute(text("""
            SELECT
                COUNT(*) as total_messages,
                COUNT(DISTINCT conversation_id) as total_conversations,
                COALESCE(SUM(CAST(json_extract(token_usage, '$.total_tokens') AS INTEGER)), 0) as total_tokens,
                COALESCE(AVG(CAST(json_extract(token_usage, '$.total_tokens') AS INTEGER)), 0) as avg_tokens
            FROM messages
            WHERE role = 'assistant' AND token_usage IS NOT NULL
        """)).fetchone()
        return {
            "total_messages": row[0],
            "total_conversations": row[1],
            "total_tokens": row[2],
            "avg_tokens": round(row[3]),
        }
    finally:
        db.close()


@router.get("/stats/trend")
def stats_trend(days: int = 30):
    """按天统计 token 趋势"""
    db = SessionLocal()
    try:
        rows = db.execute(text("""
            SELECT
                DATE(created_at) as date,
                COUNT(*) as message_count,
                COALESCE(SUM(CAST(json_extract(token_usage, '$.prompt_tokens') AS INTEGER)), 0) as prompt_tokens,
                COALESCE(SUM(CAST(json_extract(token_usage, '$.completion_tokens') AS INTEGER)), 0) as completion_tokens,
                COALESCE(SUM(CAST(json_extract(token_usage, '$.total_tokens') AS INTEGER)), 0) as total_tokens
            FROM messages
            WHERE role = 'assistant' AND token_usage IS NOT NULL
                AND created_at >= DATE('now', :offset)
            GROUP BY DATE(created_at)
            ORDER BY date
        """), {"offset": f"-{days} days"}).fetchall()
        return [
            {
                "date": r[0],
                "message_count": r[1],
                "prompt_tokens": r[2],
                "completion_tokens": r[3],
                "total_tokens": r[4],
            }
            for r in rows
        ]
    finally:
        db.close()


@router.get("/stats/by_mode")
def stats_by_mode():
    """按 chat_type 分组统计"""
    db = SessionLocal()
    try:
        rows = db.execute(text("""
            SELECT
                c.chat_type,
                COUNT(m.id) as message_count,
                COALESCE(AVG(CAST(json_extract(m.token_usage, '$.total_tokens') AS INTEGER)), 0) as avg_tokens,
                COALESCE(SUM(CAST(json_extract(m.token_usage, '$.total_tokens') AS INTEGER)), 0) as total_tokens
            FROM messages m
            JOIN conversations c ON m.conversation_id = c.id
            WHERE m.role = 'assistant' AND m.token_usage IS NOT NULL
            GROUP BY c.chat_type
        """)).fetchall()
        return [
            {
                "chat_type": r[0],
                "message_count": r[1],
                "avg_tokens": round(r[2]),
                "total_tokens": r[3],
            }
            for r in rows
        ]
    finally:
        db.close()
