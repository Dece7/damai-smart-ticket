"""Agent 服务 - 整合 Agent + 会话记忆"""

import json
import logging
from app.chains.agent import run_agent
from app.services.memory_service import memory_service

logger = logging.getLogger(__name__)


class AgentService:
    async def chat(self, message: str, conversation_id: str | None):
        """Agent 对话（带会话记忆）"""
        if not conversation_id:
            conv = memory_service.create_conversation("agent")
            conversation_id = str(conv.id)
            yield f'data: {json.dumps({"type": "conversation_id", "content": conversation_id}, ensure_ascii=False)}\n\n'

        memory_service.save_message(int(conversation_id), "user", message)
        history = memory_service.get_history(int(conversation_id), max_messages=10)

        full_response = ""
        saved_sources = None
        saved_usage = None
        saved_steps = []
        async for chunk in run_agent(message, history):
            yield chunk
            if chunk.startswith("data: ") and chunk != "data: [DONE]\n\n":
                try:
                    d = json.loads(chunk[6:])
                    if d.get("type") == "token":
                        full_response += d["content"]
                    elif d.get("type") == "sources":
                        saved_sources = d["content"]
                    elif d.get("type") == "usage":
                        saved_usage = d["content"]
                    elif d.get("type") == "step":
                        saved_steps.append(d)
                except:
                    pass

        if full_response:
            memory_service.save_message(int(conversation_id), "assistant", full_response, sources=saved_sources, steps=saved_steps or None, token_usage=saved_usage)


agent_service = AgentService()
