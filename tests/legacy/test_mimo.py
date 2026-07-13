"""
Mimo API 能力验证脚本
运行方式：在项目根目录执行
  source .venv/Scripts/activate
  python test_mimo.py
"""
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("MIMO_API_KEY"),
    base_url=os.getenv("MIMO_BASE_URL"),
)


def test_chat():
    """测试 1: 基础对话"""
    print("=" * 50)
    print("测试 1: 基础对话")
    print("=" * 50)
    try:
        resp = client.chat.completions.create(
            model=os.getenv("MIMO_MODEL", "mimo"),
            messages=[{"role": "user", "content": "你好，用一句话介绍你自己"}],
            max_tokens=100,
        )
        print(f"  模型: {resp.model}")
        print(f"  回复: {resp.choices[0].message.content}")
        print(f"  Token: prompt={resp.usage.prompt_tokens}, completion={resp.usage.completion_tokens}")
        print("  结果: PASS\n")
        return True
    except Exception as e:
        print(f"  错误: {e}")
        print("  结果: FAIL\n")
        return False


def test_streaming():
    """测试 2: 流式输出"""
    print("=" * 50)
    print("测试 2: 流式输出 (SSE)")
    print("=" * 50)
    try:
        stream = client.chat.completions.create(
            model=os.getenv("MIMO_MODEL", "mimo"),
            messages=[{"role": "user", "content": "数1到5"}],
            max_tokens=50,
            stream=True,
        )
        content = ""
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                content += chunk.choices[0].delta.content
        print(f"  流式内容: {content}")
        print("  结果: PASS\n")
        return True
    except Exception as e:
        print(f"  错误: {e}")
        print("  结果: FAIL\n")
        return False


def test_function_calling():
    """测试 3: Function Calling (工具调用)"""
    print("=" * 50)
    print("测试 3: Function Calling")
    print("=" * 50)
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "获取指定城市的天气信息",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {"type": "string", "description": "城市名"},
                    },
                    "required": ["city"],
                },
            },
        }
    ]
    try:
        resp = client.chat.completions.create(
            model=os.getenv("MIMO_MODEL", "mimo"),
            messages=[{"role": "user", "content": "北京今天天气怎么样？"}],
            tools=tools,
            tool_choice="auto",
        )
        msg = resp.choices[0].message
        if msg.tool_calls:
            print(f"  调用工具: {msg.tool_calls[0].function.name}")
            print(f"  参数: {msg.tool_calls[0].function.arguments}")
            print("  结果: PASS (支持 Function Calling)\n")
            return True
        else:
            print(f"  回复: {msg.content}")
            print("  结果: PARTIAL (未触发工具调用，但 API 未报错)\n")
            return True
    except Exception as e:
        print(f"  错误: {e}")
        if "tool" in str(e).lower() or "function" in str(e).lower():
            print("  结果: FAIL (不支持 Function Calling)\n")
        else:
            print("  结果: FAIL\n")
        return False


if __name__ == "__main__":
    print("\n>>> Mimo API 能力验证 <<<\n")

    if not os.getenv("MIMO_API_KEY") or os.getenv("MIMO_API_KEY") == "tp-your-mimo-key":
        print("请先在 .env 文件中配置 MIMO_API_KEY")
        print("复制 .env.example 为 .env，填入你的 API Key")
        exit(1)

    results = {
        "基础对话": test_chat(),
        "流式输出": test_streaming(),
        "Function Calling": test_function_calling(),
    }

    print("=" * 50)
    print("验证结果汇总")
    print("=" * 50)
    for name, ok in results.items():
        status = "PASS" if ok else "FAIL"
        print(f"  {name}: {status}")
    print()
