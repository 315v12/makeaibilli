"""
scorer.py — v2 multi-pass engine producing a 90-stock list every scan:
  30 SHORT (0-72h) · 30 LONG (4-30d) · 30 EXTRA-LONG (1-18mo).

Flow (mirrors the requested pipeline):
  1) web scraping      -> signals saved to the 15-day SQLite store
  2) analyze/process   -> first-pass intel score per ticker (incl. 15-day history)
  3) reprocess vs market performance (last 7 days, all stocks except crypto)
  4) reprocess again   -> relative-strength refinement, assign to best tier, rank

No dollar values. No risk/reward. Crypto excluded from picks (its news still counts).
"""

import os
from collections import defaultdict
from datetime import datetime

from utils.state import (pop_signals, push_alert, clear_alerts, get_watchlist, get_client)
from utils.store import signals_last_days, save_decision
from analysis.technical import analyze, clear_cache
from analysis.options import determine_direction
from analysis.plan import build_plan
from analysis.ranking import fetch_market_data, category_benchmarks
from analysis.universe import all_tickers
from analysis.fortune500 import fortune_tickers
from analysis.names import name_of, register_name, CRYPTO_BLOCK
import logging
log = logging.getLogger("makeaibilli")

PER_TIER = 30


def _gather(signals):
    """Group signals by ticker into an intel profile."""
    intel = defaultdict(lambda: {"news":[],"reddit":[],"stocktwits":[],"sec":[],
        "congress":[],"influencer":[],"earnings":[],"ipo":[],"sources":set()})
    for s in signals:
        t = s.get("type","")
        for tk in (s.get("tickers") or []):
            if not tk or not (1 <= len(tk) <= 5): continue
            tk = tk.upper()
            d = intel[tk]; d["sources"].add(s.get("source",""))
            if s.get("company_name"): register_name(tk, s["company_name"])
            bucket = {"news":"news","social_reddit":"reddit","social_stocktwits":"stocktwits",
                      "sec_8k":"sec","sec_form4":"sec","congress_trade":"congress",
                      "influencer":"influencer","earnings":"earnings","ipo":"ipo"}.get(t)
            if bucket: d[bucket].append(s)
    return intel


def _intel_points(d):
    """First-pass: how strongly the web (incl. 15-day history) points at this name."""
    pts, why, cat = 0, [], None
    if d["earnings"]:
        pts += 22; why.append(f"Earnings catalyst: {d['earnings'][0]['headline'][:90]}")
        cat = {"kind":"earnings","when":d['earnings'][0].get('headline','').split('(')[0]}
    if d["ipo"]:
        pts += 18; why.append(f"Upcoming IPO: {d['ipo'][0]['headline'][:90]}")
        cat = {"kind":"ipo","when":d['ipo'][0].get('ipo_date','')}
    if d["congress"]:
        pts += 12; why.append(f"Congressional buying: {d['congress'][0]['headline'][:90]}")
    if d["influencer"]:
        i=d["influencer"][0]; pts += min(i.get("sentiment",0)*3,12)
        why.append(f"Market mover {i.get('influencer','')}: {i['headline'][:80]}")
    alln = d["news"]+d["sec"]
    if alln:
        m=max(s.get("sentiment",0) for s in alln); pts += min(max(m*4,0),14)
        if m>=1: why.append(f"News flow: {alln[0]['headline'][:90]}")
    if d["reddit"]:
        mc=sum(s.get("mention_count",1) for s in d["reddit"]); pts += min(mc,8)
        if mc>=4: why.append(f"Retail buzz building ({mc} mentions across forums)")
    if d["stocktwits"]:
        br=d["stocktwits"][0].get("bull_ratio",0.5)
        if br>=0.65: pts+=6; why.append(f"StockTwits {int(br*100)}% bullish")
    return pts, why, cat


def _ewma(values: list[float], halflife: float = 2.0) -> float:
    """Exponentially-weighted mean (newest first). Used to smooth scores over scans."""
    if not values:
        return 0.0
    import math
    decay = 0.5 ** (1.0 / halflife)
    num = den = 0.0
    w = 1.0
    for v in values:               # values[0] = newest
        num += w * v; den += w; w *= decay
    return num / den if den else 0.0


def smooth_score(ticker: str, tier: str, new_score: float, alpha: float = 0.45) -> float:
    """
    Blend this scan's raw score with the stock's recent history so rankings are
    stable scan-to-scan (a #1 won't vanish next cycle unless something real changed).
    alpha = weight on the NEW score (0.45 => 55% weight on history = sticky).
    """
    from utils.store import recent_scores_for
    hist = recent_scores_for(ticker, tier, limit=8)
    if not hist:
        return new_score
    return round(alpha * new_score + (1 - alpha) * _ewma(hist), 2)


def _tier_scores(md, ta, ipts):
    """Pass 3-4: blend intel with market performance into per-tier scores."""
    short = ipts
    if md["vol_ratio"]>=2: short+=12
    elif md["vol_ratio"]>=1.5: short+=7
    if md["mom_5d"]>3: short+=10
    rsi = ta.get("rsi14",50) if ta else 50
    if 28<=rsi<=42: short+=10
    elif rsi>=68: short+=8
    if ta and ta.get("macd_crossover"): short+=6

    lng = int(ipts*0.5)
    if md["above_50ema"]: lng+=15
    if md["mom_20d"]>0: lng+=15
    if 0<md["mom_5d"]<15: lng+=10
    if md["above_200ema"]: lng+=10

    xl = int(ipts*0.3)
    if md["above_200ema"]: xl+=30
    if md["ema50"]>md["ema200"]: xl+=20
    if md["mom_20d"]>0: xl+=15
    if -5<=md["mom_20d"]<=40: xl+=10

    return min(short,100), min(lng,100), min(xl,100)


def run_scoring_cycle(include_fortune=False):
    clear_cache()

    # ── 1) intel: fresh queue + 15-day history from the DB ────────────────────
    fresh = pop_signals(800)
    history = signals_last_days(15)
    intel = _gather(fresh + history)

    # Candidate pool: web-surfaced + curated universe + watchlist (+ Fortune 500 on the slow clock)
    # KNOWN universe of real, tradeable tickers (curated + S&P 500 + watchlist).
    # We validate intel-surfaced tickers against this so junk words extracted from
    # text ("THE","GPU","VWAP","ONLY"...) never get sent to Yahoo.
    known = set(all_tickers()) | set(fortune_tickers()) | set(get_watchlist() or [])
    surfaced_valid = {t for t in intel.keys() if t in known}     # only real names from chatter
    candidates = surfaced_valid | set(all_tickers()) | set(get_watchlist() or [])
    if include_fortune:
        candidates |= set(fortune_tickers())
    # Drop crypto-native names from the *recommendation* pool (their news still counted above)
    candidates = {c for c in candidates if c not in CRYPTO_BLOCK and 1 <= len(c) <= 5}
    # Hardware guard: cap how many we price-validate per scan (intel names prioritized)
    MAX_CANDIDATES = int(__import__("os").getenv("MAX_CANDIDATES", 150))
    if len(candidates) > MAX_CANDIDATES:
        intel_first = [t for t in intel.keys() if t in candidates and t not in CRYPTO_BLOCK]
        rest = [t for t in candidates if t not in set(intel_first)]
        candidates = set(intel_first + rest[:max(0, MAX_CANDIDATES - len(intel_first))])

    # ── 2-3) market validation (filters useless/illiquid; gives 7-day perf) ───
    log.info(f"  validating {len(candidates)} candidates against market data...")
    market = fetch_market_data(list(candidates))
    if not market:
        log.warning("  no stocks passed market filter (yfinance returned nothing)")
        return {"short":0,"long":0,"xlong":0}
    log.info(f"  {len(market)} liquid stocks passed; running technical analysis...")
    bench = category_benchmarks(market)

    scored = []
    # Deep TA only on the strongest intel names + always the curated set (perf cap)
    rank_helper = sorted(market.items(),
        key=lambda kv: (_intel_points(intel.get(kv[0],{"news":[],"reddit":[],"stocktwits":[],
            "sec":[],"congress":[],"influencer":[],"earnings":[],"ipo":[],"sources":set()}))[0]
            + max(kv[1]["mom_5d"],0)), reverse=True)
    deep_cap = 80 if include_fortune else 40
    deep = dict(rank_helper[:deep_cap])   # cap deep TA for the iMac

    for ticker, md in market.items():
        d = intel.get(ticker, {"news":[],"reddit":[],"stocktwits":[],"sec":[],
            "congress":[],"influencer":[],"earnings":[],"ipo":[],"sources":set()})
        ipts, why, cat = _intel_points(d)
        ta = analyze(ticker) if ticker in deep else None
        s_sc, l_sc, x_sc = _tier_scores(md, ta, ipts)
        # Smooth against recent history so ranks don't whipsaw every 15 min
        s_sc = smooth_score(ticker, "short", s_sc)
        l_sc = smooth_score(ticker, "long",  l_sc)
        x_sc = smooth_score(ticker, "xlong", x_sc)
        rs = round(md["mom_5d"] - bench.get(md["category"],0), 2)

        # decision bullets (always >=2 extra beyond the intel reasons)
        bullets = list(why)
        bullets.append(f"7-day performance: {'+' if md['mom_5d']>=0 else ''}{md['mom_5d']}% "
                       f"({'beating' if rs>=0 else 'lagging'} its {md['category']} peers by "
                       f"{'+' if rs>=0 else ''}{rs}%)")
        bullets.append(f"Trend posture: {'above' if md['above_200ema'] else 'below'} the 200-day "
                       f"and {'above' if md['above_50ema'] else 'below'} the 50-day moving average")
        if cat is None and d["news"]:
            bullets.append(f"Most recent headline: {d['news'][0]['headline'][:90]}")

        scored.append({"ticker":ticker,"md":md,"d":d,"cat":cat,"why":bullets[:5],
                       "rs":rs,"short":s_sc,"long":l_sc,"xlong":x_sc,
                       "direction": determine_direction(ta,0,
                           d["stocktwits"][0].get("bull_ratio",0.5) if d["stocktwits"] else 0.5)
                           if ta else "bullish"})

    # ── 4) rank INDEPENDENTLY per tier, top 30 each (a stock may fit >1 horizon)
    out = {"short":[], "long":[], "xlong":[]}
    for tier in out:
        members = sorted(scored, key=lambda s: s[tier], reverse=True)[:PER_TIER]
        for i, s in enumerate(members):
            s = dict(s)            # copy so per-tier fields don't collide
            s["best_score"] = s[tier]
            md = s["md"]
            plan = build_plan(s["ticker"], tier, s["direction"], s["cat"], md)
            alert = {
                "tier": tier, "rank": i+1, "ticker": s["ticker"],
                "name": name_of(s["ticker"]), "category": md["category"],
                "price": md["price"], "change_pct": md["mom_1d"],
                "perf_7d": md["mom_5d"], "rs_vs_category": s["rs"],
                "direction": s["direction"], "reasons": s["why"],
                "sources": list(s["d"]["sources"])[:5],
                "buy_triggers": plan["buy_triggers"], "sell_triggers": plan["sell_triggers"],
                "hold_label": plan["hold_label"], "exit_rule": plan["exit_rule"],
                "catalyst_stamp": plan["catalyst_stamp"],
                "timestamp": datetime.now().strftime("%I:%M %p ET"),
            }
            out[tier].append(alert)
            save_decision({"ticker":s["ticker"],"tier":tier,"score":s["best_score"],**alert})

    log.info(f"  ranked: {len(out['short'])} short, {len(out['long'])} long, {len(out['xlong'])} extra-long")
    # publish: replace the board
    clear_alerts()
    for tier in ("short","long","xlong"):
        for a in out[tier]:
            push_alert(a)
    return {k: len(v) for k,v in out.items()}
