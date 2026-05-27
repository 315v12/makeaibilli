"""
ipo_scraper.py — upcoming IPOs within 5 days (Finnhub IPO calendar).
New listings often move hard in their first sessions.
"""
import os, requests
from datetime import datetime, timedelta
from utils.state import push_signal, set_scraper_status

def run():
    key = os.getenv("FINNHUB_API_KEY","")
    if not key:
        set_scraper_status("IPO calendar","warn","Needs Finnhub key"); return 0
    today = datetime.utcnow().date()
    frm, to = today.isoformat(), (today + timedelta(days=5)).isoformat()
    try:
        r = requests.get("https://finnhub.io/api/v1/calendar/ipo",
                         params={"from":frm,"to":to,"token":key}, timeout=10)
        r.raise_for_status()
        ipos = r.json().get("ipoCalendar", [])
    except Exception as e:
        set_scraper_status("IPO calendar","warn",str(e)[:60]); return 0
    pushed = 0
    for ipo in ipos:
        sym = (ipo.get("symbol") or "").strip().upper()
        if not sym: continue
        push_signal({"type":"ipo","source":"IPO calendar","tickers":[sym],
            "headline":f"{ipo.get('name','?')} IPO ~{ipo.get('date','?')} "
                       f"(${ipo.get('price','?')}, {ipo.get('numberOfShares','?')} shares)",
            "company_name": ipo.get("name",""),
            "ipo_date": ipo.get("date",""), "sentiment":3,
            "ts":datetime.utcnow().isoformat()})
        pushed += 1
    set_scraper_status("IPO calendar","ok",f"{pushed} upcoming IPOs (<=5d)")
    return pushed

if __name__ == "__main__":
    from dotenv import load_dotenv; load_dotenv(); print(run())
