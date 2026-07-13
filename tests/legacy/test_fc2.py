"""Function Calling 完整下单流程测试"""
import httpx
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

def test_chat(message: str):
    print(f"\n{'='*50}")
    print(f"用户: {message}")
    print(f"{'='*50}")
    r = httpx.post(
        'http://localhost:8000/api/chat',
        json={'message': message, 'chat_type': 'assistant'},
        timeout=120
    )
    tokens = []
    for line in r.text.split('\n'):
        if line.startswith('data:') and line != 'data: [DONE]':
            try:
                d = json.loads(line[5:])
                t = d.get('type', '')
                if t == 'tool_result':
                    print(f'\n[Tool] {d["tool"]}')
                elif t == 'thinking':
                    print(f'\n[Thinking] {d["content"]}')
                elif t == 'token':
                    tokens.append(d['content'])
            except:
                pass
    print(f"\n{'─'*50}")
    print(''.join(tokens))


if __name__ == '__main__':
    test_chat("我想买周杰伦北京演唱会的票，1280的内场，买2张，手机号13800138000")
