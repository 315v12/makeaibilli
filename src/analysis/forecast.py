"""
forecast.py — forward-looking PROJECTION layer.

This is the "what the engine expects to happen" half of a pick (the triggers in
plan.py are "what to do when it happens"). It does NOT predict exact prices —
nothing can. It produces, from each asset's own behavior:

  • Expected price RANGE over the horizon, from the asset's own volatility
    (ATR-based, scaled by sqrt(time) — the same math options markets use for
    an "expected move"). ~68% (1σ) and ~95% (2σ) bands.
  • A directional LEAN (bullish / neutral / bearish) with a 0-10 strength,
    read from trend posture + momentum + (for short horizons) overbought/
    oversold position.
  • Two CONDITIONAL targets: a continuation target if the current trend holds,
    and a reversion level if it pulls back. Both are explicitly conditional.

Honest framing carried into the UI: these are probabilistic estimates from
price behavior, not guarantees. Markets gap on news; ranges break.
"""

import math

# Trading-day horizon used for each tier's projection.
HORIZON_DAYS = {"short": 3, "long": 20, "xlong": 90}


def _range_pos(price, lo, hi):
    if hi is None or lo is None or hi <= lo:
        return 0.5
    return max(0.0, min(1.0, (price - lo) / (hi - lo)))


def project(md: dict, tier: str) -> dict:
    """Return a projection dict for one asset on one horizon."""
    price = md["price"]
    h = HORIZON_DAYS.get(tier, 3)

    # ── expected move from the asset's OWN daily volatility ──────────────────
    # ATR is an average daily true range; ATR/price ≈ a daily move fraction.
    daily_vol = (md.get("atr", price * 0.02) / price) if price else 0.02
    daily_vol = max(0.003, min(daily_vol, 0.25))      # sane floor/ceiling
    move_1s = daily_vol * math.sqrt(h)                # 1σ over the horizon
    range_low  = round(price * (1 - move_1s), 2)
    range_high = round(price * (1 + move_1s), 2)
    range_low2  = round(price * (1 - 2 * move_1s), 2)
    range_high2 = round(price * (1 + 2 * move_1s), 2)

    # ── directional lean from trend + momentum (+ mean-reversion on short) ───
    sig = 0
    sig += 2 if md.get("above_200ema") else -2
    sig += 1 if md.get("above_50ema") else -1
    sig += 2 if md.get("mom_20d", 0) > 0 else -2
    sig += 1 if md.get("mom_5d", 0) > 0 else -1
    if tier == "short":
        rp = _range_pos(price, md.get("lo_20"), md.get("hi_20"))
        if rp < 0.25:   sig += 2     # near recent low → bounce more likely
        elif rp > 0.80: sig -= 2     # stretched near recent high → pullback risk
    max_sig = 8 if tier == "short" else 6
    strength = round(min(10.0, abs(sig) / max_sig * 10), 1)
    lean = "Bullish" if sig >= 2 else ("Bearish" if sig <= -2 else "Neutral")

    # ── conditional targets ──────────────────────────────────────────────────
    # Continuation: project the recent average daily drift forward, DAMPED
    # (trends decay), and capped to the 2σ band so it never gets fantastical.
    daily_drift = (md.get("mom_20d", 0) / 100.0) / 20.0      # avg daily return, last ~20d
    damp = 0.4
    drift = daily_drift * h * damp
    drift = max(-2 * move_1s, min(2 * move_1s, drift))       # cap at ±2σ
    continuation_target = round(price * (1 + drift), 2)

    # Reversion level: where it likely pulls back to (support) on a bullish lean,
    # or where it bounces to (resistance) on a bearish lean.
    if lean == "Bearish":
        reversion_level = round(max(md.get("hi_20", price), md.get("ema50", price)), 2)
    else:
        reversion_level = round(min(md.get("lo_20", price), md.get("ema50", price)), 2)

    return {
        "horizon_days": h,
        "expected_move_pct": round(move_1s * 100, 1),
        "range_low": range_low, "range_high": range_high,
        "range_low_2s": range_low2, "range_high_2s": range_high2,
        "lean": lean, "lean_strength": strength,
        "continuation_target": continuation_target,
        "reversion_level": reversion_level,
    }
