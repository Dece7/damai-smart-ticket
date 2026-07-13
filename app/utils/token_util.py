"""Token解析工具"""

import json
import logging
import base64
from typing import Optional

logger = logging.getLogger(__name__)

# 全栈项目的tokenSecret
TOKEN_SECRET = "CSYZWECHAT"


def parse_token(token: str) -> Optional[dict]:
    """解析JWT Token，获取用户信息
    
    Args:
        token: JWT Token字符串
        
    Returns:
        用户信息字典，包含userId等字段
    """
    try:
        # JWT Token由三部分组成：header.payload.signature
        parts = token.split('.')
        if len(parts) != 3:
            logger.warning("Token格式错误")
            return None
        
        # 解析payload部分
        payload = parts[1]
        
        # Base64解码
        # 添加padding
        payload += '=' * (4 - len(payload) % 4)
        payload_bytes = base64.urlsafe_b64decode(payload)
        payload_json = json.loads(payload_bytes.decode('utf-8'))
        
        # 获取subject字段（用户信息）
        subject = payload_json.get('sub')
        if subject:
            user_info = json.loads(subject)
            return user_info
        
        return None
    except Exception as e:
        logger.error(f"解析Token失败: {e}")
        return None


def get_user_id_from_token(token: str) -> Optional[int]:
    """从Token中获取用户ID
    
    Args:
        token: JWT Token字符串
        
    Returns:
        用户ID
    """
    user_info = parse_token(token)
    if user_info:
        return user_info.get('userId')
    return None
