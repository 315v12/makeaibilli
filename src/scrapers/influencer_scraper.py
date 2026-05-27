"""
influencer_scraper.py
Tracks market-moving individuals and big-money flows via RELIABLE channels
(news wires + StockTwits), since direct X/Facebook scraping is dead/unreliable.

When a tracked name appears in a headline alongside a ticker, that's a strong
signal — these people move stocks when they speak or trade.
"""

import re, feedparser, requests
from datetime import datetime, timedelta
from utils.state import push_signal, set_scraper_status

# People whose words/trades move markets. Add/remove freely.
INFLUENCERS = {
    # Name fragment : weight (how much their involvement matters)
    "musk":            5,   # Elon Musk — tweets move TSLA, DOGE, etc
    "buffett":         5,   # Warren Buffett / Berkshire
    "berkshire":       5,
    "burry":           4,   # Michael Burry (Big Short)
    "ackman":          4,   # Bill Ackman
    "pelosi":          5,   # Nancy Pelosi — congressional trades
    "cathie wood":     3,   # ARK
    "ark invest":      3,
    "icahn":           4,   # Carl Icahn
    "powell":          4,   # Jerome Powell — Fed, moves whole market
    "federal reserve": 4,
    "cramer":          2,   # Jim Cramer — often a contrarian/fade signal
    "soros":           3,
    "griffin":         3,   # Ken Griffin / Citadel
    "tepper":          3,   # David Tepper
}

# News wires that report fast on big players
WIRES = [
    ("Reuters",      "https://feeds.reuters.com/reuters/businessNews"),
    ("CNBC",         "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
    ("MarketWatch",  "https://feeds.marketwatch.com/marketwatch/marketpulse/"),
    ("Benzinga",     "https://www.benzinga.com/feed"),
]

def _tickers(text):
    return list(set(re.findall(r'\$?([A-Z]{2,5})\b', text)))

def _recent(entry, hours=6):
    try:
        pub = datetime(*entry.published_parsed[:6])
        return datetime.utcnow() - pub < timedelta(hours=hours)
    except:
        return True

def run():
    pushed = 0
    for source, url in WIRES:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:30]:
                if not _recent(entry):
                    continue
                title = getattr(entry, "title", "")
                summary = getattr(entry, "summary", "")
                text = f"{title} {summary}".lower()

                # Which influencer is mentioned?
                hit_name, hit_weight = None, 0
                for name, weight in INFLUENCERS.items():
                    if name in text:
                        hit_name, hit_weight = name, weight
                        break
                if not hit_name:
                    continue

                tickers = _tickers(f"{title} {summary}")
                push_signal({
                    "type": "influencer",
                    "source": f"{source} (influencer)",
                    "tickers": tickers,
                    "influencer": hit_name.title(),
                    "headline": title[:200],
                    "sentiment": hit_weight,
                    "url": getattr(entry, "link", ""),
                    "ts": datetime.utcnow().isoformat(),
                })
                pushed += 1
        except Exception as e:
            set_scraper_status(f"Influencer:{source}", "warn", str(e)[:50])

    set_scraper_status("Influencer/whale tracker", "ok",
                       f"{pushed} market-mover mentions")
    return pushed

if __name__ == "__main__":
    print(f"Influencer: {run()} mentions")
