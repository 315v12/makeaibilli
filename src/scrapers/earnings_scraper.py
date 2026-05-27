"""
earnings_scraper.py — TOP PRIORITY signal.
Flags stocks reporting earnings in the next 7 days or that just reported
in the last 2 days. Earnings = the biggest catalyst for fast moves, so these
get the heaviest weight in the heat score.
Uses Finnhub's free earnings calendar.
"""

import os, requests
from datetime import datetime, timedelta
from utils.state import push_signal, set_scraper_status


def run():
    key = os.getenv("FINNHUB_API_KEY", "")
    if not key:
        set_scraper_status("Earnings calendar", "warn", "Needs Finnhub key")
        return 0

    today = datetime.utcnow().date()
    frm = (today - timedelta(days=2)).isoformat()
    to  = (today + timedelta(days=7)).isoformat()

    try:
        resp = requests.get(
            "https://finnhub.io/api/v1/calendar/earnings",
            params={"from": frm, "to": to, "token": key}, timeout=10)
        resp.raise_for_status()
        rows = resp.json().get("earningsCalendar", [])
    except Exception as e:
        set_scraper_status("Earnings calendar", "warn", str(e)[:60])
        return 0

    pushed = 0
    for r in rows:
        sym = r.get("symbol", "").strip().upper()
        if not sym:
            continue
        try:
            edate = datetime.fromisoformat(r.get("date")).date()
        except Exception:
            continue
        days_away = (edate - today).days
        # "Hot for earnings" window: reporting very soon OR just reported
        if -2 <= days_away <= 7:
            when = "just reported" if days_away < 0 else \
                   "reports today" if days_away == 0 else \
                   f"reports in {days_away}d"
            push_signal({
                "type": "earnings",
                "source": "Earnings calendar",
                "tickers": [sym],
                "headline": f"{sym} {when} (EPS est {r.get('epsEstimate','?')})",
                "days_away": days_away,
                "sentiment": 4,   # earnings = strongest catalyst weight
                "ts": datetime.utcnow().isoformat(),
            })
            pushed += 1

    set_scraper_status("Earnings calendar", "ok", f"{pushed} earnings flagged")
    return pushed


if __name__ == "__main__":
    from dotenv import load_dotenv; load_dotenv()
    print(f"Earnings: {run()} flagged")
