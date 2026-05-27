import requests
from datetime import datetime
from utils.state import push_signal, set_scraper_status

BASE = "https://api.stocktwits.com/api/2"
HEADERS = {"User-Agent": "makeaibilli/1.0"}

def get_trending():
    try:
        resp = requests.get(f"{BASE}/trending/symbols.json", headers=HEADERS, timeout=8)
        resp.raise_for_status()
        return [s["symbol"] for s in resp.json().get("symbols", [])]
    except: return []

def get_sentiment(ticker):
    try:
        resp = requests.get(f"{BASE}/streams/symbol/{ticker}.json", headers=HEADERS, timeout=8)
        if resp.status_code == 429: return None
        resp.raise_for_status()
        msgs = resp.json().get("messages", [])
        if not msgs: return None
        bull = sum(1 for m in msgs if m.get("entities",{}).get("sentiment",{}).get("basic")=="Bullish")
        bear = sum(1 for m in msgs if m.get("entities",{}).get("sentiment",{}).get("basic")=="Bearish")
        total = bull + bear
        return {"ticker":ticker,"bull_ratio":round(bull/total,2) if total else 0.5,
                "total_messages":len(msgs)}
    except: return None

def run():
    trending = get_trending()
    if not trending:
        set_scraper_status("StockTwits","warn","Could not fetch trending"); return 0
    pushed = 0
    for ticker in trending[:30]:
        data = get_sentiment(ticker)
        if not data: continue
        if data["bull_ratio"] > 0.65 or data["bull_ratio"] < 0.35:
            push_signal({"type":"social_stocktwits","source":"StockTwits",
                "tickers":[ticker],"bull_ratio":data["bull_ratio"],
                "message_count":data["total_messages"],"ts":datetime.utcnow().isoformat()})
            pushed += 1
    set_scraper_status("StockTwits","ok",f"{len(trending)} trending, {pushed} signals")
    return pushed

if __name__ == "__main__":
    print(f"StockTwits: {run()} signals")
