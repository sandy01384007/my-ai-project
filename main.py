import os
import requests
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

print("🚀 OKX 交易机器人启动成功！")

# 配置
BASE_URL = "https://www.okx.com"

def write_log(text):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {text}")

def okx_api(path, params=None):
    url = BASE_URL + path
    try:
        resp = requests.get(url, params=params, timeout=10)
        return resp.json()
    except Exception as e:
        write_log(f"API请求失败: {e}")
        return None

def get_ticker(symbol):
    data = okx_api("/api/v5/market/ticker", {"instId": symbol})
    if data and data.get('code') == '0' and data.get('data'):
        return data['data'][0]
    return None

def main():
    write_log("支持命令：查询 BTC-USDT-SWAP、所有交易对、退出")
    
    while True:
        try:
            cmd = input("\n请输入命令: ").strip()
            if not cmd:
                continue
                
            cmd_lower = cmd.lower()
            
            if cmd_lower in ["退出", "exit", "q"]:
                write_log("机器人已停止")
                break
                
            elif cmd_lower in ["所有交易对", "list", "all"]:
                write_log("正在获取交易对列表...")
                data = okx_api("/api/v5/public/instruments", {"instType": "SWAP"})
                if data and data.get('code') == '0':
                    pairs = [item['instId'] for item in data['data'][:20]]
                    write_log(f"前20个永续合约示例: {pairs}")
                else:
                    write_log("获取失败")
                    
            elif "查询" in cmd or "查" in cmd:
                symbol = cmd.replace("查询", "").replace("查", "").strip().upper()
                if not symbol.endswith("-SWAP"):
                    symbol += "-USDT-SWAP"
                
                write_log(f"查询 {symbol} ...")
                ticker = get_ticker(symbol)
                
                if ticker:
                    price = float(ticker.get('last', 0))
                    change = float(ticker.get('changePercent', 0))
                    write_log(f"✅ {symbol} 最新价: {price} | 涨跌幅: {change}%")
                else:
                    write_log(f"❌ 无法获取 {symbol} 数据")
            else:
                write_log("未知命令")
                
        except Exception as e:
            write_log(f"错误: {e}")

if __name__ == "__main__":
    main()
