"""搜索节目技能"""

from app.skills.base import Skill
from app.utils.java_api_client import java_api


class SearchProgramSkill(Skill):
    """搜索节目技能"""
    
    @property
    def name(self) -> str:
        return "search_program"
    
    @property
    def description(self) -> str:
        return "根据城市、类型或艺人搜索节目。当用户想查找演出、演唱会、话剧等节目时使用。"
    
    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "城市名，如'北京'、'上海'"
                },
                "category": {
                    "type": "string",
                    "description": "节目类型，如'演唱会'、'话剧'、'音乐节'"
                },
                "actor": {
                    "type": "string",
                    "description": "艺人名，如'周杰伦'、'林俊杰'"
                }
            }
        }
    
    def execute(self, city: str = "", category: str = "", actor: str = "") -> dict:
        """执行搜索"""
        result = java_api.search_program(
            content=f"{category} {actor}".strip(),
            city=city
        )
        return result or {"totalSize": 0, "list": []}
