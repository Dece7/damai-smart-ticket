"""查询订单列表技能"""

from app.skills.base import Skill
from app.utils.java_api_client import java_api


class GetOrderListSkill(Skill):
    """查询订单列表技能"""
    
    @property
    def name(self) -> str:
        return "get_order_list"
    
    @property
    def description(self) -> str:
        return "查询用户的订单列表。当用户询问'我有哪些订单'、'查看我的订单'时使用。"
    
    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "用户ID（可选，不提供则使用当前登录用户的ID）"
                }
            }
        }
    
    def execute(self, user_id: int = None) -> dict:
        """执行查询"""
        if not user_id:
            user_id = java_api.get_user_id()
        result = java_api.get_order_list(user_id=user_id)
        return result or {"total": 0, "list": []}
