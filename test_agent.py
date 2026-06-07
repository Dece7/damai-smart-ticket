"""Agent 测试 - 验证自动工具选择"""
import httpx
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

BASE = "http://localhost:8000/api"


def test_agent(message, label):
    print(f"\n{'='*50}")
    print(f"[{label}] 用户: {message}")
    print(f"{'='*50}")
    r = httpx.post(f"{BASE}/agent", json={"message": message}, timeout=120)
    tokens = []
    for line in r.text.split('\n'):
        if line.startswith('data:') and line != 'data: [DONE]':
            try:
                d = json.loads(line[5:])
                t = d.get('type', '')
                if t == 'thinking':
                    print(f'\n[Tool] {d["content"]}')
                elif t == 'tool_result':
                    print(f'  -> 结果已返回')
                elif t == 'token':
                    tokens.append(d['content'])
            except:
                pass
    print(f"\n{'─'*50}")
    print(''.join(tokens))


if __name__ == '__main__':
    # 测试 1: 应该调用 RAG 工具
    test_agent("怎么退票", "RAG 场景")

    # 测试 2: 应该调用 Function Calling 工具
    test_agent("北京有什么演唱会", "FC 场景")

    # 测试 3: 混合场景
    test_agent("帮我查一下周杰伦演唱会的票，顺便告诉我退票政策", "混合场景")
