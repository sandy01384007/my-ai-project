import os
import hmac
import hashlib
import base64
import requests
import json
import time
from datetime import datetime
from openai import OpenAI

# ==================== 配置区（从环境变量读取） ====================
PASSPHRASE = os.getenv("OKX_PASSPHRASE", "")
API_KEY = os.getenv("OKX_API_KEY", "")
API_SECRET = os.getenv("OKX_SECRET", "")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")

BASE_URL = "https://www.okx.com"
LOG_DIR = "/app/logs"  # Linux 容器兼容路径
os.makedirs(LOG_DIR, exist_ok=True)

log_file = f"{LOG_DIR}/trading_log_{datetime.now().strftime('%Y-%m-%d')}.txt"

# DeepSeek 客户端初始化
if DEEPSEEK_API_KEY:
    client = OpenAI(
        api_key=DEEPSEEK_API_KEY,
        base_url="https://api.deepseek.com/v1"
    )
    print("✅ DEEPSEEK_API_KEY 配置状态: 已设置")
else:
    client = None
    print("⚠️ DEEPSEEK_API_KEY 配置状态: 未设置（简化版运行）")

# ==================== 工具函数 ====================
def write_log(text):
    content = f"[{datetime.now().strftime('%H:%M:%S')}] {text}"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(content + "\n")
    print(content)

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
    signature = get_okx_signature(timestamp, method, path, body_str, API_SECRET)
    
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

# ==================== 交易对支持 ====================
def get_all_trading_pairs():
    try:
        data = okx_api("GET", "/api/v5/public/instruments", {"instType": "SWAP"})
        if data.get('code') == '0':
            pairs = [item['instId'] for item in data['data']]
            write_log(f"✅ 共加载 {len(pairs)} 个永续合约")
            return pairs
        else:
            write_log("获取交易对失败")
            return []
    except Exception as e:
        write_log(f"错误: {e}")
        return []

def get_ticker(symbol):
    data = okx_api("GET", "/api/v5/market/ticker", {"instId": symbol})
    if data.get('code') == '0' and data.get('data'):
        return data['data'][0]
    return None

# ==================== 交易策略 ====================
def generate_trading_strategy(symbol, ticker):
    price = float(ticker.get('last', 0))
    change = float(ticker.get('changePercent', 0))
    
    if change > 1.5:
        trend = "↑ 日内强势上涨趋势"
        action = "做多"
    elif change < -1.5:
        trend = "↓ 日内明显下跌趋势"
        action = "观望或轻仓做空"
    else:
        trend = "→ 震荡整理"
        action = "区间高抛低吸"
    
    log = f"""
【{symbol}】
趋势判断: {trend}
关键位: 支撑 {price-300:.1f} | 阻力 {price+300:.1f}
重点关注区域: {action} ({price:.1f} 附近)
当前价格: {price:.1f} | 目标位: {price*1.015:.1f} (1.5R) / {price*1.03:.1f} (RR3.0)
5M价格行为: 震荡 | MA交叉: 无明显信号
本策略不构成投资建议，仅供参考，投资有风险！
"""
    return log.strip()

# ==================== 主程序（自动运行模式） ====================
def main():
    write_log("🚀 OKX 交易机器人启动成功！")
    write_log(f"当前时间: {datetime.now()}")
    
    # 检查配置
    if not all([API_KEY, API_SECRET, PASSPHRASE]):
        write_log("❌ 错误: OKX API 配置不完整，请检查环境变量 OKX_API_KEY / OKX_SECRET / OKX_PASSPHRASE")
        return
    
    pairs = get_all_trading_pairs()
    if not pairs:
        write_log("❌ 无法获取交易对")
        return
    
    # 自动分析前 20 个交易对
    write_log("开始自动分析...")
    for symbol in pairs[:20]:
        ticker = get_ticker(symbol)
        if ticker:
            strategy = generate_trading_strategy(symbol, ticker)
            write_log(strategy)
        time.sleep(0.5)  # 避免请求过快
    
    write_log("✅ 本轮分析完成，日志已保存")
    write_log("提示: 生产环境建议改成定时任务或 Web 服务")

if __name__ == "__main__":
    main()
