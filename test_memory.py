"""会话记忆测试"""
import httpx
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

BASE = "http://localhost:8000/api"


def chat(message, conversation_id=None):
    r = httpx.post(f"{BASE}/chat", json={
        "message": message,
        "conversation_id": conversation_id,
        "chat_type": "assistant",
    }, timeout=120)
    conv_id = conversation_id
    tokens = []
    for line in r.text.split('\n'):
        if line.startswith('data:') and line != 'data: [DONE]':
            try:
                d = json.loads(line[5:])
                if d.get('type') == 'conversation_id':
                    conv_id = d['content']
                elif d.get('type') == 'token':
                    tokens.append(d['content'])
            except:
                pass
    return conv_id, ''.join(tokens)


print("=" * 50)
print("测试：多轮对话记忆")
print("=" * 50)

# 第一轮
conv_id, answer = chat("北京有什么演唱会")
print(f"\n[第1轮] 用户: 北京有什么演唱会")
print(f"[第1轮] AI: {answer[:100]}...")
print(f"[第1轮] 对话ID: {conv_id}")

# 第二轮（同一对话）
conv_id, answer = chat("第一个演出的票档价格是多少", conversation_id=conv_id)
print(f"\n[第2轮] 用户: 第一个演出的票档价格是多少")
print(f"[第2轮] AI: {answer[:100]}...")
print(f"[第2轮] 对话ID: {conv_id}")

# 查看对话列表
r = httpx.get(f"{BASE}/conversations")
print(f"\n对话列表: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")

# 查看历史消息
r = httpx.get(f"{BASE}/conversations/{conv_id}/messages")
msgs = r.json()
print(f"\n历史消息 ({len(msgs)} 条):")
for m in msgs:
    print(f"  [{m['role']}] {m['content'][:50]}...")
