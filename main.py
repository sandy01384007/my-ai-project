import os
import hmac
import hashlib
import base64
import requests
import json
import time
import threading
from datetime import datetime
from flask import Flask, jsonify, request
from openai import OpenAI

app = Flask(__name__)

# ==================== 配置区（从环境变量读取） ====================
PASSPHRASE = os.getenv("OKX_PASSPHRASE", "")
API_KEY = os.getenv("OKX_API_KEY", "")
API_SECRET = os.getenv("OKX_SECRET", "")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")

BASE_URL = "https://www.okx.com"
LOG_DIR = "/app/logs"
os.makedirs(LOG_DIR, exist_ok=True)

# 内存缓存（最近日志 + 分析结果）
cache = {
    "last_analysis": None,
    "last_analysis_time": None,
    "logs": []
}

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
    # 写入文件
    log_file = f"{LOG_DIR}/trading_log_{datetime.now().strftime('%Y-%m-%d')}.txt"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(content + "\n")
    # 同时存入内存缓存（保留最近200条）
    cache["logs"].append(content)
    if len(cache["logs"]) > 200:
        cache["logs"].pop(0)
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
            resp = requests.get(url, headers=headers, params=body, timeout=10)
        else:
            resp = requests.request(method, url, headers=headers, json=body, timeout=10)
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
    
    result = {
        "symbol": symbol,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "trend": trend,
        "action": action,
        "price": price,
        "change_percent": change,
        "support": round(price - 300, 1),
        "resistance": round(price + 300, 1),
        "focus_area": f"{action} ({price:.1f} 附近)",
        "target_1_5r": round(price * 1.015, 1),
        "target_rr3": round(price * 1.03, 1),
        "price_behavior_5m": "震荡",
        "ma_cross": "无明显信号",
        "disclaimer": "本策略不构成投资建议，仅供参考，投资有风险！"
    }
    
    write_log(f"【{symbol}】{trend} | 价格: {price} | 建议: {action}")
    return result

def run_batch_analysis(limit=20):
    """批量分析，返回结果列表"""
    if not all([API_KEY, API_SECRET, PASSPHRASE]):
        return {"error": "OKX API 配置不完整，请检查环境变量"}
    
    pairs = get_all_trading_pairs()
    if not pairs:
        return {"error": "无法获取交易对"}
    
    results = []
    write_log(f"开始批量分析前 {limit} 个交易对...")
    
    for symbol in pairs[:limit]:
        ticker = get_ticker(symbol)
        if ticker:
            strategy = generate_trading_strategy(symbol, ticker)
            results.append(strategy)
        time.sleep(0.3)  # 降低请求频率
    
    write_log("✅ 批量分析完成")
    
    cache["last_analysis"] = results
    cache["last_analysis_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    return {
        "analysis_time": cache["last_analysis_time"],
        "count": len(results),
        "results": results
    }

# ==================== Flask 路由 ====================

@app.route('/')
def home():
    """首页 + 健康检查"""
    return jsonify({
        "status": "running",
        "service": "OKX Trading Bot",
        "version": "2.0.0-web",
        "endpoints": {
            "健康检查": "GET /",
            "配置状态": "GET /api/status",
            "单个分析": "GET /api/analyze/<symbol>",
            "批量分析": "GET /api/analyze?limit=10",
            "最近日志": "GET /api/logs?lines=50",
            "缓存结果": "GET /api/cache"
        }
    })

@app.route('/api/status')
def status():
    """查看配置状态（脱敏）"""
    return jsonify({
        "okx_configured": all([API_KEY, API_SECRET, PASSPHRASE]),
        "deepseek_configured": DEEPSEEK_API_KEY != "",
        "api_key_preview": API_KEY[:4] + "****" if API_KEY else None,
        "last_analysis_time": cache["last_analysis_time"],
        "cached_results_count": len(cache["last_analysis"]) if cache["last_analysis"] else 0
    })

@app.route('/api/analyze', methods=['GET'])
def analyze():
    """批量分析，支持 limit 参数（默认20，最大50）"""
    if not all([API_KEY, API_SECRET, PASSPHRASE]):
        return jsonify({"code": 500, "error": "OKX API 配置不完整"}), 500
    
    limit = request.args.get('limit', 20, type=int)
    limit = min(max(limit, 1), 50)  # 限制 1-50，防止超时
    
    result = run_batch_analysis(limit=limit)
    if "error" in result:
        return jsonify({"code": 500, "error": result["error"]}), 500
    
    return jsonify({
        "code": 200,
        "message": "分析完成",
        "data": result
    })

@app.route('/api/analyze/<symbol>', methods=['GET'])
def analyze_symbol(symbol):
    """分析指定交易对（实时）"""
    if not all([API_KEY, API_SECRET, PASSPHRASE]):
        return jsonify({"code": 500, "error": "OKX API 配置不完整"}), 500
    
    ticker = get_ticker(symbol)
    if not ticker:
        return jsonify({"code": 404, "error": f"无法获取 {symbol} 的行情数据"}), 404
    
    result = generate_trading_strategy(symbol, ticker)
    return jsonify({
        "code": 200,
        "message": f"{symbol} 分析完成",
        "data": result
    })

@app.route('/api/logs', methods=['GET'])
def get_logs():
    """获取最近日志"""
    lines = request.args.get('lines', 50, type=int)
    lines = min(lines, 200)
    return jsonify({
        "code": 200,
        "count": len(cache["logs"][-lines:]),
        "logs": cache["logs"][-lines:]
    })

@app.route('/api/cache', methods=['GET'])
def get_cache():
    """获取上次批量分析的缓存结果（不调用API，秒开）"""
    return jsonify({
        "code": 200,
        "last_analysis_time": cache["last_analysis_time"],
        "count": len(cache["last_analysis"]) if cache["last_analysis"] else 0,
        "results": cache["last_analysis"]
    })

# ==================== 启动 ====================
if __name__ == '__main__':
    write_log("🚀 OKX 交易机器人 Web 服务启动！")
    
    # 后台线程：启动后自动运行一次分析（预热缓存）
    def auto_analyze():
        time.sleep(3)  # 等服务器完全启动
        write_log("自动执行首次分析...")
        run_batch_analysis(limit=10)
    
    threading.Thread(target=auto_analyze, daemon=True).start()
    
    # 监听 Railway 注入的 PORT
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
