"""Router-Skill 智能助手服务"""

import json
import logging
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from app.core.config import get_settings
from app.skills import router
from app.services.memory_service import memory_service
from app.utils.java_api_client import java_api

logger = logging.getLogger(__name__)


class RouterSkillService:
    """Router-Skill 智能助手服务"""
    
    def __init__(self):
        settings = get_settings()
        self.llm = ChatOpenAI(
            api_key=settings.mimo_api_key,
            base_url=settings.mimo_base_url,
            model=settings.mimo_model,
            streaming=True,
            stream_usage=True,
        )
    
    async def chat(self, message: str, conversation_id: str | None, user_id: int = None):
        """Router-Skill 对话"""
        # 创建或获取对话
        if not conversation_id:
            conv = memory_service.create_conversation("router_skill", user_id=user_id)
            conversation_id = str(conv.id)
            yield f'data: {json.dumps({"type": "conversation_id", "content": conversation_id}, ensure_ascii=False)}\n\n'
        
        # 保存用户消息
        memory_service.save_message(int(conversation_id), "user", message)
        
        # 执行路由
        result = router.execute(message)
        
        if result["type"] == "success":
            # 让LLM生成更好的回复
            skill = result["skill"]
            data = result["result"]
            
            # 构建提示词
            prompt = self._build_prompt(message, skill, data)
            
            # 流式生成回复
            full_response = ""
            async for chunk in self.llm.astream([HumanMessage(content=prompt)]):
                if chunk.content:
                    full_response += chunk.content
                    yield f'data: {json.dumps({"type": "token", "content": chunk.content}, ensure_ascii=False)}\n\n'
            
            # 保存助手回复
            memory_service.save_message(int(conversation_id), "assistant", full_response)
        else:
            # 错误回复
            error_msg = result["message"]
            yield f'data: {json.dumps({"type": "token", "content": error_msg}, ensure_ascii=False)}\n\n'
            memory_service.save_message(int(conversation_id), "assistant", error_msg)
    
    def _build_prompt(self, user_message: str, skill: str, data: dict) -> str:
        """构建提示词"""
        if skill == "search_program":
            return self._build_search_prompt(user_message, data)
        elif skill == "get_order_list":
            return self._build_order_list_prompt(user_message, data)
        elif skill == "create_order_guide":
            return self._build_order_guide_prompt(user_message, data)
        elif skill == "search_knowledge_base":
            return self._build_knowledge_prompt(user_message, data)
        else:
            return f"用户问题：{user_message}\n\n请根据以下数据生成回复：\n{json.dumps(data, ensure_ascii=False)}"
    
    def _build_knowledge_prompt(self, user_message: str, data: dict) -> str:
        """构建知识库搜索提示词"""
        answer = data.get("answer", "")
        
        if not answer:
            return f"用户问题：{user_message}\n\n抱歉，未找到相关信息。请建议用户换个方式提问，或者联系人工客服。"
        
        return f"""用户问题：{user_message}

根据知识库查询，找到以下相关信息：

{answer}

请用友好的语气回复用户，直接回答用户的问题。如果信息不够完整，可以建议用户换个方式提问或联系人工客服。"""
    
    def _build_search_prompt(self, user_message: str, data: dict) -> str:
        """构建搜索结果提示词"""
        total = data.get("totalSize", 0)
        items = data.get("list", [])
        
        if total == 0:
            return f"用户问题：{user_message}\n\n抱歉，未找到相关节目。请推荐其他节目或建议用户换个搜索条件。"
        
        # 格式化节目列表
        programs = []
        for i, item in enumerate(items[:10], 1):
            title = item.get("title", "")
            actor = item.get("actor", "")
            place = item.get("place", "")
            show_time = item.get("showTime", "")
            programs.append(f"{i}. {title}（{actor}）- {place} - {show_time}")
        
        programs_text = "\n".join(programs)
        
        return f"""用户问题：{user_message}

根据查询结果，找到了 {total} 个节目：

{programs_text}

请用友好的语气回复用户，可以用表格形式展示节目信息，让用户更容易阅读。如果用户表达了购票意图，请引导用户选择具体的节目。"""
    
    def _build_order_list_prompt(self, user_message: str, data: dict) -> str:
        """构建订单列表提示词"""
        total = data.get("total", 0)
        items = data.get("list", [])
        
        if total == 0:
            return f"用户问题：{user_message}\n\n用户还没有订单记录。"
        
        # 格式化订单列表
        orders = []
        for i, item in enumerate(items[:5], 1):
            order_no = item.get("orderNumber", "")
            title = item.get("programTitle", "")
            status = item.get("orderStatus", "")
            orders.append(f"{i}. 订单号: {order_no} - {title} - 状态: {status}")
        
        orders_text = "\n".join(orders)
        
        return f"""用户问题：{user_message}

用户共有 {total} 个订单：

{orders_text}

请用友好的语气回复用户，清晰地展示订单信息。"""
    
    def _build_order_guide_prompt(self, user_message: str, data: dict) -> str:
        """构建下单引导提示词"""
        title = data.get("program_title", "")
        place = data.get("place", "")
        show_time = data.get("show_time", "")
        price_range = data.get("price_range", "")
        buy_url = data.get("buy_url", "")
        
        return f"""用户问题：{user_message}

已为用户找到购票信息：

节目名称：{title}
演出地点：{place}
演出时间：{show_time}
票价范围：{price_range}
购票链接：{buy_url}

请用友好的语气回复用户，并在回复中包含以下HTML格式的购票卡片：

<div style="background: linear-gradient(135deg, #667eea15 0%, #764ba215 100%); border: 1px solid #667eea30; border-radius: 12px; padding: 20px; margin: 12px 0;">
  <div style="display: flex; align-items: center; margin-bottom: 12px;">
    <span style="font-size: 20px; margin-right: 8px;"> </span>
    <span style="font-size: 16px; font-weight: 600; color: #1a1a1a;">{title}</span>
  </div>
  <div style="display: flex; gap: 16px; margin-bottom: 16px; font-size: 13px; color: #666;">
    <span>  {place}</span>
    <span>  {show_time}</span>
  </div>
  <div style="display: flex; justify-content: space-between; align-items: center;">
    <span style="font-size: 18px; font-weight: 600; color: #ff4757;">  {price_range}</span>
    <a href="{buy_url}" target="_blank" style="background: linear-gradient(135deg, #667eea, #764ba2); color: white; padding: 10px 28px; border-radius: 24px; text-decoration: none; font-size: 14px; font-weight: 500;">前往购票 →</a>
  </div>
</div>"""


router_skill_service = RouterSkillService()

