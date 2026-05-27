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
from analysis.scorer import _tier_scores, smooth_score, _intel_points, _ewma
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
    history = [s for s in signals_last_days(15) if s.get("type","").startswith("crypto")]
    intel = _gather(fresh + history)

    pairs = [p for p in crypto_pairs() if p.replace("-USD","") not in EXCLUDE]
    log.info(f"  [crypto] fetching candles for {len(pairs)} coins...")

    scored = []
    for pair in pairs:
        md = metrics_from_candles(pair)
        if not md:
            continue
        sym = md["ticker"]
        d = intel.get(sym, {"news":[],"reddit":[],"stocktwits":[],"sec":[],
            "congress":[],"influencer":[],"earnings":[],"ipo":[],"sources":set()})
        ipts, why, _ = _intel_points(d)
        s_sc, l_sc, x_sc = _tier_scores(md, None, ipts)
        s_sc = smooth_score(f"C:{sym}", "short", s_sc)
        l_sc = smooth_score(f"C:{sym}", "long",  l_sc)
        x_sc = smooth_score(f"C:{sym}", "xlong", x_sc)

        bullets = list(why)
        bullets.append(f"7-day move: {'+' if md['mom_5d']>=0 else ''}{md['mom_5d']}% · "
                       f"24h volume {md['vol_ratio']}x its average")
        bullets.append(f"Trend: {'above' if md['above_200ema'] else 'below'} its 200-day and "
                       f"{'above' if md['above_50ema'] else 'below'} its 50-day average")
        scored.append({"sym":sym,"md":md,"why":bullets[:5],
                       "short":s_sc,"long":l_sc,"xlong":x_sc})

    out = {"short":[], "long":[], "xlong":[]}
    for tier in out:
        members = sorted(scored, key=lambda s: s[tier], reverse=True)[:PER_TIER]
        for i, s in enumerate(members):
            md = s["md"]
            plan = build_plan(md["ticker"], tier, "bullish", None, md)
            alert = {
                "tier": tier, "rank": i+1, "ticker": md["ticker"],
                "name": f"{md['ticker']}/USD", "category": "Crypto",
                "price": md["price"], "change_pct": md["mom_1d"], "perf_7d": md["mom_5d"],
                "vol_ratio": md["vol_ratio"], "reasons": s["why"],
                "buy_triggers": plan["buy_triggers"], "sell_triggers": plan["sell_triggers"],
                "hold_label": plan["hold_label"], "exit_rule": plan["exit_rule"],
                "timestamp": datetime.now().strftime("%I:%M %p ET"),
            }
            out[tier].append(alert)
            save_crypto_decision({"ticker":md["ticker"],"tier":tier,"score":s[tier],**alert})

    log.info(f"  [crypto] ranked: {len(out['short'])} short, {len(out['long'])} long, {len(out['xlong'])} extra-long")

    # Emerging coins: strongest recent momentum + volume surge (signals of fresh interest), max 10
    emerging = sorted(scored, key=lambda s: s["md"]["mom_5d"] + s["md"]["vol_ratio"]*3,
                      reverse=True)[:10]
    em_list = [{"ticker": s["md"]["ticker"], "price": s["md"]["price"],
                "mom_5d": s["md"]["mom_5d"], "vol_ratio": s["md"]["vol_ratio"]}
               for s in emerging]
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
