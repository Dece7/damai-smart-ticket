"""工具定义 - 对应原项目 AiProgram.java 的 @Tool 方法"""

from langchain_core.tools import tool
from app.services.mock_data import PROGRAMS, TICKET_CATEGORIES, USERS, ORDER_COUNTER


@tool
def search_knowledge_base(query: str) -> str:
    """搜索购票规则知识库，回答退票政策、订票流程、入场规则等问题。
    当用户询问规则、政策、流程相关问题时使用此工具。

    Args:
        query: 搜索关键词，如"退票"、"订票"、"入场"
    """
    from app.pipelines.document_pipeline import load_vectorstore
    vectorstore = load_vectorstore()
    docs = vectorstore.similarity_search(query, k=3)
    return "\n\n".join(doc.page_content for doc in docs)


@tool
def search_program(city: str = "", category: str = "", actor: str = "") -> list[dict]:
    """根据城市、类型或艺人查询推荐的节目。至少提供一个查询条件。

    Args:
        city: 城市名，如"北京"、"上海"
        category: 节目类型，如"演唱会"、"音乐节"、"话剧"、"相声"
        actor: 艺人名，如"周杰伦"、"林俊杰"
    """
    results = PROGRAMS
    if city:
        results = [p for p in results if city in p["city"]]
    if category:
        results = [p for p in results if category in p["category"]]
    if actor:
        results = [p for p in results if actor in p["actor"]]
    return results


@tool
def get_program_detail(program_id: int) -> dict | None:
    """根据节目ID查询节目详情，包括票价信息。

    Args:
        program_id: 节目ID
    """
    program = next((p for p in PROGRAMS if p["id"] == program_id), None)
    if not program:
        return None
    tickets = TICKET_CATEGORIES.get(program_id, [])
    return {**program, "tickets": tickets}


@tool
def get_ticket_info(program_id: int) -> list[dict]:
    """根据节目ID查询票档信息（价格、余票）。

    Args:
        program_id: 节目ID
    """
    return TICKET_CATEGORIES.get(program_id, [])


@tool
def create_order(program_id: int, ticket_price: float, ticket_count: int, mobile: str) -> dict:
    """为用户生成购买节目的订单。需要先查询节目和票档信息后再调用。

    Args:
        program_id: 节目ID
        ticket_price: 票档价格
        ticket_count: 购票数量
        user_mobile: 用户手机号
    """
    program = next((p for p in PROGRAMS if p["id"] == program_id), None)
    if not program:
        return {"error": "节目不存在"}

    tickets = TICKET_CATEGORIES.get(program_id, [])
    ticket = next((t for t in tickets if t["price"] == ticket_price), None)
    if not ticket:
        return {"error": f"未找到价格为{ticket_price}的票档"}

    if ticket["remain"] < ticket_count:
        return {"error": f"余票不足，当前剩余{ticket['remain']}张"}

    user = USERS.get(mobile)
    if not user:
        return {"error": f"用户{mobile}不存在"}

    ORDER_COUNTER[0] += 1
    order_number = f"DM{ORDER_COUNTER[0]}"

    ticket["remain"] -= ticket_count

    return {
        "orderNumber": order_number,
        "programName": program["name"],
        "ticketName": ticket["name"],
        "price": ticket_price,
        "count": ticket_count,
        "totalAmount": ticket_price * ticket_count,
        "userName": user["name"],
        "status": "待支付",
        "payUrl": f"http://localhost:5173/order/{order_number}",
    }
