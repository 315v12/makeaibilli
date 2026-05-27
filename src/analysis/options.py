"""
options.py
Given technical data and a trade direction, suggests the options play:
strike, expiration, and estimated risk/reward.
"""

from datetime import datetime, timedelta
import math


def suggest_options_play(ta_data: dict, direction: str = "bullish") -> dict:
    """
    direction: 'bullish' | 'bearish'
    Returns a dict with strike, expiry, entry estimate, target, stop.
    """
    price   = ta_data.get("price", 100)
    atr     = ta_data.get("atr", price * 0.02)
    rsi     = ta_data.get("rsi14", 50)
    vol_ratio = ta_data.get("volume_ratio", 1)

    # Pick expiration based on momentum:
    # Strong momentum → shorter-dated (7 days), moderate → 14-21 days
    if vol_ratio >= 2.5 and rsi >= 65:
        days_out = 7
    elif vol_ratio >= 1.5:
        days_out = 14
    else:
        days_out = 21

    expiry = (datetime.now() + timedelta(days=days_out)).strftime("%b %d")

    if direction == "bullish":
        # First OTM call: round up to nearest $2.50 or $5 increment
        increment = _strike_increment(price)
        strike = _round_up_to_increment(price * 1.01, increment)
        play   = "BUY CALL"
        # Target: price + 1.5× ATR
        target = round(price + (atr * 1.5), 2)
        # Stop: price - 0.75× ATR
        stop_price = round(price - (atr * 0.75), 2)
    else:
        increment = _strike_increment(price)
        strike = _round_down_to_increment(price * 0.99, increment)
        play   = "BUY PUT"
        target = round(price - (atr * 1.5), 2)
        stop_price = round(price + (atr * 0.75), 2)

    # Rough option premium estimate (very simplified — real IV needed for accuracy)
    intrinsic = max(0, abs(price - strike))
    time_value = round(price * 0.015 * math.sqrt(days_out / 30), 2)
    entry_low  = round(intrinsic + time_value * 0.85, 2)
    entry_high = round(intrinsic + time_value * 1.15, 2)

    # Risk/reward on the option (rough)
    target_option = round(entry_low * 2.0, 2)   # target = 2× entry
    rr = round(target_option / entry_high, 1) if entry_high else 2.0

    return {
        "play":       play,
        "strike":     strike,
        "expiry":     expiry,
        "days_out":   days_out,
        "entry_low":  entry_low,
        "entry_high": entry_high,
        "target_option": target_option,
        "stop_option": round(entry_low * 0.45, 2),   # -55% loss stop
        "stock_target": target,
        "stock_stop":   stop_price,
        "rr_ratio":   rr,
    }


def determine_direction(ta_data: dict, news_sentiment: int,
                        social_sentiment: float) -> str:
    """Decide bullish or bearish based on combined signals."""
    score = 0
    rsi = ta_data.get("rsi14", 50)

    if rsi <= 40:       score += 1   # oversold — bounce bullish
    elif rsi >= 65:     score += 1   # momentum bullish
    elif rsi >= 75:     score -= 1   # overbought — lean bearish

    if ta_data.get("above_vwap"):   score += 1
    if ta_data.get("ema_bullish_stack"): score += 1
    if news_sentiment > 0:  score += 1
    if news_sentiment < 0:  score -= 1
    if social_sentiment > 0.65: score += 1
    if social_sentiment < 0.35: score -= 1

    return "bullish" if score >= 0 else "bearish"


def _strike_increment(price: float) -> float:
    if price < 25:   return 0.50
    if price < 100:  return 1.00
    if price < 200:  return 2.50
    if price < 500:  return 5.00
    return 10.0


def _round_up_to_increment(value: float, increment: float) -> float:
    return round(math.ceil(value / increment) * increment, 2)


def _round_down_to_increment(value: float, increment: float) -> float:
    return round(math.floor(value / increment) * increment, 2)
