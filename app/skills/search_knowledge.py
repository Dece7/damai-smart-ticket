"""知识库搜索技能"""

from app.skills.base import Skill
from app.pipelines.rag_pipeline import get_hybrid_retriever


class SearchKnowledgeSkill(Skill):
    """知识库搜索技能"""
    
    @property
    def name(self) -> str:
        return "search_knowledge_base"
    
    @property
    def description(self) -> str:
        return "搜索购票规则知识库。当用户询问退票政策、订票流程、入场规则等问题时使用。"
    
    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词，如'退票'、'订票'、'入场'"
                }
            },
            "required": ["query"]
        }
    
    def execute(self, query: str) -> dict:
        """执行搜索"""
        retriever = get_hybrid_retriever(use_reranker=False)
        docs = retriever(query, original_query=query)
        
        parts = []
        for doc in docs[:3]:
            parts.append(doc.page_content)
        
        return {"answer": "\n\n---\n\n".join(parts)}
