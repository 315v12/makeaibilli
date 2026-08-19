"""
crypto_scrapers.py — gather crypto intel from across the web:
  • crypto news RSS (CoinDesk, Cointelegraph, Decrypt, Bitcoin Mag, CryptoSlate)
  • DuckDuckGo HTML search per coin (free, no key — broad web + social surfacing)
  • Reddit crypto subs via public .json (no auth)
StockTwits/Google: Google blocks scrapers without a paid API, so DuckDuckGo is
the reliable free web-search source; we cast wide across the others.
"""
import re, time, requests, feedparser
from datetime import datetime
from utils.state import push_signal, set_scraper_status
from crypto.crypto_universe import crypto_symbols

HEADERS = {"User-Agent": "Mozilla/5.0 (makeaibilli/4.0)"}

RSS = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
    "https://decrypt.co/feed",
    "https://bitcoinmagazine.com/.rss/full/",
    "https://cryptoslate.com/feed/",
    "https://www.newsbtc.com/feed/",
]
REDDIT_SUBS = ["CryptoCurrency","CryptoMarkets","altcoin","SatoshiStreetBets","ethtrader"]

POS = ["surge","rally","breakout","adoption","partnership","upgrade","bullish","record",
       "soar","gain","approval","integration","launch","listing","mainnet","staking"]
NEG = ["hack","exploit","crash","dump","lawsuit","ban","delist","bearish","plunge",
       "scam","rug","outage","halt","selloff","liquidation","depeg"]

def _sent(text):
    t = text.lower()
    return sum(1 for k in POS if k in t) - sum(1 for k in NEG if k in t)

def _coins_in(text):
    syms = crypto_symbols()
    found = []
    up = text.upper()
    for s in syms:
        if re.search(rf'\b{s}\b', up) or s.lower() in text.lower():
            found.append(s)
    return list(dict.fromkeys(found))


def _scrape_rss():
    n = 0
    for url in RSS:
        try:
            feed = feedparser.parse(url)
            for e in feed.entries[:25]:
                title = e.get("title","")
                coins = _coins_in(title + " " + e.get("summary",""))
                if not coins: continue
                push_signal({"type":"crypto_news","source":"Crypto RSS","tickers":coins,
                    "headline":title[:200],"sentiment":_sent(title),
                    "url":e.get("link",""),"ts":datetime.utcnow().isoformat(),"asset":"crypto"})
                n += 1
        except Exception:
            continue
    return n


def _scrape_duckduckgo():
    """DuckDuckGo HTML endpoint — free web search, surfaces blogs + social posts."""
    n = 0
    for sym in crypto_symbols()[:25]:   # rotate-friendly cap for the iMac
        try:
            r = requests.post("https://html.duckduckgo.com/html/",
                data={"q": f"{sym} crypto news today"}, headers=HEADERS, timeout=8)
            if r.status_code != 200: continue
            titles = re.findall(r'result__a[^>]*>(.*?)</a>', r.text)[:5]
            for t in titles:
                clean = re.sub(r'<[^>]+>', '', t).strip()
                if not clean: continue
                push_signal({"type":"crypto_web","source":"DuckDuckGo","tickers":[sym],
                    "headline":clean[:200],"sentiment":_sent(clean),
                    "ts":datetime.utcnow().isoformat(),"asset":"crypto"})
                n += 1
            time.sleep(0.5)   # be polite
        except Exception:
            continue
    return n


def _scrape_reddit():
    n = 0
    for sub in REDDIT_SUBS:
        try:
            r = requests.get(f"https://www.reddit.com/r/{sub}/hot.json?limit=40",
                             headers=HEADERS, timeout=8)
            if r.status_code != 200: continue
            for post in r.json().get("data",{}).get("children",[]):
                d = post.get("data",{})
                text = d.get("title","") + " " + d.get("selftext","")[:200]
                coins = _coins_in(text)
                if not coins: continue
                push_signal({"type":"crypto_social","source":f"r/{sub}","tickers":coins,
                    "headline":d.get("title","")[:200],"sentiment":_sent(text),
                    "mention_count":1,"ts":datetime.utcnow().isoformat(),"asset":"crypto"})
                n += 1
        except Exception:
            continue
    return n


def run():
    total = 0
    try:    total += _scrape_rss()
    except Exception: pass
    try:    total += _scrape_reddit()
    except Exception: pass
    try:    total += _scrape_duckduckgo()
    except Exception: pass
    set_scraper_status("Crypto web/social","ok",f"{total} crypto signals (RSS+Reddit+DuckDuckGo)")
    return total

if __name__ == "__main__":
    from dotenv import load_dotenv; load_dotenv(); print(run())
