"""
asset_enricher.py — per-asset profile enrichment from public sources.

For stocks: Wikipedia REST summary + Wikidata structured facts (founders,
inception date, headquarters).

For crypto: CoinGecko free API (description, genesis date, homepage,
categories, country of origin).

Why no "why invest" / "future impact" bullets:
Those require editorial judgment — fabricating them risks giving fake
confidence to real money decisions. This module collects FACTS that let the
user form their own view (description of what the company actually does,
who founded it, when, where it's based, links to read more). The dashboard
shows these facts as bullets in the asset's detail view.

Caching: results are written to /data/enrich/{kind}_{key}.json with a 30-day
TTL so we don't hammer Wikipedia/CoinGecko on every page view.
"""

import os, re, json, requests
from datetime import datetime, timedelta

ENRICH_DIR    = "/data/enrich"
TTL_DAYS      = 30
WIKI_SUMMARY  = "https://en.wikipedia.org/api/rest_v1/page/summary/"
WIKIDATA_ITEM = "https://www.wikidata.org/wiki/Special:EntityData/{}.json"
COINGECKO     = "https://api.coingecko.com/api/v3"
HEADERS       = {"User-Agent": "makeaibilli/4.x (asset enricher; non-commercial)"}

_SAFE = re.compile(r'[^A-Za-z0-9._-]')

# in-process cache for Wikidata label lookups (lots of small queries per company)
_label_cache: dict = {}
# in-process cache for the CoinGecko coin list (one fetch, used for all crypto lookups)
_coin_list_cache: list = []


# ── cache helpers ─────────────────────────────────────────────────────────────

def _cache_path(kind: str, key: str) -> str:
    os.makedirs(ENRICH_DIR, exist_ok=True)
    safe = _SAFE.sub("_", key.upper())[:40]
    return os.path.join(ENRICH_DIR, f"{kind}_{safe}.json")


def _read_cache(kind: str, key: str):
    p = _cache_path(kind, key)
    if not os.path.exists(p):
        return None
    try:
        data = json.load(open(p))
        ts = datetime.fromisoformat(data.get("_cached_at", "2020-01-01T00:00"))
        if datetime.utcnow() - ts < timedelta(days=TTL_DAYS):
            return data
    except Exception:
        pass
    return None


def _write_cache(kind: str, key: str, data: dict):
    try:
        data["_cached_at"] = datetime.utcnow().isoformat()
        json.dump(data, open(_cache_path(kind, key), "w"))
    except Exception:
        pass


# ── Wikipedia / Wikidata helpers (for stocks) ────────────────────────────────

def _wiki_summary(title: str) -> dict:
    if not title: return {}
    try:
        r = requests.get(WIKI_SUMMARY + title.replace(" ", "_"),
                         headers=HEADERS, timeout=8)
        if r.status_code == 200:
            return r.json() or {}
    except Exception:
        pass
    return {}


def _wikidata_entity(qid: str) -> dict:
    if not qid: return {}
    try:
        r = requests.get(WIKIDATA_ITEM.format(qid), headers=HEADERS, timeout=8)
        if r.status_code == 200:
            return r.json().get("entities", {}).get(qid, {}) or {}
    except Exception:
        pass
    return {}


def _wikidata_label(qid: str) -> str:
    if not qid: return ""
    if qid in _label_cache:
        return _label_cache[qid]
    e = _wikidata_entity(qid)
    lbl = e.get("labels", {}).get("en", {}).get("value", "")
    _label_cache[qid] = lbl
    return lbl


def _wikidata_facts(qid: str) -> dict:
    """Pull founders (P112), inception (P571), headquarters (P159), CEO (P169),
    owners (P127), country (P17) from a company's Wikidata entity."""
    e = _wikidata_entity(qid)
    claims = e.get("claims", {})

    def _ids(prop):
        out = []
        for c in claims.get(prop, []):
            v = c.get("mainsnak", {}).get("datavalue", {}).get("value", {})
            if isinstance(v, dict) and v.get("id"):
                out.append(v["id"])
        return out

    def _time(prop):
        for c in claims.get(prop, [])[:1]:
            t = c.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("time", "")
            if t: return t.lstrip("+").split("T")[0]
        return ""

    founders = [lbl for lbl in (_wikidata_label(q) for q in _ids("P112")) if lbl]
    ceos     = [lbl for lbl in (_wikidata_label(q) for q in _ids("P169")) if lbl]
    owners   = [lbl for lbl in (_wikidata_label(q) for q in _ids("P127")) if lbl]
    hq_ids   = _ids("P159")
    country_ids = _ids("P17")
    return {
        "founders":     founders[:5],
        "founded":      _time("P571"),
        "headquarters": _wikidata_label(hq_ids[0]) if hq_ids else "",
        "country":      _wikidata_label(country_ids[0]) if country_ids else "",
        "ceo":          ceos[0] if ceos else "",
        "owners":       owners[:5],
    }


# ── public: stock enrichment ──────────────────────────────────────────────────

def enrich_stock(ticker: str, name: str = "") -> dict:
    """Return Wikipedia/Wikidata facts about a company. Cached 30 days.
    Searches Wikipedia by company name first, falls back to ticker."""
    ticker = (ticker or "").upper()
    if not ticker:
        return {}
    cached = _read_cache("stock", ticker)
    if cached is not None:
        return cached

    candidates = [c for c in (name, ticker) if c]
    summary = {}
    for c in candidates:
        summary = _wiki_summary(c)
        if summary.get("extract") and summary.get("wikibase_item"):
            break

    result = {"ticker": ticker, "name": name}
    if summary:
        result["description"]       = (summary.get("extract") or "")[:1500]
        result["short_description"] = summary.get("description") or ""
        result["wikipedia_url"]     = (summary.get("content_urls", {})
                                       .get("desktop", {}).get("page", ""))
        qid = summary.get("wikibase_item") or ""
        if qid:
            result.update(_wikidata_facts(qid))
    _write_cache("stock", ticker, result)
    return result


# ── public: crypto enrichment ─────────────────────────────────────────────────

def _coin_id_for(symbol: str) -> str:
    """Map a ticker symbol (e.g. ETH) to CoinGecko's coin id (e.g. ethereum)."""
    global _coin_list_cache
    if not _coin_list_cache:
        try:
            r = requests.get(f"{COINGECKO}/coins/list", headers=HEADERS, timeout=10)
            if r.status_code == 200:
                _coin_list_cache = r.json() or []
        except Exception:
            _coin_list_cache = []
    target = symbol.lower()
    # Multiple coins can share a symbol — prefer ones with shortest id (usually canonical)
    matches = [c for c in _coin_list_cache if c.get("symbol", "").lower() == target]
    matches.sort(key=lambda c: len(c.get("id", "")))
    return matches[0]["id"] if matches else ""


def enrich_crypto(symbol: str) -> dict:
    """Return CoinGecko facts about a coin. Cached 30 days."""
    symbol = (symbol or "").upper()
    if not symbol:
        return {}
    cached = _read_cache("crypto", symbol)
    if cached is not None:
        return cached

    cid = _coin_id_for(symbol)
    result: dict = {"symbol": symbol, "coin_id": cid}
    if cid:
        try:
            r = requests.get(
                f"{COINGECKO}/coins/{cid}",
                params={"localization":"false","tickers":"false","market_data":"false",
                        "community_data":"false","developer_data":"false"},
                headers=HEADERS, timeout=12)
            if r.status_code == 200:
                c = r.json() or {}
                desc = (c.get("description") or {}).get("en", "")
                # strip HTML tags from CoinGecko's description
                desc = re.sub(r'<[^>]+>', '', desc)[:1500]
                links = c.get("links") or {}
                result.update({
                    "name":              c.get("name", ""),
                    "description":       desc,
                    "genesis_date":      c.get("genesis_date") or "",
                    "homepage":          (links.get("homepage") or [""])[0],
                    "categories":        [x for x in (c.get("categories") or []) if x][:8],
                    "country_origin":    c.get("country_origin") or "",
                    "hashing_algorithm": c.get("hashing_algorithm") or "",
                    "twitter":           links.get("twitter_screen_name") or "",
                    "subreddit":         links.get("subreddit_url") or "",
                    "github":            (links.get("repos_url") or {}).get("github", [])[:3],
                    "block_time_minutes": c.get("block_time_in_minutes") or 0,
                })
        except Exception:
            pass
    _write_cache("crypto", symbol, result)
    return result
