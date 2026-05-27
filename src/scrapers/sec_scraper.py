import re, feedparser, requests
from datetime import datetime, timedelta
from utils.state import push_signal, set_scraper_status

EDGAR_8K = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&dateb=&owner=include&count=40&search_text=&output=atom"
EDGAR_F4 = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=4&dateb=&owner=include&count=40&search_text=&output=atom"
HEADERS = {"User-Agent": "makeaibilli research@makeaibilli.com"}

def _recent(entry, hours=6):
    try:
        pub = datetime(*entry.published_parsed[:6])
        return datetime.utcnow() - pub < timedelta(hours=hours)
    except: return True

def _ticker(entry):
    match = re.search(r'\((\d{10})\)', getattr(entry,"title",""))
    if match:
        try:
            resp = requests.get(f"https://data.sec.gov/submissions/CIK{match.group(1)}.json",
                                headers=HEADERS, timeout=5)
            if resp.ok:
                tickers = resp.json().get("tickers", [])
                return tickers[0] if tickers else None
        except: pass
    return None

def run():
    signals = []
    for url, sig_type, label in [(EDGAR_8K,"sec_8k","8-K"),(EDGAR_F4,"sec_form4","Form 4")]:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:15]:
                if not _recent(entry): continue
                ticker = _ticker(entry)
                title = getattr(entry,"title","")
                signals.append({"type":sig_type,"source":f"SEC EDGAR {label}",
                    "tickers":[ticker] if ticker else [],"headline":title[:200],
                    "sentiment":2 if sig_type=="sec_form4" else 1,
                    "url":getattr(entry,"link",""),"ts":datetime.utcnow().isoformat()})
        except Exception as e:
            set_scraper_status("SEC EDGAR","warn",str(e)[:60])
    for s in signals: push_signal(s)
    set_scraper_status("SEC EDGAR","ok",f"{len(signals)} filings")
    return len(signals)

if __name__ == "__main__":
    print(f"SEC: {run()} signals")
