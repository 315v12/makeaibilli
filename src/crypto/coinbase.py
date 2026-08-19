"""
coinbase.py — Coinbase market data via the PUBLIC Exchange REST API.
No auth, no key, no FIX. Just candles + ticker for analysis.

  products : GET /products
  candles  : GET /products/{id}/candles?granularity=86400   (daily OHLC)
  ticker   : GET /products/{id}/ticker
  stats    : GET /products/{id}/stats   (24h)

WebSocket (wss://ws-feed.exchange.coinbase.com) is the upgrade path for
sub-second live ticks; for our scheduled scans, REST polling gives us
everything (OHLC, volume, price) and is far simpler/robust on the iMac.
"""
import requests

BASE = "https://api.exchange.coinbase.com"
HEADERS = {"User-Agent": "makeaibilli/4.0"}


def get_candles(product_id: str, granularity: int = 86400) -> list:
    """Returns candles newest-first: [[time, low, high, open, close, volume], ...]."""
    try:
        r = requests.get(f"{BASE}/products/{product_id}/candles",
                         params={"granularity": granularity}, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return []
        return r.json()           # up to 300 candles
    except Exception:
        return []


def get_stats(product_id: str) -> dict:
    try:
        r = requests.get(f"{BASE}/products/{product_id}/stats",
                         headers=HEADERS, timeout=8)
        return r.json() if r.status_code == 200 else {}
    except Exception:
        return {}


def metrics_from_candles(product_id: str) -> dict | None:
    """
    Build the SAME metrics dict the stock engine + plan.py expect, but from
    Coinbase daily candles — so crypto reuses the exact data-derived trigger logic.
    """
    candles = get_candles(product_id, 86400)
    if not candles or len(candles) < 25:
        return None
    # candles newest-first; reverse to oldest-first
    candles = list(reversed(candles))
    closes = [c[4] for c in candles]
    vols   = [c[5] for c in candles]
    highs  = [c[2] for c in candles]
    lows   = [c[3] for c in candles]
    price  = closes[-1]
    if price <= 0:
        return None

    def ema(series, span):
        k = 2 / (span + 1); e = series[0]
        for v in series[1:]:
            e = v * k + e * (1 - k)
        return e

    ema50  = ema(closes[-60:], 50) if len(closes) >= 50 else ema(closes, len(closes))
    ema200 = ema(closes, 200) if len(closes) >= 200 else ema50
    avg_vol = sum(vols[-20:]) / min(len(vols), 20)
    atr_vals = [highs[i] - lows[i] for i in range(-14, 0)]
    atr = sum(atr_vals) / len(atr_vals) if atr_vals else price * 0.03

    return {
        "ticker": product_id.replace("-USD", ""),
        "product_id": product_id,
        "category": "Crypto",
        "price": round(price, 4 if price < 10 else 2),
        "mom_1d":  round((price/closes[-2]-1)*100, 2) if len(closes) >= 2 else 0,
        "mom_5d":  round((price/closes[-6]-1)*100, 2) if len(closes) >= 6 else 0,
        "mom_20d": round((price/closes[-21]-1)*100, 2) if len(closes) >= 21 else 0,
        "mom_120d": round((price/closes[-min(121, len(closes))]-1)*100, 2),
        "mom_12_1": round((closes[-21 if len(closes) > 22 else -1]/closes[-min(252, len(closes))]-1)*100, 2)
                    if closes[-min(252, len(closes))] else 0.0,
        "vol_ratio": round(vols[-1]/avg_vol, 2) if avg_vol else 1.0,
        "above_50ema":  price > ema50,
        "above_200ema": price > ema200,
        "ema50":  round(ema50, 4 if price < 10 else 2),
        "ema200": round(ema200, 4 if price < 10 else 2),
        "hi_20":  round(max(closes[-20:]), 4 if price < 10 else 2),
        "lo_20":  round(min(closes[-20:]), 4 if price < 10 else 2),
        "hi_52w": round(max(closes), 4 if price < 10 else 2),
        "lo_52w": round(min(closes), 4 if price < 10 else 2),
        "atr": round(atr, 4 if price < 10 else 2),
    }
