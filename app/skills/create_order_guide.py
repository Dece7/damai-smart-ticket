"""下单引导技能"""

from app.skills.base import Skill
from app.utils.java_api_client import java_api


class CreateOrderGuideSkill(Skill):
    """下单引导技能"""
    
    @property
    def name(self) -> str:
        return "create_order_guide"
    
    @property
    def description(self) -> str:
        return "引导用户购买节目票。当用户想要买票、购票时使用。直接返回购票链接，不询问用户信息。"
    
    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "program_id": {
                    "type": "integer",
                    "description": "节目ID"
                }
            },
            "required": ["program_id"]
        }
    
    def execute(self, program_id: int) -> dict:
        """执行下单引导"""
        # 查询节目详情
        program = java_api.get_program_detail(program_id)
        if not program:
            return {"error": "未找到该节目信息"}
        
        # 查询票档信息
        tickets = java_api.get_ticket_categories(program_id) or []
        
        # 生成购票链接
        buy_url = f"http://localhost:5173/contentDetail/index/{program_id}"
        
        return {
            "type": "buy_guide",
            "program_title": program.get("title", ""),
            "show_time": program.get("showTime", ""),
            "place": program.get("place", ""),
            "price_range": f"¥{tickets[0].get('price', '0')}起" if tickets else "价格待定",
            "buy_url": buy_url,
            "ticket_count": len(tickets),
        }
