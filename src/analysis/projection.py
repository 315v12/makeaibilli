"""
projection.py — forward-looking expected-move projection.

HONEST FRAMING (read this before trusting any number it produces):
No model predicts an exact future price. What this computes is a PROBABILITY
RANGE for where an asset is likely to trade over a horizon, from two ingredients
every quant desk uses:

  • Volatility (how far it typically moves) — from ATR. One day's expected
    move ≈ ATR. Over H days the band widens with √H (variance adds with time).
  • Drift (which way momentum is leaning) — a small, capped directional bias
    from recent momentum. Momentum persists on average but reverses often, so
    drift is deliberately modest and never dominates the range.

The output is a center estimate and a 1-sigma band (≈68% of outcomes if moves
were normal) plus a wider 2-sigma band (≈95%). Real markets have fat tails and
overnight gaps, so treat these as rough odds, not promises. Earnings, news, and
halts can blow through any band.

This is forward-looking by construction: it projects the NEXT session / the
horizon ahead, not what already happened. History is the input; the expected
move is the output.
"""

import math

# Trading-day horizon used for each tier's projection.
TIER_HORIZON = {"short": 2, "long": 14, "xlong": 90}

# Cap on how much daily drift momentum can imply (fractional, per day).
_MAX_DRIFT_PER_DAY = 0.006
# Cap on TOTAL drift over the horizon — momentum decays, it does not compound
# linearly for months. Keeps the center estimate realistic.
_MAX_TOTAL_DRIFT = {"short": 0.04, "long": 0.12, "xlong": 0.25}


def _daily_drift(md: dict) -> float:
    """Fractional expected drift per day from momentum, capped. Blends the
    20-day and 5-day momentum (both expressed as % moves over their window)."""
    mom20 = md.get("mom_20d", 0) / 100.0     # total fractional move over 20d
    mom5  = md.get("mom_5d", 0) / 100.0       # over 5d
    per_day = 0.5 * (mom20 / 20.0) + 0.5 * (mom5 / 5.0)
    return max(-_MAX_DRIFT_PER_DAY, min(_MAX_DRIFT_PER_DAY, per_day))


def project(md: dict, tier: str) -> dict:
    """Expected-move projection for one asset over its tier's horizon.

    Returns a dict with the center estimate, 1-sigma low/high (likely range),
    2-sigma low/high (wider range), the horizon in days, and an expected-return %.
    All prices rounded sensibly for the asset's price scale.
    """
    price = float(md.get("price", 0) or 0)
    if price <= 0:
        return {}
    H = TIER_HORIZON.get(tier, 5)
    atr = float(md.get("atr", price * 0.02) or price * 0.02)

    sigma_day = atr / price                      # 1-day fractional vol proxy
    sigma_h   = sigma_day * math.sqrt(H)         # widens with √time
    exp_move  = price * sigma_h                   # 1-sigma move in $

    drift = _daily_drift(md) * H                  # fractional drift over horizon
    cap = _MAX_TOTAL_DRIFT.get(tier, 0.15)        # momentum decays — cap it
    drift = max(-cap, min(cap, drift))
    center = price * (1 + drift)

    rnd = (lambda v: round(v, 4)) if price < 10 else (lambda v: round(v, 2))
    return {
        "horizon_days": H,
        "center":  rnd(center),
        "low_1s":  rnd(center - exp_move),
        "high_1s": rnd(center + exp_move),
        "low_2s":  rnd(center - 2 * exp_move),
        "high_2s": rnd(center + 2 * exp_move),
        "exp_return_pct": round(drift * 100, 2),
        "band_pct": round(sigma_h * 100, 1),       # ± size of the 1-sigma band, %
    }


def projection_sentence(proj: dict, tier: str) -> str:
    """One-line plain-English summary for the UI."""
    if not proj:
        return ""
    H = proj["horizon_days"]
    horizon_word = {"short": "next ~2 sessions", "long": "next ~2-3 weeks",
                    "xlong": "next ~3 months"}.get(tier, f"next {H} sessions")
    bias = ("higher" if proj["exp_return_pct"] > 0.2 else
            "lower" if proj["exp_return_pct"] < -0.2 else "roughly flat")
    return (f"Over the {horizon_word}, the data leans {bias}: a likely range of "
            f"${proj['low_1s']}–${proj['high_1s']} (±{proj['band_pct']}%), "
            f"centered near ${proj['center']}. Wider band ${proj['low_2s']}–${proj['high_2s']}.")
