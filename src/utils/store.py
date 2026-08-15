"""
store.py — PER-ASSET SQLite store.

Every stock and every coin we analyze gets its OWN SQLite file at
    /data/assets/<TICKER>.db
holding 30 days of signals + decisions for that asset alone.

Why per-asset:
- Each asset is its own self-contained record we can inspect, back up, or
  ship independently.
- Reads for one asset (the EWMA smoothing path) touch only that asset's
  file — faster, regardless of how big the universe grows.
- Corruption or weirdness in one asset's file can't pollute the others.

Trade-off: cross-asset queries (signals_last_days, get_recent_ipos, db_stats,
purge_old) iterate the directory. That's a slower step than a single big DB
would be, but the user explicitly accepted longer processing time, and the
work is bounded by the number of assets in the universe (~130 today).
"""

import os, glob, json, sqlite3, threading, re
from datetime import datetime, timedelta

DB_PATH        = os.getenv("DB_PATH", "/data/makeaibilli.db")
RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", 30))
ASSETS_DIR     = os.path.join(os.path.dirname(DB_PATH) or "/data", "assets")

# Coins/tickers we never want per-asset databases for. Sourced from the crypto
# universe module so there's one place to edit. If the import fails (e.g., a
# stocks-only deploy), nothing is excluded.
try:
    from crypto.crypto_universe import EXCLUDE as _CRYPTO_EXCLUDE
except Exception:
    _CRYPTO_EXCLUDE = set()
EXCLUDED = {t.upper() for t in _CRYPTO_EXCLUDE}

# One lock per asset so two threads can't clobber the same file mid-write.
_locks_mutex = threading.Lock()
_locks: dict = {}

_TICKER_OK = re.compile(r"[^A-Za-z0-9._-]")


# ── helpers ───────────────────────────────────────────────────────────────────

def _safe(ticker: str) -> str:
    """Sanitize a ticker for use as a filename. ASCII letters/digits/._- only."""
    return _TICKER_OK.sub("_", (ticker or "").upper())[:32]


def _asset_path(ticker: str) -> str:
    return os.path.join(ASSETS_DIR, f"{_safe(ticker)}.db")


def _lock_for(ticker: str) -> threading.Lock:
    key = _safe(ticker)
    with _locks_mutex:
        lk = _locks.get(key)
        if lk is None:
            lk = _locks[key] = threading.Lock()
        return lk


def _ensure_dir():
    os.makedirs(ASSETS_DIR, exist_ok=True)


def _open(path: str) -> sqlite3.Connection:
    """Open (and lazily create) a per-asset DB with the standard schema."""
    c = sqlite3.connect(path, timeout=30)
    c.row_factory = sqlite3.Row
    c.executescript("""
      CREATE TABLE IF NOT EXISTS signals (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          ts TEXT, type TEXT, source TEXT,
          sentiment REAL, headline TEXT, payload TEXT);
      CREATE INDEX IF NOT EXISTS idx_sig_ts   ON signals(ts);
      CREATE INDEX IF NOT EXISTS idx_sig_type ON signals(type);

      CREATE TABLE IF NOT EXISTS decisions (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          ts TEXT, tier TEXT, score REAL, payload TEXT);
      CREATE INDEX IF NOT EXISTS idx_dec_tier_ts ON decisions(tier, ts);
    """)
    return c


# ── public API (signatures match the old store.py so callers don't change) ────

def cleanup_excluded() -> int:
    """Delete any per-asset DB files for tickers in the EXCLUDED set
    (BTC, LTC, USDT, BNB, USDC, SOL, ADA). Returns the number removed."""
    _ensure_dir()
    removed = 0
    for t in EXCLUDED:
        p = _asset_path(t)
        if os.path.exists(p):
            try:
                os.remove(p)
                removed += 1
            except Exception:
                pass
    return removed


def init():
    _ensure_dir()
    cleanup_excluded()


def save_signal(sig: dict):
    """Persist a signal to EVERY ticker it mentions. Each ticker writes to
    its own file. Signals routed only to excluded coins (BTC, LTC, USDT, BNB,
    USDC, SOL, ADA) are dropped — those never get per-asset databases."""
    _ensure_dir()
    tickers = sig.get("tickers") or ([sig["ticker"]] if sig.get("ticker") else [])
    tickers = [t for t in tickers if t and t.upper() not in EXCLUDED]
    if not tickers:
        return
    ts = datetime.utcnow().isoformat()
    row = (ts, sig.get("type",""), sig.get("source",""),
           float(sig.get("sentiment", 0) or 0),
           (sig.get("headline","") or "")[:300],
           json.dumps(sig)[:2000])
    for t in tickers:
        try:
            with _lock_for(t):
                c = _open(_asset_path(t))
                try:
                    c.execute(
                        "INSERT INTO signals (ts,type,source,sentiment,headline,payload) "
                        "VALUES (?,?,?,?,?,?)", row)
                    c.commit()
                finally:
                    c.close()
        except Exception:
            # one bad file shouldn't kill the scrape
            continue


def save_decision(d: dict):
    """Persist a decision to its asset's own file."""
    _ensure_dir()
    t = d.get("ticker","")
    if not t or t.upper() in EXCLUDED:
        return
    try:
        with _lock_for(t):
            c = _open(_asset_path(t))
            try:
                c.execute(
                    "INSERT INTO decisions (ts,tier,score,payload) VALUES (?,?,?,?)",
                    (datetime.utcnow().isoformat(), d.get("tier",""),
                     float(d.get("score", 0)), json.dumps(d)[:4000]))
                c.commit()
            finally:
                c.close()
    except Exception:
        pass


# Crypto used to prefix tickers with "C:" so smoothing could find them in the
# shared decisions table. With per-asset files there's no shared table, so the
# crypto decision goes into BTC.db / ETH.db / etc. directly — no prefix.
def save_crypto_decision(d: dict):
    save_decision(d)


def recent_scores_for(ticker: str, tier: str, limit: int = 8) -> list:
    """Most-recent stored scores for a ticker+tier (newest first) — used by
    the EWMA smoother. Opens only this asset's file."""
    p = _asset_path(ticker)
    if not os.path.exists(p):
        return []
    try:
        with _lock_for(ticker):
            c = _open(p)
            try:
                rows = c.execute(
                    "SELECT score FROM decisions WHERE tier=? "
                    "ORDER BY id DESC LIMIT ?", (tier, limit)).fetchall()
            finally:
                c.close()
        return [float(r["score"]) for r in rows]
    except Exception:
        return []


def signal_history_for(ticker: str, days: int = RETENTION_DAYS) -> list:
    """All recent signals for one asset, newest first. Touches one file."""
    p = _asset_path(ticker)
    if not os.path.exists(p):
        return []
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    try:
        with _lock_for(ticker):
            c = _open(p)
            try:
                rows = c.execute(
                    "SELECT * FROM signals WHERE ts>=? ORDER BY ts DESC",
                    (cutoff,)).fetchall()
            finally:
                c.close()
        out = []
        for r in rows:
            d = dict(r); d["ticker"] = _safe(ticker)
            out.append(d)
        return out
    except Exception:
        return []


def signals_last_days(days: int = RETENTION_DAYS) -> list:
    """Cross-asset: every signal in the retention window, every asset.
    Iterates every per-asset file. Bounded by universe size."""
    _ensure_dir()
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    out: list = []
    for p in sorted(glob.glob(os.path.join(ASSETS_DIR, "*.db"))):
        t = os.path.basename(p)[:-3]
        try:
            c = sqlite3.connect(p, timeout=20)
            c.row_factory = sqlite3.Row
            try:
                rows = c.execute(
                    "SELECT * FROM signals WHERE ts>=?", (cutoff,)).fetchall()
            finally:
                c.close()
            for r in rows:
                d = dict(r)
                # Re-attach the ticker (which lives in the filename, not the row),
                # and keep a tickers=[t] form so callers expecting either work.
                d["ticker"]  = t
                d["tickers"] = [t]
                # Pull anything else from the payload (e.g. catalysts, sources).
                try:
                    payload = json.loads(d.get("payload","") or "{}")
                except Exception:
                    payload = {}
                for k, v in payload.items():
                    d.setdefault(k, v)
                out.append(d)
        except Exception:
            continue
    return out


def get_recent_ipos(limit: int = 10) -> list:
    """Upcoming IPOs across all assets, newest first, deduped by ticker."""
    _ensure_dir()
    cutoff = (datetime.utcnow() - timedelta(days=15)).isoformat()
    rows = []
    for p in glob.glob(os.path.join(ASSETS_DIR, "*.db")):
        t = os.path.basename(p)[:-3]
        try:
            c = sqlite3.connect(p, timeout=10)
            c.row_factory = sqlite3.Row
            try:
                r = c.execute(
                    "SELECT * FROM signals WHERE type='ipo' AND ts>=? "
                    "ORDER BY ts DESC LIMIT 1", (cutoff,)).fetchone()
            finally:
                c.close()
            if r:
                try: payload = json.loads(r["payload"] or "{}")
                except Exception: payload = {}
                # Carry the full enriched payload so the dashboard has every
                # field the scraper captured (industry, market cap, etc.).
                payload.setdefault("ticker", t)
                payload.setdefault("ts", r["ts"])
                payload.setdefault("headline", r["headline"] or "")
                rows.append(payload)
        except Exception:
            continue
    rows.sort(key=lambda x: x["ts"], reverse=True)
    return rows[:limit]


def get_recent_new_coins(limit: int = 15) -> list:
    """Recently detected new Coinbase listings across all per-asset DBs.
    Each row carries the structured product fields the scraper captured."""
    _ensure_dir()
    cutoff = (datetime.utcnow() - timedelta(days=RETENTION_DAYS)).isoformat()
    rows = []
    for p in glob.glob(os.path.join(ASSETS_DIR, "*.db")):
        t = os.path.basename(p)[:-3]
        try:
            c = sqlite3.connect(p, timeout=10)
            c.row_factory = sqlite3.Row
            try:
                r = c.execute(
                    "SELECT * FROM signals WHERE type='crypto_new_listing' AND ts>=? "
                    "ORDER BY ts DESC LIMIT 1", (cutoff,)).fetchone()
            finally:
                c.close()
            if r:
                try: payload = json.loads(r["payload"] or "{}")
                except Exception: payload = {}
                payload.setdefault("ticker", t)
                payload.setdefault("ts", r["ts"])
                payload.setdefault("headline", r["headline"] or "")
                rows.append(payload)
        except Exception:
            continue
    rows.sort(key=lambda x: x.get("ts",""), reverse=True)
    return rows[:limit]


def purge_old():
    """Drop rows older than the retention window in every per-asset file,
    then VACUUM each on a fresh autocommit connection (SQLite forbids
    VACUUM inside a transaction)."""
    _ensure_dir()
    cutoff = (datetime.utcnow() - timedelta(days=RETENTION_DAYS)).isoformat()
    for p in glob.glob(os.path.join(ASSETS_DIR, "*.db")):
        t = os.path.basename(p)[:-3]
        try:
            with _lock_for(t):
                c = sqlite3.connect(p, timeout=20)
                try:
                    c.execute("DELETE FROM signals  WHERE ts<?", (cutoff,))
                    c.execute("DELETE FROM decisions WHERE ts<?", (cutoff,))
                    c.commit()
                finally:
                    c.close()
                try:
                    v = sqlite3.connect(p, isolation_level=None)
                    v.execute("VACUUM"); v.close()
                except Exception:
                    pass
        except Exception:
            continue


def db_stats() -> dict:
    """Aggregate counts across every per-asset file, plus the asset count."""
    _ensure_dir()
    sig = dec = 0
    size_b = 0
    files = glob.glob(os.path.join(ASSETS_DIR, "*.db"))
    for p in files:
        try:
            size_b += os.path.getsize(p)
            c = sqlite3.connect(p, timeout=5)
            try:
                sig += c.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
                dec += c.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
            finally:
                c.close()
        except Exception:
            continue
    return {
        "signals":   sig,
        "decisions": dec,
        "assets":    len(files),
        "size_mb":   round(size_b / 1e6, 1),
    }


def list_assets() -> list:
    """All asset symbols currently tracked (whatever has a DB file)."""
    _ensure_dir()
    return sorted(os.path.basename(p)[:-3] for p in
                  glob.glob(os.path.join(ASSETS_DIR, "*.db")))
