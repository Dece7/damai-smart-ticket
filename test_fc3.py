"""Function Calling 简单测试"""
import httpx
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

r = httpx.post(
    'http://localhost:8000/api/chat',
    json={'message': '帮我查周杰伦北京演唱会1280内场的票，买2张，手机号13800138000', 'chat_type': 'assistant'},
    timeout=180
)
print(f'Status: {r.status_code}')
tokens = []
for line in r.text.split('\n'):
    if line.startswith('data:') and line != 'data: [DONE]':
        try:
            d = json.loads(line[5:])
            t = d.get('type', '')
            if t == 'tool_result':
                print(f'\n[Tool] {d["tool"]}: {json.dumps(d["content"], ensure_ascii=False)[:200]}')
            elif t == 'thinking':
                print(f'\n[Thinking] {d["content"]}')
            elif t == 'token':
                tokens.append(d['content'])
            elif t == 'error':
                print(f'\n[Error] {d["content"]}')
        except:
            pass
print('\n' + ''.join(tokens))
