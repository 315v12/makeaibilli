"""
company_news_scraper.py — searches NEWS for Fortune/S&P 500 companies by name,
not just ticker. Cycles through the universe in batches each heavy sweep so it
covers all ~500 over time without hammering the free Finnhub tier or the iMac.
"""
import os, time, requests
from datetime import datetime, timedelta
from utils.state import push_signal, set_scraper_status, get_client
from analysis.fortune500 import fortune_tickers
from analysis.names import name_of

BATCH = 40   # companies per heavy sweep

POS = ["beats","beat","surge","record","contract","approval","upgrade","growth",
       "profit","acquisition","buyback","raises","wins","expansion","strong"]
NEG = ["miss","falls","downgrade","recall","lawsuit","loss","cut","warning",
       "decline","fraud","probe","investigation","layoff","weak"]

def _sent(text):
    t = text.lower()
    return sum(1 for k in POS if k in t) - sum(1 for k in NEG if k in t)

def run():
    key = os.getenv("FINNHUB_API_KEY","")
    if not key:
        set_scraper_status("Fortune 500 news","warn","Needs Finnhub key"); return 0
    tickers = fortune_tickers()
    if not tickers:
        set_scraper_status("Fortune 500 news","warn","No universe"); return 0

    # rotating offset so we cover the whole list over successive sweeps
    r = get_client()
    try: off = int(r.get("fortune:offset") or 0)
    except Exception: off = 0
    batch = tickers[off:off+BATCH] or tickers[:BATCH]
    new_off = (off + BATCH) % max(len(tickers),1)
    try: r.set("fortune:offset", new_off)
    except Exception: pass

    today = datetime.utcnow().date()
    frm = (today - timedelta(days=3)).isoformat()
    to  = today.isoformat()
    pushed = 0
    for sym in batch:
        try:
            resp = requests.get("https://finnhub.io/api/v1/company-news",
                params={"symbol":sym,"from":frm,"to":to,"token":key}, timeout=8)
            if resp.status_code == 429:
                time.sleep(2)   # backoff on rate limit
                continue
            if resp.status_code != 200: continue
            arts = resp.json()[:5]   # top recent per company
            for a in arts:
                h = a.get("headline","")
                if not h: continue
                push_signal({"type":"news","source":f"{name_of(sym)} news",
                    "tickers":[sym],"headline":h[:200],"sentiment":_sent(h),
                    "company_name": name_of(sym),
                    "url":a.get("url",""),"ts":datetime.utcnow().isoformat()})
                pushed += 1
            time.sleep(1)   # throttle: stay under free-tier 60/min
        except Exception:
            continue
    set_scraper_status("Fortune 500 news","ok",
                       f"{len(batch)} companies, {pushed} headlines (offset {new_off}/{len(tickers)})")
    return pushed

if __name__ == "__main__":
    from dotenv import load_dotenv; load_dotenv(); print(run())
