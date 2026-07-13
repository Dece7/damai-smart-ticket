"""Skills模块"""

from app.skills.search_program import SearchProgramSkill
from app.skills.get_order_list import GetOrderListSkill
from app.skills.create_order_guide import CreateOrderGuideSkill
from app.skills.search_knowledge import SearchKnowledgeSkill
from app.skills.router import Router

# 注册所有技能
ALL_SKILLS = {
    "search_program": SearchProgramSkill(),
    "get_order_list": GetOrderListSkill(),
    "create_order_guide": CreateOrderGuideSkill(),
    "search_knowledge_base": SearchKnowledgeSkill(),
}

# 创建路由器
router = Router(ALL_SKILLS)

__all__ = ["ALL_SKILLS", "router", "Router"]
