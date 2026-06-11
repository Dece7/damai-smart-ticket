"""MCP Server 管理接口"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/mcp", tags=["MCP"])


class MCPServerInfo(BaseModel):
    name: str
    tools: list[dict]
    status: str


@router.get("/info", response_model=MCPServerInfo)
async def get_mcp_info():
    """获取 MCP Server 信息和可用工具列表"""
    from app.mcp.server import list_tools

    tools = await list_tools()
    tool_list = [
        {
            "name": t.name,
            "description": t.description,
            "parameters": t.inputSchema.get("properties", {}),
        }
        for t in tools
    ]

    return MCPServerInfo(
        name="damai-ticket-server",
        tools=tool_list,
        status="running",
    )


@router.get("/tools")
async def list_mcp_tools():
    """列出所有 MCP 工具"""
    from app.mcp.server import list_tools

    tools = await list_tools()
    return [
        {
            "name": t.name,
            "description": t.description,
            "parameters": t.inputSchema.get("properties", {}),
            "required": t.inputSchema.get("required", []),
        }
        for t in tools
    ]
