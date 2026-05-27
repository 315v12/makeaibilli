import os, re, feedparser, requests
from datetime import datetime, timedelta
from utils.state import push_signal, set_scraper_status

RSS_FEEDS = [
    ("Reuters",          "https://feeds.reuters.com/reuters/businessNews"),
    ("CNBC Top",         "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
    ("CNBC Markets",     "https://www.cnbc.com/id/20910258/device/rss/rss.html"),
    ("MarketWatch",      "https://feeds.marketwatch.com/marketwatch/topstories/"),
    ("MarketWatch Pulse","https://feeds.marketwatch.com/marketwatch/marketpulse/"),
    ("Yahoo Finance",    "https://finance.yahoo.com/news/rssindex"),
    ("Seeking Alpha",    "https://seekingalpha.com/feed.xml"),
    ("Benzinga",         "https://www.benzinga.com/feed"),
    ("Motley Fool",      "https://www.fool.com/feeds/index.aspx"),
    ("Investing.com",    "https://www.investing.com/rss/news.rss"),
    ("Business Insider", "https://markets.businessinsider.com/rss/news"),
    ("Zacks",            "https://www.zacks.com/rss/rss_news.php"),
    ("TheStreet",        "https://www.thestreet.com/.rss/full/"),
    ("Nasdaq Markets",   "https://www.nasdaq.com/feed/rssoutbound?category=Markets"),
    ("Forbes Markets",   "https://www.forbes.com/markets/feed/"),
    ("Investors IBD",    "https://www.investors.com/feed/"),
    ("Kiplinger",        "https://www.kiplinger.com/feed/all"),
    ("CNN Business",     "http://rss.cnn.com/rss/money_latest.rss"),
]

POSITIVE = ["beats","beat","surge","surges","record","contract","approval",
            "approved","breakthrough","partnership","upgraded","profit","growth",
            "acquisition","buyback","raises guidance"]
NEGATIVE = ["miss","misses","falls","drops","downgraded","recall","lawsuit",
            "loss","losses","cut","warning","decline","fraud","investigation"]

def _tickers(text):
    return list(set(re.findall(r'\$([A-Z]{2,5})\b', text)))

def _sentiment(text):
    t = text.lower()
    return sum(1 for k in POSITIVE if k in t) - sum(1 for k in NEGATIVE if k in t)

def _recent(entry, hours=4):
    try:
        pub = datetime(*entry.published_parsed[:6])
        return datetime.utcnow() - pub < timedelta(hours=hours)
    except: return True

def scrape_rss():
    signals = []
    for name, url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:20]:
                if not _recent(entry): continue
                title = getattr(entry, "title", "")
                text = f"{title} {getattr(entry,'summary','')}"
                tickers = _tickers(text)
                sentiment = _sentiment(text)
                if not tickers and sentiment == 0: continue
                signals.append({"type":"news","source":name,"tickers":tickers,
                    "headline":title[:200],"sentiment":sentiment,
                    "url":getattr(entry,"link",""),"ts":datetime.utcnow().isoformat()})
        except Exception as e:
            set_scraper_status(f"RSS:{name}", "warn", str(e)[:60])
    return signals

def scrape_finnhub():
    key = os.getenv("FINNHUB_API_KEY","")
    if not key: return []
    try:
        resp = requests.get("https://finnhub.io/api/v1/news",
            params={"category":"general","token":key}, timeout=8)
        resp.raise_for_status()
        signals = []
        for item in resp.json()[:30]:
            h = item.get("headline","")
            tickers = _tickers(h)
            if item.get("related"):
                tickers += [t.strip().upper() for t in item["related"].split(",")]
            tickers = list(set(t for t in tickers if t))
            signals.append({"type":"news","source":"Finnhub","tickers":tickers,
                "headline":h[:200],"sentiment":_sentiment(h),
                "url":item.get("url",""),"ts":datetime.utcnow().isoformat()})
        return signals
    except Exception as e:
        set_scraper_status("Finnhub", "warn", str(e)[:60])
        return []

def run():
    signals = scrape_rss() + scrape_finnhub()
    for s in signals: push_signal(s)
    set_scraper_status("News (RSS + APIs)", "ok", f"{len(signals)} signals")
    return len(signals)

if __name__ == "__main__":
    from dotenv import load_dotenv; load_dotenv()
    print(f"News: {run()} signals")
