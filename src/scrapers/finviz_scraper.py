"""
finviz_scraper.py
Scrapes Finviz's free screener for high-volume movers, gap-ups, and
stocks with unusual activity — no API key needed.
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime
from utils.state import push_signal, set_scraper_status

BASE_URL = "https://finviz.com/screener.ashx"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

# Screener presets — each returns stocks matching that filter
SCREENS = {
    "High Volume":      "v=111&f=sh_avgvol_o500,sh_curvol_o2000000&o=-change",
    "Gap Up >3%":       "v=111&f=ta_gap_u3&o=-change",
    "Oversold Bounce":  "v=111&f=ta_rsi_os30,sh_avgvol_o300&o=-change",
    "Breakout":         "v=111&f=ta_highlow52w_nh,sh_avgvol_o300&o=-change",
    "Unusual Volume":   "v=111&f=sh_curvol_o3x&o=-change",
}


def _parse_screener(url: str, screen_name: str) -> list[dict]:
    results = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        table = soup.find("table", {"id": "screener-views-table"})
        if not table:
            # Try alternate table selector
            table = soup.find("table", class_="table-light")
        if not table:
            return results

        rows = table.find_all("tr")[1:]   # skip header
        for row in rows[:15]:
            cells = row.find_all("td")
            if len(cells) < 9:
                continue
            try:
                ticker  = cells[1].text.strip()
                company = cells[2].text.strip()
                sector  = cells[3].text.strip()
                price   = cells[8].text.strip()
                change  = cells[9].text.strip()
                volume  = cells[10].text.strip()
                results.append({
                    "ticker": ticker,
                    "company": company,
                    "sector": sector,
                    "price": price,
                    "change": change,
                    "volume": volume,
                    "screen": screen_name,
                })
            except (IndexError, AttributeError):
                continue
    except Exception as e:
        set_scraper_status(f"Finviz:{screen_name}", "warn", str(e)[:60])
    return results


def run():
    all_tickers: dict[str, dict] = {}
    signals_pushed = 0

    for screen_name, params in SCREENS.items():
        url = f"{BASE_URL}?{params}"
        rows = _parse_screener(url, screen_name)
        for row in rows:
            t = row["ticker"]
            if t not in all_tickers:
                all_tickers[t] = row
            else:
                # Ticker appears in multiple screens — increase weight
                all_tickers[t]["screens_count"] = \
                    all_tickers[t].get("screens_count", 1) + 1

    for ticker, data in all_tickers.items():
        screens_count = data.get("screens_count", 1)
        push_signal({
            "type": "finviz_screen",
            "source": f"Finviz ({data['screen']})",
            "tickers": [ticker],
            "company": data.get("company", ""),
            "sector": data.get("sector", ""),
            "price": data.get("price", ""),
            "change_pct": data.get("change", ""),
            "screens_hit": screens_count,
            "sentiment": screens_count,   # more screens = stronger signal
            "ts": datetime.utcnow().isoformat(),
        })
        signals_pushed += 1

    set_scraper_status("Finviz screener", "ok",
                       f"{signals_pushed} tickers across {len(SCREENS)} screens")
    return signals_pushed


if __name__ == "__main__":
    print(f"Finviz pushed {run()} tickers")
