"""Skill接口定义"""

from abc import ABC, abstractmethod
from typing import Any


class Skill(ABC):
    """技能基类"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """技能名称"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """技能描述"""
        pass
    
    @property
    @abstractmethod
    def parameters(self) -> dict:
        """参数定义（JSON Schema格式）"""
        pass
    
    @abstractmethod
    def execute(self, **kwargs) -> dict:
        """执行技能"""
        pass
    
    def to_prompt(self) -> str:
        """转换为提示词格式"""
        return f"""
技能名称: {self.name}
技能描述: {self.description}
参数: {self.parameters}
"""
