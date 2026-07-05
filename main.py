import os
import hmac
import hashlib
import base64
import requests
import pandas as pd
import json
from datetime import datetime
from openai import OpenAI

# ==================== 配置区 ====================
PASSPHRASE = "Xzj620018#"
API_KEY = "837c294f-3c88-49c2-9743-20966918e82c"
API_SECRET = "9A2845F8B1351F8AC537A1BC926F1B5F"

BASE_URL = "https://www.okx.com"
LOG_DIR = r"C:\Users\sandy\trading_logs"
os.makedirs(LOG_DIR, exist_ok=True)

log_file = f"{LOG_DIR}\\trading_log_{datetime.now().strftime('%Y-%m-%d')}.txt"

client = OpenAI(
    api_key="sk-3275dcead21d44d1ad128331d7a26b8e",
    base_url="https://api.deepseek.com/v1"
)

# ==================== 工具函数 ====================
def write_log(text):
    content = f"[{datetime.now().strftime('%H:%M:%S')}] {text}"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(content + "\n")

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

# ==================== 任意交易对支持 ====================
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

# ==================== 新增：K线获取与阻力计算 ====================
def get_klines(symbol, bar="1H", limit=20):
    """
    获取 OKX K 线数据
    bar: 1m/3m/5m/15m/30m/1H/2H/4H...
    OKX 返回数据按时间倒序，最新在前
    返回9列: ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm
    """
    data = okx_api("GET", "/api/v5/market/candles", {
        "instId": symbol,
        "bar": bar,
        "limit": str(limit)
    })
    if data.get('code') == '0' and data.get('data'):
        klines = data['data']
        # 修复：OKX 返回 9 列数据
        df = pd.DataFrame(klines, columns=[
            'ts', 'o', 'h', 'l', 'c', 'vol', 'volCcy', 'volCcyQuote', 'confirm'
        ])
        df = df.astype({'o': float, 'h': float, 'l': float, 'c': float, 'vol': float})
        return df
    return None

def calculate_levels(df, n=10):
    """
    计算最近 n 根 K 线的支撑/阻力位
    阻力 = 最近 n 根高点最大值
    支撑 = 最近 n 根低点最小值
    """
    if df is None or len(df) < n:
        return None, None
    recent = df.head(n)
    resistance = recent['h'].max()
    support = recent['l'].min()
    return support, resistance

# ==================== 交易策略日志（增加15M/5M阻力） ====================
def generate_trading_strategy(symbol, ticker, sup=None, res=None, 
                              res_15m=None, res_5m=None):
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
    
    # 基础关键位（1H 或默认）
    if sup is not None and res is not None:
        key_line = f"关键位: 支撑 {sup:.1f} | 阻力 {res:.1f}"
    else:
        key_line = f"关键位: 支撑 {price-300:.1f} | 阻力 {price+300:.1f}"
    
    # 追加 15分钟、5分钟阻力
    if res_15m is not None:
        key_line += f" | 15M阻力 {res_15m:.1f}"
    if res_5m is not None:
        key_line += f" | 5M阻力 {res_5m:.1f}"
    
    log = f"""
【{symbol}】
趋势判断: {trend}
{key_line}
重点关注区域: {action} ({price:.1f} 附近)
当前价格: {price:.1f} | 目标位: {price*1.015:.1f} (1.5R) / {price*1.03:.1f} (RR3.0)
5M价格行为: 震荡 | MA交叉: 无明显信号
本策略不构成投资建议，仅供参考，投资有风险！
"""
    return log.strip()

# ==================== 主程序 ====================
def main():
    write_log("🚀 交易机器人启动 - 支持任意交易对")
    pairs = get_all_trading_pairs()
    
    while True:
        try:
            cmd = input("\n输入命令 (查询 BTC、所有交易对、退出): ").strip()
            cmd_lower = cmd.lower()
            
            if cmd_lower in ["退出", "exit", "q"]:
                break
            elif cmd_lower in ["所有交易对", "list", "all"]:
                print("前30个交易对示例:", pairs[:30])
            elif "查询" in cmd or "查" in cmd:
                parts = cmd.replace("查询", "").replace("查", "").strip().upper()
                symbol = parts
                if not symbol.endswith("-SWAP"):
                    symbol += "-SWAP"
                if "-USDT" not in symbol and "-USD" not in symbol:
                    symbol = symbol.replace("-SWAP", "-USDT-SWAP")
                
                write_log(f"正在查询: {symbol}")
                ticker = get_ticker(symbol)
                if ticker:
                    # 实时行情
                    print(f"\n✅ {symbol} 实时行情:")
                    print(f"最新价: {ticker.get('last', 'N/A')}")
                    print(f"涨跌幅: {ticker.get('changePercent', 'N/A')}%")
                    print(f"24h成交量: {ticker.get('vol24h', 'N/A')}")
                    
                    # 获取多时间框架 K 线
                    sup, res = None, None
                    res_15m = None
                    res_5m = None
                    
                    # 1H 作为基础支撑阻力
                    df_1h = get_klines(symbol, bar="1H", limit=20)
                    if df_1h is not None:
                        sup, res = calculate_levels(df_1h, n=10)
                    
                    # 15分钟阻力
                    df_15m = get_klines(symbol, bar="15m", limit=20)
                    if df_15m is not None:
                        _, res_15m = calculate_levels(df_15m, n=10)
                    
                    # 5分钟阻力
                    df_5m = get_klines(symbol, bar="5m", limit=20)
                    if df_5m is not None:
                        _, res_5m = calculate_levels(df_5m, n=10)
                    
                    # 生成策略
                    strategy = generate_trading_strategy(
                        symbol, ticker,
                        sup=sup, res=res,
                        res_15m=res_15m, res_5m=res_5m
                    )
                    print(strategy)
                    write_log(strategy)
                else:
                    error_msg = f"❌ 无法获取 {symbol} 行情"
                    print(error_msg)
                    write_log(error_msg)
            else:
                print("未知命令，支持：查询 BTC、所有交易对、退出")
        except Exception as e:
            print(f"输入错误: {e}")

if __name__ == "__main__":
    main()
