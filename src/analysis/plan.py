"""
plan.py v3 — DATA-DERIVED, stock-specific entry/exit triggers.

No generic clock times. Every trigger is computed from THIS stock's own price
structure (support/resistance, swing levels, moving averages, ATR) plus its
real scheduled catalysts (earnings/IPO dates). Returns 2-5 buy and 2-5 sell
triggers, each tied to a concrete price level or date specific to the stock.
"""

TIER_HOLD = {
    "short": ("0–72 hours", "Exit within ~3 days"),
    "long":  ("4–30 days",  "Hold the multi-day swing; reassess weekly"),
    "xlong": ("1–18 months","Position trade; review monthly, exit on thesis break"),
}


def _near(a, b, pct=2.5):
    return abs(a - b) / b * 100 <= pct if b else False


def build_plan(ticker, tier, direction, catalyst, md):
    """md = market metrics for THIS stock (price, ema50/200, hi/lo_20, hi/lo_52w, atr)."""
    hold_label, exit_rule = TIER_HOLD.get(tier, TIER_HOLD["short"])
    p     = md["price"]
    e50   = md.get("ema50", p);  e200 = md.get("ema200", p)
    hi20  = md.get("hi_20", p);  lo20 = md.get("lo_20", p)
    hi52  = md.get("hi_52w", p); lo52 = md.get("lo_52w", p)
    atr   = md.get("atr", round(p*0.02, 2))

    buys, sells = [], []

    # ── BUY triggers (each tied to a level on THIS chart) ─────────────────────
    # 1. Scheduled catalyst (real, stock-specific date)
    if catalyst and catalyst.get("kind") == "earnings":
        buys.append((f"Ahead of earnings {catalyst.get('when','')}",
                     f"its own scheduled report — the move is event-driven, not a clock pattern"))
    if catalyst and catalyst.get("kind") == "ipo":
        buys.append((f"After {catalyst.get('when','')} listing settles",
                     "let its first real prints establish a range"))

    # 2. Nearest support beneath price (pick the closest meaningful one)
    supports = []
    if lo20 < p:  supports.append((lo20, "20-day support (recent floor it held)"))
    if e50  < p:  supports.append((e50,  "50-day moving average (dynamic support)"))
    if e200 < p:  supports.append((e200, "200-day line (major trend support)"))
    if lo52 < p:  supports.append((lo52, "52-week low (deep-value floor)"))
    supports.sort(key=lambda s: p - s[0])          # closest first
    for lvl, why in supports[:2]:
        buys.append((f"Buy the dip near ${lvl:.2f}", why))

    # 3. Breakout reclaim (if price is below a key MA, buying the reclaim)
    if p < e50:
        buys.append((f"On a reclaim back above ${e50:.2f}", "loss of 50-day flips to strength when recovered"))

    # ── SELL triggers (resistance / measured targets on THIS chart) ───────────
    if catalyst and catalyst.get("kind") == "earnings":
        sells.append((f"Into the post-earnings move ({catalyst.get('when','')})",
                      "sell the reaction; don't round-trip the report"))

    resists = []
    if hi20 > p: resists.append((hi20, "20-day high (recent ceiling)"))
    if hi52 > p: resists.append((hi52, "52-week high (breakout level)"))
    resists.sort(key=lambda s: s[0] - p)            # closest first
    for lvl, why in resists[:2]:
        sells.append((f"Trim into resistance ${lvl:.2f}", why))

    # measured target off ATR (volatility-scaled, specific to this stock)
    mult = 1.5 if tier == "short" else (3 if tier == "long" else 6)
    sells.append((f"Measured target ${p + mult*atr:.2f}",
                  f"entry + {mult}× its ATR (${atr:.2f}/day) — sized to its own volatility"))
    # protective stop tied to its structure
    stop = max(lo20, e50) if (lo20 < p or e50 < p) else round(p - 1.5*atr, 2)
    sells.append((f"Cut if it loses ${stop:.2f}", "structure break — the setup is wrong below here"))

    fmt = lambda lst: [{"trigger": t, "why": w} for (t, w) in lst]
    return {
        "tier": tier, "direction": direction,
        "hold_label": hold_label, "exit_rule": exit_rule,
        "catalyst_stamp": (f"📅 {catalyst.get('when','')}" if catalyst else ""),
        "buy_triggers":  fmt(buys[:5]),
        "sell_triggers": fmt(sells[:5]),
    }
