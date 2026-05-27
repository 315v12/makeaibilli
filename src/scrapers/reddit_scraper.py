"""
reddit_scraper.py — NO LOGIN REQUIRED.
Uses Reddit's public .json endpoints instead of the OAuth API.
Just a custom User-Agent. Zero signup.
"""

import re, requests
from collections import defaultdict
from datetime import datetime
from utils.state import push_signal, set_scraper_status

SUBREDDITS = ["wallstreetbets", "stocks", "options", "Daytrading", "StockMarket"]
HEADERS = {"User-Agent": "makeaibilli/1.0 (market scanner)"}
IGNORE = {"I","A","CEO","IPO","ATH","DD","YOLO","FDA","SEC","GDP","CPI","FED",
          "ETF","EPS","PE","AI","EV","ER","PM","AM","US","NY","OP","WSB","CALLS",
          "PUTS","TLDR","EOD","ATM","OTM","ITM","IV","HODL","TA","USD","CALL","PUT",
          "LEAPS","RSI","YOY","QOQ","WSJ","GAAP","FINRA","NQ","ES","SPX","VIX","BTC",
          "ETH","NQ","DCA","GUH","FOMO","IRA","ROTH","CD","APR","APY","CFO","COO",
          "CTO","IPO","M&A","SPAC","NFT","DOJ","FTC","DOD","NATO","GDPR","ESG","AKAN",
          "NOT","CALL","PCE","YES","CPU","DTE","ST","RKT","NOW","IT","SO","BE","GO",
          "ALL","NEW","CEO","NSA","CIA","FBI","IRS","UK","EU","AT","ON","UP","TV"}

def _tickers(text):
    dollar = re.findall(r'\$([A-Z]{2,5})\b', text)
    plain = [w for w in re.findall(r'\b([A-Z]{2,5})\b', text) if w not in IGNORE]
    return list(set(dollar + plain))

def _sentiment(text):
    t = text.lower()
    pos = sum(1 for k in ["bull","calls","moon","buy","long","squeeze","breakout","ripping","green"] if k in t)
    neg = sum(1 for k in ["bear","puts","dump","short","crash","sell","tank","red","baghold"] if k in t)
    return pos - neg

def run():
    ticker_mentions = defaultdict(list)
    ticker_sources = defaultdict(set)
    errors = 0

    for sub in SUBREDDITS:
        try:
            # Public hot feed — no auth
            url = f"https://www.reddit.com/r/{sub}/hot.json?limit=30"
            resp = requests.get(url, headers=HEADERS, timeout=8)
            if resp.status_code != 200:
                errors += 1
                continue
            for child in resp.json().get("data", {}).get("children", []):
                post = child.get("data", {})
                text = f"{post.get('title','')} {post.get('selftext','')}"
                sentiment = _sentiment(text)
                weight = min(post.get("score", 0) / 100, 3)
                for ticker in _tickers(text):
                    ticker_mentions[ticker].append(sentiment + weight)
                    ticker_sources[ticker].add(f"r/{sub}")
        except Exception:
            errors += 1

    pushed = 0
    for ticker, scores in ticker_mentions.items():
        if len(scores) < 2:
            continue
        push_signal({
            "type": "social_reddit", "source": "Reddit", "tickers": [ticker],
            "mention_count": len(scores),
            "avg_sentiment": round(sum(scores) / len(scores), 2),
            "subreddits": list(ticker_sources[ticker]),
            "ts": datetime.utcnow().isoformat(),
        })
        pushed += 1

    status = "ok" if errors < len(SUBREDDITS) else "warn"
    set_scraper_status("Reddit (no login)", status, f"{pushed} tickers, {errors} errs")
    return pushed

if __name__ == "__main__":
    print(f"Reddit: {run()} tickers")
