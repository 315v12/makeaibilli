"""
ranking.py — the SECOND-PASS market validation layer.
After the web intel surfaces candidate tickers (first pass), this batch-pulls
their real market data, filters out useless/illiquid names, and measures
both short-term momentum and long-term trend so the scorer can project
potential gain on both horizons.
"""

import yfinance as yf
try:
    yf.set_tz_cache_location('/tmp/yf-cache')
except Exception:
    pass
# Silence yfinance's noisy per-ticker "delisted" errors — we validate tickers upstream now
import logging as _lg
for _n in ("yfinance", "yfinance.utils", "yfinance.data"):
    _lg.getLogger(_n).setLevel(_lg.CRITICAL)
from analysis.universe import category_of, MIN_PRICE, MIN_AVG_VOLUME


def fetch_market_data(tickers: list[str]) -> dict:
    """
    One batched download. Returns {ticker: metrics} for liquid, real stocks only.
    Useless stocks (penny / illiquid) are dropped here.
    """
    tickers = list(dict.fromkeys([t for t in tickers if t and 2 <= len(t) <= 5]))
    if not tickers:
        return {}
    try:
        data = yf.download(" ".join(tickers), period="6mo", interval="1d",
                           progress=False, auto_adjust=True, group_by="ticker",
                           threads=True)
    except Exception:
        return {}

    out = {}
    for t in tickers:
        try:
            df = data[t] if len(tickers) > 1 else data
            close = df["Close"].dropna()
            vol   = df["Volume"].dropna()
            if len(close) < 25:
                continue
            price   = float(close.iloc[-1])
            avg_vol = float(vol.tail(20).mean())
            if price < MIN_PRICE or avg_vol < MIN_AVG_VOLUME:
                continue   # filter useless stocks

            ema50  = float(close.ewm(span=50).mean().iloc[-1])
            ema200 = float(close.ewm(span=200).mean().iloc[-1]) if len(close) >= 200 else ema50

            # Stock-SPECIFIC price levels (derived from this name's own history)
            hi_20  = float(close.tail(20).max())
            lo_20  = float(close.tail(20).min())
            hi_52w = float(close.tail(252).max())
            lo_52w = float(close.tail(252).min())
            # average true range proxy from daily range
            highs = df["High"].dropna().tail(14); lows = df["Low"].dropna().tail(14)
            atr = float((highs.values - lows.values).mean()) if len(highs) == len(lows) and len(highs) else round(price*0.02,2)

            out[t] = {
                "ticker": t,
                "category": category_of(t),
                "price": round(price, 2),
                "mom_1d":  round((price/float(close.iloc[-2]) - 1)*100, 2),
                "mom_5d":  round((price/float(close.iloc[-6]) - 1)*100, 2),
                "mom_20d": round((price/float(close.iloc[-21]) - 1)*100, 2),
                "vol_ratio": round(float(vol.iloc[-1])/avg_vol, 2) if avg_vol else 1.0,
                "above_50ema":  price > ema50,
                "above_200ema": price > ema200,
                "ema50": round(ema50, 2),
                "ema200": round(ema200, 2),
                "hi_20": round(hi_20,2), "lo_20": round(lo_20,2),
                "hi_52w": round(hi_52w,2), "lo_52w": round(lo_52w,2),
                "atr": round(atr,2),
            }
        except Exception:
            continue
    return out


def category_benchmarks(market: dict) -> dict:
    """Average 5-day momentum per category — the peer benchmark for relative strength."""
    bench = {}
    cats = {}
    for m in market.values():
        cats.setdefault(m["category"], []).append(m["mom_5d"])
    for cat, moms in cats.items():
        bench[cat] = round(sum(moms)/len(moms), 2) if moms else 0.0
    return bench
