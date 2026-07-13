"""Function Calling 测试脚本"""
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
    test_chat("北京有什么演唱会")
    test_chat("周杰伦演唱会有什么票档")
