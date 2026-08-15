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
    if catalyst and catalyst.get("kind") == "earnings":
        buys.append((f"Buy before earnings on {catalyst.get('when','')}",
                     "earnings is the catalyst — position ahead of the report"))
    if catalyst and catalyst.get("kind") == "ipo":
        buys.append((f"Wait until after the {catalyst.get('when','')} listing settles",
                     "let the first day of real trading establish a price range"))

    supports = []
    if lo20 < p:  supports.append((lo20, "recent 20-day low — price held here before"))
    if e50  < p:  supports.append((e50,  "50-day moving average — short-term trend support"))
    if e200 < p:  supports.append((e200, "200-day moving average — long-term trend support"))
    if lo52 < p:  supports.append((lo52, "52-week low — major floor"))
    supports.sort(key=lambda s: p - s[0])
    for lvl, why in supports[:2]:
        buys.append((f"Buy when price drops to ${lvl:.2f}", why))

    if p < e50:
        buys.append((f"Buy if price recovers above ${e50:.2f}",
                     "reclaiming the 50-day average is a strength signal"))

    # ── SELL triggers (resistance / measured targets / stop on THIS chart) ────
    if catalyst and catalyst.get("kind") == "earnings":
        sells.append((f"Sell into the earnings reaction ({catalyst.get('when','')})",
                      "take the move from the report; don't hold through it both ways"))

    resists = []
    if hi20 > p: resists.append((hi20, "recent 20-day high — price has stalled here before"))
    if hi52 > p: resists.append((hi52, "52-week high — major breakout level"))
    resists.sort(key=lambda s: s[0] - p)
    for lvl, why in resists[:2]:
        sells.append((f"Sell when price reaches ${lvl:.2f}", why))

    mult = 1.5 if tier == "short" else (3 if tier == "long" else 6)
    sells.append((f"Sell at ${p + mult*atr:.2f} (profit target)",
                  f"entry plus {mult}× this stock's typical daily range (${atr:.2f})"))

    stop = max(lo20, e50) if (lo20 < p or e50 < p) else round(p - 1.5*atr, 2)
    sells.append((f"Stop loss at ${stop:.2f}",
                  "below this price the setup is broken — exit and reassess"))

    fmt = lambda lst: [{"trigger": t, "why": w} for (t, w) in lst]
    return {
        "tier": tier, "direction": direction,
        "hold_label": hold_label, "exit_rule": exit_rule,
        "catalyst_stamp": (f"{catalyst.get('when','')}" if catalyst else ""),
        "buy_triggers":  fmt(buys[:5]),
        "sell_triggers": fmt(sells[:5]),
    }
