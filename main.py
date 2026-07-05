from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import requests
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="OKX 交易机器人")

BASE_URL = "https://www.okx.com"

@app.get("/")
async def root():
    html = """
    <h1>🚀 OKX 交易机器人 Web 版</h1>
    <p>访问 <a href="/query/BTC">/query/BTC</a> 查询行情</p>
    """
    return HTMLResponse(html)

@app.get("/query/{symbol}")
async def query_symbol(symbol: str):
    symbol = symbol.upper()
    if not symbol.endswith("-SWAP"):
        symbol += "-USDT-SWAP"
    
    url = f"{BASE_URL}/api/v5/market/ticker?instId={symbol}"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if data.get('code') == '0' and data.get('data'):
            ticker = data['data'][0]
            price = float(ticker.get('last', 0))
            change = float(ticker.get('changePercent', 0))
            
            return {
                "symbol": symbol,
                "price": price,
                "change_percent": change,
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "status": "success"
            }
        else:
            return {"status": "error", "message": "无法获取数据"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
