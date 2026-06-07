"""Prompt 注入防护模块

检测并拦截常见的 Prompt 注入攻击：
- 角色劫持：试图让 AI 扮演其他角色
- 指令覆盖：试图修改系统提示词
- 提示词泄露：试图获取系统提示词内容
"""

import re
import logging

logger = logging.getLogger(__name__)

# 常见注入模式（正则）
INJECTION_PATTERNS = [
    r"忽略(之前|上面|以上|所有)(的)?(指令|规则|提示|要求)",
    r"ignore\s+(previous|above|all)\s+(instructions|rules|prompts)",
    r"你现在(是|扮演|成为)",
    r"you\s+are\s+now",
    r"从现在起(你|你将)",
    r"from\s+now\s+on\s+you",
    r"(输出|显示|告诉我|打印)(你的|系统|初始)(提示词?|prompt|指令|规则)",
    r"(show|print|output|reveal|tell)\s+(me\s+)?(your|the|system)\s+(prompt|instructions|rules)",
    r"(假装|假设|想象)(你(是|没有|没有限制))",
    r"(pretend|imagine|assume)\s+(you\s+(are|have\s+no|are\s+not))",
    r"DAN\s*模式",
    r"(进入|切换到|activate)\s*(开发者|开发者模式|调试|debug)\s*模式",
    r"(developer|debug|admin)\s*mode",
    r"绕过(限制|规则|安全|过滤)",
    r"bypass\s+(restrictions|rules|safety|filters)",
    r"(删除|禁用|取消)(安全|限制|过滤|规则)",
    r"(disable|remove|cancel)\s+(safety|restrictions|filters|rules)",
]

# 编译正则，提高性能
COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]


def check_injection(text: str) -> tuple[bool, str]:
    """检测输入是否包含 Prompt 注入

    Returns:
        (is_inject, reason): 是否注入，原因
    """
    for pattern in COMPILED_PATTERNS:
        match = pattern.search(text)
        if match:
            reason = f"检测到可疑指令：'{match.group()}'"
            logger.warning(f"Prompt 注入检测: {reason} | 输入: {text[:100]}")
            return True, reason
    return False, ""


def sanitize_input(text: str, max_length: int = 2000) -> str:
    """清理用户输入"""
    # 截断过长输入
    if len(text) > max_length:
        text = text[:max_length]
    # 去除首尾空白
    text = text.strip()
    return text
