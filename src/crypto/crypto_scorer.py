"""
crypto_scorer.py — the crypto engine. Same philosophy as stocks:
  1) web/social intel (RSS + DuckDuckGo + Reddit) grouped per coin
  2) validate against Coinbase candles (real OHLC, 24/7)
  3) score per horizon, EWMA-smoothed for stability
  4) data-derived entry/exit triggers from each coin's OWN candle structure
Excludes BTC/LTC/USDT/BNB/USDC/SOL/ADA from picks.
"""
import logging
from collections import defaultdict
from datetime import datetime

from utils.state import pop_crypto_signals, push_crypto_alert, clear_crypto_alerts
from utils.store import signals_last_days, save_crypto_decision, recent_scores_for
from analysis.plan import build_plan
from analysis.scorer import smooth_score, _intel_points, _ewma, assign_unique_tiers
from analysis.ranking import category_benchmarks
from analysis.factors import compute_composites, factor_breakdown
from analysis.projection import project
from crypto.crypto_universe import crypto_pairs, crypto_symbols, EXCLUDE
from crypto.coinbase import metrics_from_candles

log = logging.getLogger("makeaibilli")
PER_TIER = 20   # 20 per horizon for crypto (smaller liquid universe)


def _gather(signals):
    intel = defaultdict(lambda: {"news":[],"reddit":[],"stocktwits":[],"sec":[],
        "congress":[],"influencer":[],"earnings":[],"ipo":[],"sources":set()})
    for s in signals:
        if s.get("asset") != "crypto": continue
        t = s.get("type","")
        bucket = {"crypto_news":"news","crypto_web":"news","crypto_social":"reddit"}.get(t)
        for sym in (s.get("tickers") or []):
            sym = sym.upper()
            d = intel[sym]; d["sources"].add(s.get("source",""))
            if bucket: d[bucket].append(s)
    return intel


def run_crypto_cycle():
    fresh = pop_crypto_signals(800)
    history = [s for s in signals_last_days(30) if s.get("type","").startswith("crypto")]
    intel = _gather(fresh + history)

    # Per-coin signal accumulation over the 30-day window, from the database.
    from collections import Counter
    sig_count = Counter()
    for s in history:
        for t in (s.get("tickers") or []):
            if t: sig_count[t.upper()] += 1

    pairs = [p for p in crypto_pairs() if p.replace("-USD","") not in EXCLUDE]
    log.info(f"  [crypto] fetching candles for {len(pairs)} coins...")

    # ── PASS A: fetch candles + intel per coin, build the universe ────────────
    market, intel_pts_map, meta = {}, {}, {}
    for pair in pairs:
        md = metrics_from_candles(pair)
        if not md:
            continue
        sym = md["ticker"]
        d = intel.get(sym, {"news":[],"reddit":[],"stocktwits":[],"sec":[],
            "congress":[],"influencer":[],"earnings":[],"ipo":[],"sources":set()})
        ipts, why, _ = _intel_points(d)
        market[sym] = md
        intel_pts_map[sym] = ipts
        meta[sym] = (d, why)

    if not market:
        log.warning("  [crypto] no candles returned")
        return {"short":0,"long":0,"xlong":0}

    # ── multi-factor composite across the crypto universe + regime ────────────
    bench = category_benchmarks(market)
    composites, regime = compute_composites(market, intel_pts_map,
                                            {s: None for s in market}, bench)
    log.info(f"  [crypto] regime: "
             f"{'TRENDING' if regime>0 else 'CHOPPY/DOWN' if regime<0 else 'NEUTRAL'}")

    # ── PASS B: assemble rows from composite scores (smoothed on bare symbol) ─
    scored = []
    for sym, md in market.items():
        d, why = meta[sym]
        comp = composites.get(sym, {"short":0,"long":0,"xlong":0})
        # Database signal-history bonus (sustained 30-day coverage = conviction).
        sig_bonus = min(sig_count.get(sym, 0) * 0.4, 12)
        cs, cl, cx = (min(100, comp["short"]+sig_bonus),
                      min(100, comp["long"]+sig_bonus),
                      min(100, comp["xlong"]+sig_bonus))
        # NOTE: per-asset DBs key crypto by bare symbol (BTC.db), so smoothing
        # must use the bare symbol — not the old "C:SYM" prefix. Smoothing blends
        # against this coin's stored DECISION history in the database.
        s_sc = smooth_score(sym, "short", cs)
        l_sc = smooth_score(sym, "long",  cl)
        x_sc = smooth_score(sym, "xlong", cx)

        bullets = list(why)
        bullets.append(f"7-day move: {'+' if md['mom_5d']>=0 else ''}{md['mom_5d']}% · "
                       f"24h volume {md['vol_ratio']}x its average")
        bullets.append(f"Trend: {'above' if md['above_200ema'] else 'below'} its 200-day and "
                       f"{'above' if md['above_50ema'] else 'below'} its 50-day average")
        scored.append({"sym":sym,"md":md,"why":bullets[:5],
                       "factors": factor_breakdown(md, None, intel_pts_map[sym], bench),
                       "short":s_sc,"long":l_sc,"xlong":x_sc})

    out = {"short":[], "long":[], "xlong":[]}
    # Assign each coin to its single best-fit tier (sym lives under "sym", but
    # assign_unique_tiers only reads the tier-score keys, so it works as-is).
    buckets = assign_unique_tiers(scored, PER_TIER)
    placed = set()
    for tier in out:
        for i, s in enumerate(buckets[tier]):
            md = s["md"]
            placed.add(md["ticker"])
            plan = build_plan(md["ticker"], tier, "bullish", None, md)
            alert = {
                "tier": tier, "rank": i+1, "ticker": md["ticker"],
                "name": f"{md['ticker']}/USD", "category": "Crypto",
                "price": md["price"], "change_pct": md["mom_1d"], "perf_7d": md["mom_5d"],
                "vol_ratio": md["vol_ratio"], "reasons": s["why"],
                "buy_triggers": plan["buy_triggers"], "sell_triggers": plan["sell_triggers"],
                "hold_label": plan["hold_label"], "exit_rule": plan["exit_rule"],
                "factors": s.get("factors", {}),
                "projection": project(md, tier),
                "timestamp": datetime.now().strftime("%I:%M %p ET"),
            }
            out[tier].append(alert)
            save_crypto_decision({"ticker":md["ticker"],"tier":tier,"score":s[tier],**alert})

    log.info(f"  [crypto] ranked: {len(out['short'])} short, {len(out['long'])} long, {len(out['xlong'])} extra-long")

    # Emerging coins: strongest recent momentum + volume surge (fresh interest),
    # EXCLUDING any coin already placed in a tier above so every tab is unique. Max 10.
    # Each gets the SAME alert shape as a tiered pick so View → detail shows
    # triggers, projection, factor breakdown, and enrichment.
    emerging = sorted([s for s in scored if s["md"]["ticker"] not in placed],
                      key=lambda s: s["md"]["mom_5d"] + s["md"]["vol_ratio"]*3,
                      reverse=True)[:10]
    em_list = []
    for s in emerging:
        md = s["md"]
        plan = build_plan(md["ticker"], "short", "bullish", None, md)
        em_list.append({
            "tier": "emerging", "ticker": md["ticker"],
            "name": f"{md['ticker']}/USD", "category": "Crypto",
            "price": md["price"], "change_pct": md["mom_1d"], "perf_7d": md["mom_5d"],
            "vol_ratio": md["vol_ratio"], "reasons": s["why"],
            "buy_triggers": plan["buy_triggers"], "sell_triggers": plan["sell_triggers"],
            "hold_label": plan["hold_label"], "exit_rule": plan["exit_rule"],
            "factors": s.get("factors", {}),
            "projection": project(md, "short"),
            "timestamp": datetime.now().strftime("%I:%M %p ET"),
        })
    try:
        from utils.state import set_crypto_emerging
        set_crypto_emerging(em_list)
    except Exception:
        pass

    clear_crypto_alerts()
    for tier in ("short","long","xlong"):
        for a in out[tier]:
            push_crypto_alert(a)
    return {k: len(v) for k,v in out.items()}
