import requests
from datetime import datetime, timedelta
from utils.state import push_signal, set_scraper_status

URL = "https://api.quiverquant.com/beta/live/congresstrading"
HEADERS = {"User-Agent": "makeaibilli/1.0", "Accept": "application/json"}

def run():
    try:
        resp = requests.get(URL, headers=HEADERS, timeout=10)
        if resp.status_code == 401:
            set_scraper_status("Congress trades","warn","Free tier requires signup at quiverquant.com")
            return 0
        resp.raise_for_status()
        trades = resp.json()
    except Exception as e:
        set_scraper_status("Congress trades","warn",str(e)[:60]); return 0

    pushed = 0
    cutoff = datetime.utcnow() - timedelta(days=30)
    for trade in trades:
        try:
            date = datetime.strptime(trade.get("TransactionDate",""), "%Y-%m-%d")
        except: continue
        if date < cutoff: continue
        tx = trade.get("Transaction","").lower()
        if "purchase" not in tx and "buy" not in tx: continue
        ticker = trade.get("Ticker","").strip().upper()
        if not ticker: continue
        push_signal({"type":"congress_trade","source":"Congress (QuiverQuant)",
            "tickers":[ticker],"headline":f"{trade.get('Representative','?')} purchased {ticker}",
            "sentiment":3,"ts":datetime.utcnow().isoformat()})
        pushed += 1

    set_scraper_status("Congress trades","ok",f"{pushed} recent purchases")
    return pushed

if __name__ == "__main__":
    print(f"Congress: {run()} signals")
