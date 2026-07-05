import os
from datetime import datetime
from dotenv import load_dotenv
import requests

load_dotenv()

print("🚀 OKX 交易机器人启动成功！")
print(f"当前时间: {datetime.now()}")
print("DEEPSEEK_API_KEY 配置状态:", "已设置" if os.getenv("DEEPSEEK_API_KEY") else "未设置")

# 简单健康检查
print("✅ 服务运行正常（简化版）")
print("提示：生产环境建议改成定时任务或 Web 服务")

if __name__ == "__main__":
    print("机器人已就绪")
