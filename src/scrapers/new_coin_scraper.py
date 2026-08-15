"""
new_coin_scraper.py — detect coins newly listed on Coinbase by diffing the
public /products endpoint against the last-known snapshot stored on disk.

Coinbase doesn't publish a "new listings" feed, so we maintain our own. Each
run:
  1) fetches every USD trading pair
  2) compares against /data/known_products.json
  3) anything new emits a `crypto_new_listing` signal carrying as much detail
     as the product record gives us (status, base currency, min funds, etc.)
  4) the snapshot is updated so the same coin isn't flagged twice

First run takes a snapshot but does NOT fire signals (everything would look
"new" the first time, which would just be noise).
"""
import os, json, requests
from datetime import datetime
from utils.state import push_signal, set_scraper_status

SNAPSHOT = "/data/known_products.json"
COINBASE = "https://api.exchange.coinbase.com/products"


def _load_snapshot() -> set:
    if not os.path.exists(SNAPSHOT):
        return set()
    try:
        return set(json.load(open(SNAPSHOT)))
    except Exception:
        return set()


def _save_snapshot(ids: set):
    try:
        os.makedirs(os.path.dirname(SNAPSHOT), exist_ok=True)
        with open(SNAPSHOT, "w") as f:
            json.dump(sorted(ids), f)
    except Exception:
        pass


def run():
    try:
        r = requests.get(COINBASE, timeout=15)
        r.raise_for_status()
        products = r.json()
    except Exception as e:
        set_scraper_status("New crypto listings", "warn", str(e)[:60])
        return 0

    # USD pairs only; we trade in USD
    current = {p["id"]: p for p in products
               if p.get("quote_currency") == "USD" and not p.get("trading_disabled", False)}
    current_ids = set(current.keys())
    prev_ids = _load_snapshot()

    # First run: take the snapshot, don't flag everything as new.
    if not prev_ids:
        _save_snapshot(current_ids)
        set_scraper_status("New crypto listings", "ok",
                           f"baseline {len(current_ids)} pairs (first run)")
        return 0

    new_ids = current_ids - prev_ids
    pushed = 0
    for pid in sorted(new_ids):
        p = current[pid]
        sym = p.get("base_currency", pid.replace("-USD", "")).upper()
        push_signal({
            "type": "crypto_new_listing", "asset": "crypto",
            "source": "coinbase",
            "tickers": [sym], "ticker": sym,
            "headline": f"New Coinbase listing: {p.get('display_name', pid)}",
            "sentiment": 3, "ts": datetime.utcnow().isoformat(),

            # ── structured fields the dashboard turns into bullets ────────────
            "product_id":          pid,
            "base_currency":       p.get("base_currency", ""),
            "quote_currency":      p.get("quote_currency", ""),
            "display_name":        p.get("display_name", ""),
            "status":              p.get("status", ""),
            "status_message":      p.get("status_message", ""),
            "trading_disabled":    p.get("trading_disabled", False),
            "post_only":           p.get("post_only", False),
            "limit_only":          p.get("limit_only", False),
            "cancel_only":         p.get("cancel_only", False),
            "auction_mode":        p.get("auction_mode", False),
            "base_min_size":       p.get("base_min_size", ""),
            "base_max_size":       p.get("base_max_size", ""),
            "min_market_funds":    p.get("min_market_funds", ""),
            "base_increment":      p.get("base_increment", ""),
            "quote_increment":     p.get("quote_increment", ""),
            "fx_stablecoin":       p.get("fx_stablecoin", False),
            "detected_at":         datetime.utcnow().isoformat(),
        })
        pushed += 1

    _save_snapshot(current_ids)
    set_scraper_status("New crypto listings", "ok",
                       f"{pushed} new pairs detected" if pushed
                       else f"no new pairs ({len(current_ids)} tracked)")
    return pushed


if __name__ == "__main__":
    from dotenv import load_dotenv; load_dotenv(); print(run())
