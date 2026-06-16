"""工具定义 - 支持模拟数据和真实 Java API 两种模式

当 java_api_enabled=True 时，调用真实 Java 后端 API；
否则使用本地模拟数据（demo 模式）。
"""

import logging
from langchain_core.tools import tool
from app.utils.java_api_client import java_api

logger = logging.getLogger(__name__)


def _fallback_mock():
    """Java API 不可用时，回退到模拟数据"""
    from app.services.mock_data import PROGRAMS, TICKET_CATEGORIES, USERS, ORDER_COUNTER, ORDERS, MEMBERS
    return PROGRAMS, TICKET_CATEGORIES, USERS, ORDER_COUNTER, ORDERS, MEMBERS


@tool
def search_knowledge_base(query: str) -> str:
    """搜索购票规则知识库，回答退票政策、订票流程、入场规则等问题。
    当用户询问规则、政策、流程相关问题时使用此工具。

    Args:
        query: 搜索关键词，如"退票"、"订票"、"入场"
    """
    from pathlib import Path
    from app.pipelines.rag_pipeline import get_hybrid_retriever, rewrite_query
    rewritten = rewrite_query(query)
    hybrid_retrieve = get_hybrid_retriever(use_reranker=False)
    docs = hybrid_retrieve(rewritten, original_query=query)

    parts = []
    for doc in docs:
        source = Path(doc.metadata.get("source", "")).stem
        parts.append(f"[来源：{source}]\n{doc.page_content}")
    return "\n\n---\n\n".join(parts)


@tool
def search_program(city: str = "", category: str = "", actor: str = "") -> list[dict]:
    """根据城市、类型或艺人查询推荐的节目。至少提供一个查询条件。

    Args:
        city: 城市名，如"北京"、"上海"
        category: 节目类型，如"演唱会"、"音乐节"、"话剧"、"相声"
        actor: 艺人名，如"周杰伦"、"林俊杰"
    """
    # 优先使用 Java API
    if java_api.enabled:
        # 构建搜索内容（不包含城市，城市通过 area_id 查询）
        search_content = f"{category} {actor}".strip()
        result = java_api.search_program(content=search_content, city=city)
        if result and result.get("list"):
            return result["list"]
        logger.info("Java API 无结果，回退到模拟数据")

    # 回退到模拟数据
    PROGRAMS, *_ = _fallback_mock()
    results = PROGRAMS
    if city:
        results = [p for p in results if city in p.get("city", "")]
    if category:
        results = [p for p in results if category in p.get("category", "")]
    if actor:
        results = [p for p in results if actor in p.get("actor", "")]
    return results


@tool
def get_program_detail(program_id: int) -> dict | None:
    """根据节目ID查询节目详情，包括票价信息。

    Args:
        program_id: 节目ID
    """
    # 优先使用 Java API
    if java_api.enabled:
        detail = java_api.get_program_detail(program_id)
        if detail:
            tickets = java_api.get_ticket_categories(program_id)
            detail["tickets"] = tickets if tickets else []
            return detail
        logger.info("Java API 无结果，回退到模拟数据")

    # 回退到模拟数据
    PROGRAMS, TICKET_CATEGORIES, *_ = _fallback_mock()
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
    # 优先使用 Java API
    if java_api.enabled:
        tickets = java_api.get_ticket_categories(program_id)
        if tickets:
            return tickets
        logger.info("Java API 无结果，回退到模拟数据")

    # 回退到模拟数据
    _, TICKET_CATEGORIES, *_ = _fallback_mock()
    return TICKET_CATEGORIES.get(program_id, [])


@tool
def create_order(program_id: int, ticket_price: float, ticket_count: int, mobile: str) -> dict:
    """为用户生成购买节目的订单。需要先查询节目和票档信息后再调用。

    Args:
        program_id: 节目ID
        ticket_price: 票档价格
        ticket_count: 购票数量
        mobile: 用户手机号
    """
    # 优先使用 Java API
    if java_api.enabled:
        # Java API 需要 ticketCategoryId，先查票档
        tickets = java_api.get_ticket_categories(program_id)
        if tickets:
            ticket = next((t for t in tickets if t.get("price") == ticket_price), None)
            if ticket:
                result = java_api.create_order(
                    program_id=program_id,
                    ticket_category_id=ticket.get("id"),
                    ticket_count=ticket_count,
                    mobile=mobile,
                )
                if result:
                    return result
        logger.info("Java API 创建订单失败，回退到模拟数据")

    # 回退到模拟数据
    PROGRAMS, TICKET_CATEGORIES, USERS, ORDER_COUNTER, ORDERS, MEMBERS, *_ = _fallback_mock()

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

    discount = 1.0
    member_level = "非会员"
    if mobile in MEMBERS:
        member = MEMBERS[mobile]
        member_level = member["level"]
        discount = member["discount"]

    total_amount = ticket_price * ticket_count
    final_amount = total_amount * discount

    order = {
        "orderNumber": order_number,
        "programId": program_id,
        "programName": program["name"],
        "ticketName": ticket["name"],
        "price": ticket_price,
        "count": ticket_count,
        "originalAmount": total_amount,
        "memberLevel": member_level,
        "discount": discount,
        "totalAmount": round(final_amount, 2),
        "userName": user["name"],
        "mobile": mobile,
        "status": "待支付",
        "payUrl": f"http://localhost:5173/order/{order_number}",
    }

    ORDERS[order_number] = order
    return order


@tool
def query_ticket_status(program_id: int) -> dict:
    """查询指定节目的实时余票状态。

    Args:
        program_id: 节目ID，如 1 表示周杰伦演唱会-北京站
    """
    # 优先使用 Java API
    if java_api.enabled:
        detail = java_api.get_program_detail(program_id)
        tickets = java_api.get_ticket_categories(program_id)
        if detail and tickets:
            ticket_status = []
            for t in tickets:
                remain = t.get("remain", 0)
                status = "有票" if remain > 0 else "售罄"
                if 0 < remain <= 10:
                    status = f"仅剩{remain}张"
                ticket_status.append({
                    "name": t.get("name", ""),
                    "price": t.get("price", 0),
                    "remain": remain,
                    "status": status,
                })
            return {
                "program": detail.get("name", ""),
                "showTime": detail.get("showTime", ""),
                "venue": detail.get("venue", ""),
                "tickets": ticket_status,
            }
        logger.info("Java API 无结果，回退到模拟数据")

    # 回退到模拟数据
    PROGRAMS, TICKET_CATEGORIES, *_ = _fallback_mock()
    program = next((p for p in PROGRAMS if p["id"] == program_id), None)
    if not program:
        return {"error": f"节目ID {program_id} 不存在"}

    tickets = TICKET_CATEGORIES.get(program_id, [])
    ticket_status = []
    for t in tickets:
        status = "有票" if t["remain"] > 0 else "售罄"
        if 0 < t["remain"] <= 10:
            status = f"仅剩{t['remain']}张"
        ticket_status.append({
            "name": t["name"],
            "price": t["price"],
            "remain": t["remain"],
            "status": status,
        })

    return {
        "program": program["name"],
        "showTime": program["showTime"],
        "venue": program["venue"],
        "tickets": ticket_status,
    }


@tool
def check_order_status(order_number: str) -> dict:
    """根据订单号查询订单状态。

    Args:
        order_number: 订单号，如 DM10001
    """
    # 优先使用 Java API
    if java_api.enabled:
        order = java_api.get_order(order_number)
        if order:
            return order
        logger.info("Java API 无结果，回退到模拟数据")

    # 回退到模拟数据
    _, _, _, _, ORDERS, *_ = _fallback_mock()
    order = ORDERS.get(order_number)
    if not order:
        return {"error": f"订单 {order_number} 不存在，请检查订单号是否正确"}
    return order


@tool
def calculate_price(program_id: int, ticket_price: float, ticket_count: int, mobile: str = "") -> dict:
    """计算票价总价，支持会员折扣。在用户确认购买前调用此工具预估费用。

    Args:
        program_id: 节目ID
        ticket_price: 票档价格
        ticket_count: 购票数量
        mobile: 用户手机号（可选，用于查询会员折扣）
    """
    # 模拟数据模式（计算逻辑简单，不需要调 Java API）
    PROGRAMS, TICKET_CATEGORIES, _, _, _, MEMBERS, *_ = _fallback_mock()

    program = next((p for p in PROGRAMS if p["id"] == program_id), None)
    if not program:
        return {"error": "节目不存在"}

    tickets = TICKET_CATEGORIES.get(program_id, [])
    ticket = next((t for t in tickets if t["price"] == ticket_price), None)
    if not ticket:
        return {"error": f"未找到价格为{ticket_price}的票档"}

    original_price = ticket_price * ticket_count
    discount = 1.0
    member_level = "非会员"
    saved_amount = 0

    if mobile and mobile in MEMBERS:
        member = MEMBERS[mobile]
        member_level = member["level"]
        discount = member["discount"]
        saved_amount = original_price * (1 - discount)

    final_price = original_price * discount

    return {
        "program": program["name"],
        "ticketName": ticket["name"],
        "unitPrice": ticket_price,
        "count": ticket_count,
        "originalPrice": original_price,
        "memberLevel": member_level,
        "discount": discount,
        "savedAmount": round(saved_amount, 2),
        "finalPrice": round(final_price, 2),
    }


@tool
def get_recommendations(city: str = "", category: str = "", budget: float = 0) -> list[dict]:
    """根据条件推荐演出。当用户说"有什么好看的"、"推荐一下"时使用。

    Args:
        city: 城市名，如"北京"、"上海"（可选）
        category: 节目类型，如"演唱会"、"话剧"（可选）
        budget: 预算上限，单位元（可选，0表示不限预算）
    """
    # 优先使用 Java API
    if java_api.enabled:
        result = java_api.get_recommend_list()
        if result:
            return result[:5]
        logger.info("Java API 无结果，回退到模拟数据")

    # 回退到模拟数据
    PROGRAMS, TICKET_CATEGORIES, *_ = _fallback_mock()
    results = PROGRAMS

    if city:
        results = [p for p in results if city in p.get("city", "")]
    if category:
        results = [p for p in results if category in p.get("category", "")]

    if budget > 0:
        filtered = []
        for p in results:
            tickets = TICKET_CATEGORIES.get(p["id"], [])
            min_price = min((t["price"] for t in tickets), default=0)
            if min_price <= budget:
                filtered.append(p)
        results = filtered

    results = sorted(results, key=lambda x: x["id"])

    recommendations = []
    for p in results[:5]:
        tickets = TICKET_CATEGORIES.get(p["id"], [])
        min_price = min((t["price"] for t in tickets), default=0)
        max_remain = max((t["remain"] for t in tickets), default=0)
        recommendations.append({
            **p,
            "minPrice": min_price,
            "ticketStatus": "有票" if max_remain > 0 else "售罄",
        })

    return recommendations
