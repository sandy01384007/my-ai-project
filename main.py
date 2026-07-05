import os
import hmac
import hashlib
import base64
import requests
import json
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# ==================== 配置区 ====================
PASSPHRASE = os.getenv("OKX_PASSPHRASE")
API_KEY = os.getenv("OKX_API_KEY")
API_SECRET = os.getenv("OKX_API_SECRET")

BASE_URL = "https://www.okx.com"

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com/v1"
)

# ==================== 工具函数 ====================
def write_log(text):
    content = f"[{datetime.now().strftime('%H:%M:%S')}] {text}"
    print(content)  # Railway 使用 print 输出日志

def get_okx_signature(timestamp, method, path, body="", secret=API_SECRET):
    if isinstance(body, dict):
        body_str = json.dumps(body)
    else:
        body_str = str(body) if body else ""
    msg = timestamp + method + path + body_str
    sign = hmac.new(bytes(secret, "utf-8"), bytes(msg, "utf-8"), hashlib.sha256).digest()
    return base64.b64encode(sign).decode()

def okx_api(method, path, body=None):
    timestamp = datetime.utcnow().isoformat()[:-3] + "Z"
    body_str = json.dumps(body) if isinstance(body, dict) else (str(body) if body else "")
    signature = get_okx_signature(timestamp, method, path, body_str)
    
    headers = {
        "OK-ACCESS-KEY": API_KEY,
        "OK-ACCESS-SIGN": signature,
        "OK-ACCESS-TIMESTAMP": timestamp,
        "OK-ACCESS-PASSPHRASE": PASSPHRASE,
        "Content-Type": "application/json"
    }
    url = BASE_URL + path
    try:
        if method == "GET":
            resp = requests.get(url, headers=headers, params=body)
        else:
            resp = requests.request(method, url, headers=headers, json=body)
        return resp.json()
    except Exception as e:
        write_log(f"API请求错误: {e}")
        return {"code": "-1", "msg": str(e)}

# ==================== 主程序 ====================
def main():
    write_log("🚀 OKX 交易机器人启动 - 支持任意交易对")
    
    # 测试 API
    write_log("正在测试 OKX 连接...")
    # 这里可以添加更多启动逻辑
    
    write_log("✅ 机器人已启动（命令行交互版适合本地，Railway 上建议改成定时任务）")

if __name__ == "__main__":
    main()
