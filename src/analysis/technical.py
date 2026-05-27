"""
technical.py — all indicators computed with PURE pandas/numpy.
No pandas-ta dependency (it's abandoned for Python 3.11), so this never
breaks on install. Same output dict the scorer expects.
"""

import yfinance as yf
try:
    yf.set_tz_cache_location('/tmp/yf-cache')
except Exception:
    pass
import pandas as pd
import numpy as np

CACHE: dict[str, dict] = {}


def _rsi(close: pd.Series, period: int = 14) -> float:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    val = rsi.iloc[-1]
    return float(val) if pd.notna(val) else 50.0


def _ema(close: pd.Series, span: int) -> float:
    return float(close.ewm(span=span, adjust=False).mean().iloc[-1])


def analyze(ticker: str) -> dict | None:
    if ticker in CACHE:
        return CACHE[ticker]
    try:
        df = yf.download(ticker, period="6mo", interval="1d",
                         progress=False, auto_adjust=True)
        if df.empty or len(df) < 25:
            return None

        close  = df["Close"].squeeze()
        high   = df["High"].squeeze()
        low    = df["Low"].squeeze()
        volume = df["Volume"].squeeze()

        price      = float(close.iloc[-1])
        prev       = float(close.iloc[-2])
        cur_vol    = float(volume.iloc[-1])
        avg_vol30  = float(volume.tail(30).mean())
        vol_ratio  = round(cur_vol / avg_vol30, 2) if avg_vol30 else 1.0
        change_pct = round((price - prev) / prev * 100, 2)

        high_52w = float(high.tail(252).max())
        low_52w  = float(low.tail(252).min())
        pct_from_high = round((price - high_52w) / high_52w * 100, 2)

        # RSI
        rsi14 = round(_rsi(close, 14), 1)
        rsi2  = round(_rsi(close, 2), 1)

        # MACD (12,26,9)
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal = macd_line.ewm(span=9, adjust=False).mean()
        hist = macd_line - signal
        macd_hist = round(float(hist.iloc[-1]), 4)
        macd_hist_prev = round(float(hist.iloc[-2]), 4)
        macd_crossover = macd_hist > 0 and macd_hist_prev <= 0

        # Bollinger Bands (20,2) -> %B
        mid = close.rolling(20).mean()
        std = close.rolling(20).std()
        bb_upper = float((mid + 2*std).iloc[-1])
        bb_lower = float((mid - 2*std).iloc[-1])
        bb_pct = round((price - bb_lower) / (bb_upper - bb_lower), 3) \
                 if (bb_upper - bb_lower) else 0.5

        # EMAs
        ema9   = round(_ema(close, 9), 2)
        ema21  = round(_ema(close, 21), 2)
        ema50  = round(_ema(close, 50), 2)
        ema200 = round(_ema(close, 200), 2) if len(close) >= 200 else ema50
        ema_bullish_stack = ema9 > ema21 > ema50

        # VWAP (14-day rolling, typical price)
        tp = (high + low + close) / 3
        vwap = float((tp * volume).rolling(14).sum().iloc[-1] /
                     volume.rolling(14).sum().iloc[-1])
        vwap = round(vwap, 2)
        above_vwap = price > vwap

        # ATR(14)
        prev_close = close.shift(1)
        tr = pd.concat([high - low,
                        (high - prev_close).abs(),
                        (low - prev_close).abs()], axis=1).max(axis=1)
        atr = round(float(tr.rolling(14).mean().iloc[-1]), 2)

        result = {
            "ticker": ticker, "price": round(price, 2), "change_pct": change_pct,
            "volume": int(cur_vol), "avg_volume_30": int(avg_vol30),
            "volume_ratio": vol_ratio, "high_52w": round(high_52w, 2),
            "low_52w": round(low_52w, 2), "pct_from_52w_high": pct_from_high,
            "rsi14": rsi14, "rsi2": rsi2, "macd_hist": macd_hist,
            "macd_crossover": macd_crossover, "bb_upper": round(bb_upper, 2),
            "bb_lower": round(bb_lower, 2), "bb_pct": bb_pct,
            "ema9": ema9, "ema21": ema21, "ema50": ema50, "ema200": ema200,
            "ema_bullish_stack": ema_bullish_stack, "vwap": vwap,
            "above_vwap": above_vwap, "atr": atr if atr else round(price*0.02, 2),
        }
        CACHE[ticker] = result
        return result
    except Exception:
        return None


def clear_cache():
    CACHE.clear()


def compute_tech_score(ta: dict) -> int:
    """Score 0-25 from technical indicators."""
    score = 0
    vr = ta.get("volume_ratio", 1)
    if vr >= 3:   score += 10
    elif vr >= 2: score += 8
    elif vr >= 1.5: score += 5

    rsi = ta.get("rsi14", 50)
    if 28 <= rsi <= 42:            score += 8
    elif rsi >= 68 and vr >= 1.5:  score += 7

    if ta.get("above_vwap"):        score += 3
    if ta.get("macd_crossover"):    score += 5
    if ta.get("ema_bullish_stack"): score += 4
    if ta.get("pct_from_52w_high", -100) >= -3 and vr >= 2: score += 3
    return min(score, 25)
