"""
ipo_scraper.py — upcoming IPOs within 30 days. For each detected IPO we:
  1) capture the full IPO calendar payload from Finnhub
  2) enrich with /stock/profile2 (industry, country, market cap, website, etc.)
  3) save a rich payload so the dashboard can show ~20 facts about it

Goal: every new IPO entering the universe carries enough metadata to make a
real decision about it — not just a ticker and a date.
"""
import os, time, requests
from datetime import datetime, timedelta
from utils.state import push_signal, set_scraper_status

FINNHUB = "https://finnhub.io/api/v1"


def _profile(symbol: str, key: str) -> dict:
    """One-shot company profile lookup. Returns {} on any failure."""
    try:
        r = requests.get(f"{FINNHUB}/stock/profile2",
                         params={"symbol": symbol, "token": key}, timeout=10)
        if r.status_code == 200:
            return r.json() or {}
    except Exception:
        pass
    return {}


def run():
    key = os.getenv("FINNHUB_API_KEY", "")
    if not key:
        set_scraper_status("IPO calendar", "warn", "Needs Finnhub key"); return 0
    today = datetime.utcnow().date()
    frm, to = today.isoformat(), (today + timedelta(days=30)).isoformat()   # 30-day forward window
    try:
        r = requests.get(f"{FINNHUB}/calendar/ipo",
                         params={"from": frm, "to": to, "token": key}, timeout=15)
        r.raise_for_status()
        ipos = r.json().get("ipoCalendar", [])
    except Exception as e:
        set_scraper_status("IPO calendar", "warn", str(e)[:60]); return 0

    pushed = 0
    for ipo in ipos:
        sym = (ipo.get("symbol") or "").strip().upper()
        if not sym:
            continue

        # ── enrich with company profile (1 extra Finnhub call per ticker) ─────
        prof = _profile(sym, key)
        time.sleep(1.1)   # respect free-tier rate limit (60/min)

        push_signal({
            "type": "ipo", "source": "IPO calendar", "tickers": [sym],
            # Headline shown anywhere a one-line summary is needed
            "headline": f"{ipo.get('name','?')} IPO ~{ipo.get('date','?')} "
                        f"(${ipo.get('price','?')}, {ipo.get('numberOfShares','?')} shares)",
            "sentiment": 3, "ts": datetime.utcnow().isoformat(),

            # ── rich, structured fields the dashboard turns into bullets ──────
            "ticker":              sym,
            "company_name":        ipo.get("name", ""),
            "ipo_date":            ipo.get("date", ""),
            "exchange":            ipo.get("exchange", ""),
            "price_range":         ipo.get("price", ""),
            "number_of_shares":    ipo.get("numberOfShares", 0),
            "total_shares_value":  ipo.get("totalSharesValue", 0),
            "status":              ipo.get("status", ""),
            # from /stock/profile2 enrichment:
            "industry":            prof.get("finnhubIndustry", ""),
            "country":             prof.get("country", ""),
            "weburl":              prof.get("weburl", ""),
            "logo":                prof.get("logo", ""),
            "currency":            prof.get("currency", ""),
            "market_cap_mln":      prof.get("marketCapitalization", 0),
            "shares_outstanding_mln": prof.get("shareOutstanding", 0),
            "phone":               prof.get("phone", ""),
            "profile_ipo_date":    prof.get("ipo", ""),
        })
        pushed += 1

    set_scraper_status("IPO calendar", "ok", f"{pushed} IPOs (next 30d, enriched)")
    return pushed


if __name__ == "__main__":
    from dotenv import load_dotenv; load_dotenv(); print(run())
