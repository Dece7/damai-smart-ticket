"""MCP Server - 将现有工具封装为 MCP 标准服务

通过 MCP 协议暴露项目的 9 个工具，外部客户端（如 Claude Desktop、Cursor）
可以连接并调用这些工具。

启动方式：
  python -m app.mcp.server          # stdio 模式（本地客户端）
  python app/mcp/server.py --http   # HTTP 模式（远程客户端）
"""

import json
import logging
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

logger = logging.getLogger(__name__)

# 创建 MCP Server 实例
server = Server("damai-ticket-server")


# ===== 工具定义 =====

@server.list_tools()
async def list_tools() -> list[types.Tool]:
    """列出所有可用工具"""
    return [
        types.Tool(
            name="search_program",
            description="根据城市、类型或艺人搜索演出信息。至少提供一个查询条件。",
            inputSchema={
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名，如'北京'、'上海'"},
                    "category": {"type": "string", "description": "节目类型，如'演唱会'、'话剧'"},
                    "actor": {"type": "string", "description": "艺人或明星名字"},
                },
            },
        ),
        types.Tool(
            name="get_program_detail",
            description="根据节目 ID 获取节目详情，包括演出时间、地点、票价等。",
            inputSchema={
                "type": "object",
                "properties": {
                    "program_id": {"type": "integer", "description": "节目 ID"},
                },
                "required": ["program_id"],
            },
        ),
        types.Tool(
            name="get_ticket_info",
            description="查询指定节目的票档信息和余票状态。",
            inputSchema={
                "type": "object",
                "properties": {
                    "program_id": {"type": "integer", "description": "节目 ID"},
                },
                "required": ["program_id"],
            },
        ),
        types.Tool(
            name="create_order",
            description="创建购票订单。需要节目 ID、票档、数量和手机号。",
            inputSchema={
                "type": "object",
                "properties": {
                    "program_id": {"type": "integer", "description": "节目 ID"},
                    "ticket_price": {"type": "number", "description": "票价"},
                    "ticket_count": {"type": "integer", "description": "购票数量"},
                    "mobile": {"type": "string", "description": "手机号"},
                },
                "required": ["program_id", "ticket_price", "ticket_count", "mobile"],
            },
        ),
        types.Tool(
            name="query_ticket_status",
            description="查询指定节目的实时余票状态。",
            inputSchema={
                "type": "object",
                "properties": {
                    "program_id": {"type": "integer", "description": "节目 ID"},
                },
                "required": ["program_id"],
            },
        ),
        types.Tool(
            name="check_order_status",
            description="根据订单号查询订单状态。",
            inputSchema={
                "type": "object",
                "properties": {
                    "order_number": {"type": "string", "description": "订单号"},
                },
                "required": ["order_number"],
            },
        ),
        types.Tool(
            name="calculate_price",
            description="计算票价，包含会员折扣。支持查询会员折扣信息。",
            inputSchema={
                "type": "object",
                "properties": {
                    "program_id": {"type": "integer", "description": "节目 ID"},
                    "ticket_price": {"type": "number", "description": "票价"},
                    "ticket_count": {"type": "integer", "description": "购票数量"},
                    "mobile": {"type": "string", "description": "手机号（用于查询会员等级）"},
                },
                "required": ["program_id", "ticket_price", "ticket_count", "mobile"],
            },
        ),
        types.Tool(
            name="get_recommendations",
            description="根据条件推荐演出。支持按城市、类型、预算筛选。",
            inputSchema={
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名"},
                    "category": {"type": "string", "description": "节目类型：concert(演唱会)/theater(话剧)/sports(体育)"},
                    "budget": {"type": "number", "description": "预算上限"},
                },
            },
        ),
        types.Tool(
            name="search_knowledge_base",
            description="搜索购票规则知识库，回答退票政策、订票流程、入场规则等问题。",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词，如'退票'、'订票'、'入场'"},
                },
                "required": ["query"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """执行工具调用"""
    from app.chains.tools import (
        search_program, get_program_detail, get_ticket_info,
        create_order, search_knowledge_base,
        query_ticket_status, check_order_status, calculate_price, get_recommendations,
    )

    tool_map = {
        "search_program": search_program,
        "get_program_detail": get_program_detail,
        "get_ticket_info": get_ticket_info,
        "create_order": create_order,
        "search_knowledge_base": search_knowledge_base,
        "query_ticket_status": query_ticket_status,
        "check_order_status": check_order_status,
        "calculate_price": calculate_price,
        "get_recommendations": get_recommendations,
    }

    tool_func = tool_map.get(name)
    if not tool_func:
        return [types.TextContent(type="text", text=f"未知工具: {name}")]

    try:
        # LangChain @tool 装饰的函数需要通过 invoke 调用
        result = tool_func.invoke(arguments)
        return [types.TextContent(type="text", text=str(result))]
    except Exception as e:
        logger.error(f"工具 {name} 执行失败: {e}")
        return [types.TextContent(type="text", text=f"工具执行失败: {str(e)}")]


async def run_stdio():
    """以 stdio 模式运行 MCP Server"""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


async def run_http(host: str = "0.0.0.0", port: int = 8001):
    """以 HTTP 模式运行 MCP Server（SSE 传输）"""
    from mcp.server.sse import SseServerTransport
    from starlette.applications import Starlette
    from starlette.routing import Route, Mount
    import uvicorn

    sse = SseServerTransport("/messages/")

    async def handle_sse(request):
        async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
            await server.run(streams[0], streams[1], server.create_initialization_options())

    app = Starlette(
        routes=[
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
        ],
    )

    print(f"MCP Server 启动于 http://{host}:{port}/sse")
    print(f"客户端连接地址: http://localhost:{port}/sse")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    import asyncio
    import sys

    logging.basicConfig(level=logging.INFO)

    if "--http" in sys.argv:
        port = 8001
        for i, arg in enumerate(sys.argv):
            if arg == "--port" and i + 1 < len(sys.argv):
                port = int(sys.argv[i + 1])
        asyncio.run(run_http(port=port))
    else:
        asyncio.run(run_stdio())
