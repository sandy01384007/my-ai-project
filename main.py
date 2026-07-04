import os
from dotenv import load_dotenv
from openai import OpenAI
import pandas as pd

# 加载环境变量
load_dotenv()

# 初始化 OpenAI 客户端
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def chat_with_gpt(prompt: str) -> str:
    """与 GPT 对话"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # 性价比高的模型
            messages=[{"role": "user", "content": prompt}]
            temperature=0.7,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"错误: {str(e)}"

# 测试示例
if __name__ == "__main__":
    print("🤖 AI 项目启动成功！")
    user_input = input("请输入你的问题: ")
    response = chat_with_gpt(user_input)
    print("\nAI 回复:", response)
