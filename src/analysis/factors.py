"""
factors.py — multi-factor composite scoring layered on top of the intel-first
pipeline.

Grounded in standard, public quant methodology:
  • Momentum     — 12-1 month return (Jegadeesh & Titman 1993): the 12-month
                   return ending ~1 month ago, skipping the most recent month
                   because the last month tends to mean-revert. Blended with
                   6-month and 1-month momentum.
  • Trend        — price vs its 50/200-day EMAs, golden-cross posture, and
                   position within the 52-week range. Rewards clean uptrends.
  • Mean rev.    — short-horizon contrarian: oversold (low RSI / near the
                   20-day low) scores HIGH because we want to buy the dip on
                   short horizons.
  • Volume       — relative volume (today vs its own 20-day average): conviction.
  • Rel. strength— the asset's 5-day move minus its category's average move.
  • Intel        — the existing news / Reddit / filings / congress score.

Each factor is converted to a z-score ACROSS THE UNIVERSE so they're comparable,
then blended with per-tier weights (the "BarBell" idea — different horizons want
different, low-correlation factors). A market-regime tilt (derived from breadth,
no extra network call) shifts weight toward momentum in trending markets and
toward mean-reversion in choppy ones.

Honest note: every factor here is in every quant fund's playbook. This shifts
the odds and stabilizes ranking; it does not predict the future or guarantee
returns. Intel stays the lead (it gates candidacy and is weighted); factors
refine the ordering within the intel-surfaced set.
"""

import statistics as _stats

# Per-tier factor weights. Each dict sums to 1.0. Factors absent from a tier
# carry zero weight there (e.g. no momentum on the 0-72h horizon — at that
# range momentum is counterproductive and mean-reversion dominates; no
# mean-reversion on the multi-month horizon — it's just noise there).
WEIGHTS = {
    "short": {"meanrev": 0.40, "volume": 0.25, "intel": 0.20, "relstr": 0.15},
    "long":  {"momentum": 0.30, "trend": 0.25, "intel": 0.20, "volume": 0.15, "meanrev": 0.10},
    "xlong": {"momentum": 0.45, "trend": 0.35, "intel": 0.20},
}

# Which factors the regime tilt touches.
_TREND_FACTORS = ("momentum", "trend")
_REVERSION_FACTORS = ("meanrev",)


# ── raw factor extraction ──────────────────────────────────────────────────────

def _range_pos(price, lo, hi):
    """Position within a [lo, hi] band, 0..1. 0 = at the low, 1 = at the high."""
    if hi is None or lo is None or hi <= lo:
        return 0.5
    return max(0.0, min(1.0, (price - lo) / (hi - lo)))


def raw_factors(md: dict, ta: dict | None, intel_pts: float, bench: dict) -> dict:
    """Compute the six raw factor values for one asset (pre-normalization)."""
    price = md["price"]

    # Momentum: blend long (12-1), medium (6mo), short (1mo). Long weighted most.
    mom = (0.5 * md.get("mom_12_1", md.get("mom_20d", 0))
           + 0.3 * md.get("mom_120d", md.get("mom_20d", 0))
           + 0.2 * md.get("mom_20d", 0))

    # Trend: distance above the 200- and 50-day, plus 52-week range position.
    e200 = md.get("ema200", price) or price
    e50  = md.get("ema50", price) or price
    dist200 = (price / e200 - 1) * 100 if e200 else 0
    dist50  = (price / e50 - 1) * 100 if e50 else 0
    rng52   = _range_pos(price, md.get("lo_52w"), md.get("hi_52w"))
    golden  = 5 if md.get("ema50", 0) > md.get("ema200", 0) else -5
    trend = dist200 + 0.5 * dist50 + 20 * rng52 + golden

    # Mean reversion: oversold scores HIGH. Use RSI when we have deep TA,
    # otherwise a pseudo-RSI from the 20-day range position so every asset is
    # measured on the same scale.
    if ta and ta.get("rsi14") is not None:
        rsi_like = ta["rsi14"]
        below_vwap = 1 if ta.get("above_vwap") is False else 0
    else:
        rsi_like = _range_pos(price, md.get("lo_20"), md.get("hi_20")) * 100
        below_vwap = 0
    meanrev = (50 - rsi_like) + 8 * below_vwap     # high when oversold / below VWAP

    # Volume: relative volume (already a ratio vs its own 20-day average).
    volume = md.get("vol_ratio", 1.0)

    # Relative strength: 5-day move minus the category's average 5-day move.
    relstr = md.get("mom_5d", 0) - bench.get(md.get("category", ""), 0)

    return {
        "momentum": mom,
        "trend":    trend,
        "meanrev":  meanrev,
        "volume":   volume,
        "relstr":   relstr,
        "intel":    float(intel_pts),
    }


# ── normalization + regime ──────────────────────────────────────────────────────

def _zscore_universe(raws: dict) -> dict:
    """raws = {ticker: {factor: value}} -> {ticker: {factor: zscore}} clamped ±3."""
    if not raws:
        return {}
    factors = ("momentum", "trend", "meanrev", "volume", "relstr", "intel")
    stats = {}
    for f in factors:
        vals = [r[f] for r in raws.values()]
        mean = _stats.fmean(vals) if vals else 0.0
        try:
            sd = _stats.pstdev(vals) if len(vals) > 1 else 0.0
        except Exception:
            sd = 0.0
        stats[f] = (mean, sd)
    z = {}
    for t, r in raws.items():
        zt = {}
        for f in factors:
            mean, sd = stats[f]
            zt[f] = max(-3.0, min(3.0, (r[f] - mean) / sd)) if sd > 1e-9 else 0.0
        z[t] = zt
    return z


def market_regime(market: dict) -> int:
    """+1 trending (favor momentum), -1 choppy/down (favor mean-reversion), 0 neutral.

    Derived from market breadth and average 20-day momentum across the universe
    we're already pricing — no extra network call. This is the standard
    'is the market above its trend' switch, approximated by breadth.
    """
    if not market:
        return 0
    n = len(market)
    above200 = sum(1 for m in market.values() if m.get("above_200ema")) / n
    avg_mom20 = _stats.fmean([m.get("mom_20d", 0) for m in market.values()])
    if above200 >= 0.55 and avg_mom20 > 0:
        return 1
    if above200 <= 0.45 or avg_mom20 < -2:
        return -1
    return 0


def _tilted_weights(tier: str, regime: int) -> dict:
    """Apply the regime tilt to a tier's weights, then renormalize to sum 1."""
    w = dict(WEIGHTS[tier])
    if regime != 0:
        tf = 1.3 if regime > 0 else 0.7      # trend/momentum multiplier
        rf = 0.7 if regime > 0 else 1.3      # mean-reversion multiplier
        for f in _TREND_FACTORS:
            if f in w: w[f] *= tf
        for f in _REVERSION_FACTORS:
            if f in w: w[f] *= rf
        total = sum(w.values())
        if total > 0:
            w = {k: v / total for k, v in w.items()}
    return w


# ── public: composite scores ────────────────────────────────────────────────────

def compute_composites(market: dict, intel_pts: dict, ta_map: dict, bench: dict):
    """
    Returns (composites, regime) where:
      composites = {ticker: {"short":0-100, "long":0-100, "xlong":0-100}}
      regime     = -1 | 0 | +1

    market    : {ticker: md}
    intel_pts : {ticker: intel points (float)}
    ta_map    : {ticker: ta dict or None}
    bench     : {category: avg 5-day momentum}
    """
    raws = {t: raw_factors(md, ta_map.get(t), intel_pts.get(t, 0.0), bench)
            for t, md in market.items()}
    z = _zscore_universe(raws)
    regime = market_regime(market)

    tier_w = {tier: _tilted_weights(tier, regime) for tier in WEIGHTS}

    composites = {}
    for t, zt in z.items():
        row = {}
        for tier, w in tier_w.items():
            composite_z = sum(w.get(f, 0.0) * zt.get(f, 0.0) for f in w)
            # map z (~[-3,3]) to 0-100; 12 ≈ one z-unit ≈ 12 points
            row[tier] = round(max(0.0, min(100.0, 50 + 12 * composite_z)), 2)
        composites[t] = row
    return composites, regime


def factor_breakdown(md: dict, ta: dict | None, intel_pts: float, bench: dict) -> dict:
    """Human-readable raw factors for one asset — for the 'why' panel / debugging."""
    r = raw_factors(md, ta, intel_pts, bench)
    return {
        "Momentum (12-1 blend)": round(r["momentum"], 1),
        "Trend strength":        round(r["trend"], 1),
        "Mean-reversion (oversold↑)": round(r["meanrev"], 1),
        "Volume vs avg":         round(r["volume"], 2),
        "Relative strength":     round(r["relstr"], 1),
        "Intel":                 round(r["intel"], 1),
    }
