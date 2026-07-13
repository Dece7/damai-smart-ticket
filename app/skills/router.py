"""Router路由器"""

import json
import logging
from typing import Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from app.core.config import get_settings
from app.skills.base import Skill

logger = logging.getLogger(__name__)

# Router提示词模板
ROUTER_PROMPT = """你是一个智能客服路由器。你的任务是理解用户的问题，然后从可用的技能中选择最合适的技能来回答。

## 可用技能

{skills_description}

## 用户问题

{user_message}

## 输出要求

请以JSON格式输出，包含以下字段：
1. "skill": 选择的技能名称
2. "parameters": 技能需要的参数（对象格式）
3. "confidence": 选择的置信度（0-1）

示例输出：
{{"skill": "search_program", "parameters": {{"city": "北京", "category": "演唱会"}}, "confidence": 0.95}}

如果用户的问题不属于任何技能范围，请输出：
{{"skill": "none", "parameters": {{}}, "confidence": 0.0}}
"""


class Router:
    """路由器"""
    
    def __init__(self, skills: dict[str, Skill]):
        self.skills = skills
        settings = get_settings()
        self.llm = ChatOpenAI(
            api_key=settings.mimo_api_key,
            base_url=settings.mimo_base_url,
            model=settings.mimo_model,
            temperature=0,
        )
    
    def _build_skills_description(self) -> str:
        """构建技能描述"""
        descriptions = []
        for name, skill in self.skills.items():
            descriptions.append(f"### {skill.name}\n{skill.description}\n参数: {skill.parameters}")
        return "\n\n".join(descriptions)
    
    def route(self, user_message: str) -> tuple[Optional[str], dict, float]:
        """路由到合适的技能
        
        Returns:
            (skill_name, parameters, confidence)
        """
        # 构建提示词
        prompt = ROUTER_PROMPT.format(
            skills_description=self._build_skills_description(),
            user_message=user_message
        )
        
        # 调用LLM
        response = self.llm.invoke([
            SystemMessage(content="你是一个技能路由器，只输出JSON格式的结果。"),
            HumanMessage(content=prompt)
        ])
        
        # 解析响应
        try:
            # 提取JSON
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            result = json.loads(content.strip())
            
            skill_name = result.get("skill")
            parameters = result.get("parameters", {})
            confidence = result.get("confidence", 0.0)
            
            if skill_name == "none":
                return None, {}, 0.0
            
            return skill_name, parameters, confidence
            
        except Exception as e:
            logger.error(f"Router解析失败: {e}")
            return None, {}, 0.0
    
    def execute(self, user_message: str) -> dict:
        """执行完整的路由和执行流程"""
        # 1. 路由
        skill_name, parameters, confidence = self.route(user_message)
        
        if not skill_name:
            return {
                "type": "error",
                "message": "抱歉，我无法理解您的问题。请尝试重新描述您的需求。"
            }
        
        # 2. 检查技能是否存在
        if skill_name not in self.skills:
            return {
                "type": "error",
                "message": f"抱歉，技能 {skill_name} 不存在。"
            }
        
        # 3. 执行技能
        skill = self.skills[skill_name]
        try:
            result = skill.execute(**parameters)
            return {
                "type": "success",
                "skill": skill_name,
                "confidence": confidence,
                "result": result
            }
        except Exception as e:
            logger.error(f"技能执行失败: {e}")
            return {
                "type": "error",
                "message": f"抱歉，执行技能时出现错误：{str(e)}"
            }

