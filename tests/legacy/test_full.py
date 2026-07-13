"""全面测试脚本"""
import httpx
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

BASE = "http://localhost:8000/api"
PASS = 0
FAIL = 0


def test(name, func):
    global PASS, FAIL
    try:
        ok = func()
        status = "PASS" if ok else "FAIL"
        if ok:
            PASS += 1
        else:
            FAIL += 1
    except Exception as e:
        status = f"FAIL ({e})"
        FAIL += 1
    print(f"  [{status}] {name}")


def chat(message, conv_id=None, chat_type="assistant"):
    r = httpx.post(f"{BASE}/chat", json={
        "message": message,
        "conversation_id": conv_id,
        "chat_type": chat_type,
    }, timeout=120)
    cid, tokens, tools = conv_id, [], []
    for line in r.text.split('\n'):
        if line.startswith('data:') and line != 'data: [DONE]':
            try:
                d = json.loads(line[5:])
                if d.get('type') == 'conversation_id':
                    cid = d['content']
                elif d.get('type') == 'token':
                    tokens.append(d['content'])
                elif d.get('type') == 'thinking':
                    tools.append(d['content'])
            except:
                pass
    return r.status_code, cid, ''.join(tokens), tools


def agent(message, conv_id=None):
    r = httpx.post(f"{BASE}/agent", json={
        "message": message,
        "conversation_id": conv_id,
    }, timeout=120)
    cid, tokens, tools = conv_id, [], []
    for line in r.text.split('\n'):
        if line.startswith('data:') and line != 'data: [DONE]':
            try:
                d = json.loads(line[5:])
                if d.get('type') == 'conversation_id':
                    cid = d['content']
                elif d.get('type') == 'token':
                    tokens.append(d['content'])
                elif d.get('type') == 'thinking':
                    tools.append(d['content'])
            except:
                pass
    return r.status_code, cid, ''.join(tokens), tools


print("=" * 60)
print("全面测试")
print("=" * 60)

# 1. 基础接口
print("\n[基础接口]")
test("根路径返回 HTML", lambda: httpx.get(f"http://localhost:8000/", timeout=5).status_code == 200)
test("Scalar 文档页", lambda: httpx.get(f"http://localhost:8000/scalar", timeout=5).status_code == 200)
test("对话列表接口", lambda: httpx.get(f"{BASE}/conversations", timeout=5).status_code == 200)

# 2. 贴心助手（Function Calling）
print("\n[贴心助手 - Function Calling]")
sc, cid, txt, tools = chat("北京有什么演唱会")
test("FC: 查询节目", lambda: sc == 200 and (len(txt) > 0 or len(tools) > 0))
test("FC: 调用了工具", lambda: len(tools) > 0)

sc2, cid2, txt2, tools2 = chat("第一个演出的票档价格", conv_id=cid)
test("FC: 多轮对话（带 conversation_id）", lambda: sc2 == 200 and len(txt2) > 0)

# 3. 规则助手（RAG）
print("\n[规则助手 - RAG]")
sc, _, txt, _ = chat("怎么退票", chat_type="rag")
test("RAG: 退票政策问答", lambda: sc == 200 and len(txt) > 10)

sc, _, txt, _ = chat("儿童票怎么买", chat_type="rag")
test("RAG: 儿童票问答", lambda: sc == 200 and len(txt) > 10)

# 4. Agent 模式
print("\n[Agent 模式]")
sc, cid, txt, tools = agent("北京有什么演唱会")
test("Agent: 查询节目", lambda: sc == 200 and len(txt) > 10)
test("Agent: 调用了工具", lambda: len(tools) > 0)

sc2, cid2, txt2, tools2 = agent("怎么退票")
test("Agent: RAG 检索", lambda: sc2 == 200 and len(txt2) > 10)

sc3, cid3, txt3, tools3 = agent("帮我查周杰伦演唱会的票，顺便告诉我退票政策")
test("Agent: 混合场景", lambda: sc3 == 200 and len(tools3) >= 2)

# 5. 连续对话（核心 bug 测试）
print("\n[连续对话 - 核心 bug 测试]")
sc1, cid, t1, _ = agent("北京有什么演唱会")
sc2, _, t2, _ = agent("第一个多少钱", conv_id=cid)
sc3, _, t3, _ = agent("帮我买一张", conv_id=cid)
test("连续 3 轮 Agent 对话", lambda: sc1 == 200 and sc2 == 200 and sc3 == 200 and len(t1) > 0 and len(t2) > 0)

# 6. 对话管理
print("\n[对话管理]")
convs = httpx.get(f"{BASE}/conversations", timeout=5).json()
test("对话列表有数据", lambda: len(convs) > 0)
if convs:
    cid = convs[0]['id']
    msgs = httpx.get(f"{BASE}/conversations/{cid}/messages", timeout=5).json()
    test("历史消息有数据", lambda: len(msgs) > 0)

# 7. 边界情况
print("\n[边界情况]")
sc, _, txt, _ = chat("", chat_type="assistant")
test("空消息处理", lambda: sc == 422)  # 应该返回 422

print(f"\n{'=' * 60}")
print(f"测试结果: {PASS} 通过, {FAIL} 失败")
print(f"{'=' * 60}")
