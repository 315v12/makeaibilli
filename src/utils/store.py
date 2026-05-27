"""
store.py — simple SQLite store. No setup, no server. The file lives on disk
and the app creates it on first run. Holds 15 days of scrapes + decisions,
auto-purges anything older, and every 15-min scan re-reads the window.
"""

import os, json, sqlite3, threading
from datetime import datetime, timedelta

DB_PATH = os.getenv("DB_PATH", "/data/makeaibilli.db")
RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", 15))
_lock = threading.Lock()


def _conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    c = sqlite3.connect(DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    return c


def init():
    with _lock, _conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT, ticker TEXT, type TEXT, source TEXT,
            sentiment REAL, headline TEXT, payload TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_signals_ts ON signals(ts);
        CREATE INDEX IF NOT EXISTS idx_signals_ticker ON signals(ticker);

        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT, ticker TEXT, tier TEXT, score REAL, payload TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_decisions_ts ON decisions(ts);
        """)


def save_signal(sig: dict):
    with _lock, _conn() as c:
        for ticker in (sig.get("tickers") or [None]):
            c.execute(
                "INSERT INTO signals (ts,ticker,type,source,sentiment,headline,payload) "
                "VALUES (?,?,?,?,?,?,?)",
                (datetime.utcnow().isoformat(), (ticker or "").upper(),
                 sig.get("type",""), sig.get("source",""),
                 float(sig.get("sentiment",0) or 0), sig.get("headline","")[:300],
                 json.dumps(sig)[:2000]))


def signals_last_days(days: int = RETENTION_DAYS) -> list[dict]:
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    with _lock, _conn() as c:
        rows = c.execute("SELECT * FROM signals WHERE ts >= ?", (cutoff,)).fetchall()
    return [dict(r) for r in rows]


def signal_history_for(ticker: str, days: int = RETENTION_DAYS) -> list[dict]:
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    with _lock, _conn() as c:
        rows = c.execute(
            "SELECT * FROM signals WHERE ticker=? AND ts>=? ORDER BY ts DESC",
            (ticker.upper(), cutoff)).fetchall()
    return [dict(r) for r in rows]


def save_decision(d: dict):
    with _lock, _conn() as c:
        c.execute("INSERT INTO decisions (ts,ticker,tier,score,payload) VALUES (?,?,?,?,?)",
                  (datetime.utcnow().isoformat(), d.get("ticker",""),
                   d.get("tier",""), float(d.get("score",0)), json.dumps(d)[:4000]))


def purge_old():
    """Delete anything past the retention window."""
    cutoff = (datetime.utcnow() - timedelta(days=RETENTION_DAYS)).isoformat()
    with _lock, _conn() as c:
        c.execute("DELETE FROM signals  WHERE ts < ?", (cutoff,))
        c.execute("DELETE FROM decisions WHERE ts < ?", (cutoff,))
        c.execute("VACUUM")


def db_stats() -> dict:
    with _lock, _conn() as c:
        s = c.execute("SELECT COUNT(*) n FROM signals").fetchone()["n"]
        d = c.execute("SELECT COUNT(*) n FROM decisions").fetchone()["n"]
    size_mb = round(os.path.getsize(DB_PATH)/1e6, 1) if os.path.exists(DB_PATH) else 0
    return {"signals": s, "decisions": d, "size_mb": size_mb}


def recent_scores_for(ticker: str, tier: str, limit: int = 8) -> list[float]:
    """Most-recent stored scores for a ticker+tier (newest first) — for EWMA smoothing."""
    with _lock, _conn() as c:
        rows = c.execute(
            "SELECT score FROM decisions WHERE ticker=? AND tier=? ORDER BY id DESC LIMIT ?",
            (ticker.upper(), tier, limit)).fetchall()
    return [float(r["score"]) for r in rows]


def save_crypto_decision(d: dict):
    """Crypto decisions share the decisions table, keyed 'C:SYM' so smoothing reuses recent_scores_for."""
    with _lock, _conn() as c:
        c.execute("INSERT INTO decisions (ts,ticker,tier,score,payload) VALUES (?,?,?,?,?)",
                  (datetime.utcnow().isoformat(), "C:"+d.get("ticker",""),
                   d.get("tier",""), float(d.get("score",0)), json.dumps(d)[:4000]))


def get_recent_ipos(limit: int = 10) -> list[dict]:
    """Upcoming IPOs captured in the last 15 days, newest first, deduped by ticker."""
    cutoff = (datetime.utcnow() - timedelta(days=15)).isoformat()
    with _lock, _conn() as c:
        rows = c.execute("SELECT * FROM signals WHERE type='ipo' AND ts>=? ORDER BY ts DESC",
                         (cutoff,)).fetchall()
    seen, out = set(), []
    for r in rows:
        t = r["ticker"]
        if not t or t in seen: continue
        seen.add(t)
        try: payload = json.loads(r["payload"])
        except Exception: payload = {}
        out.append({"ticker": t, "headline": r["headline"],
                    "company_name": payload.get("company_name",""),
                    "ipo_date": payload.get("ipo_date","")})
        if len(out) >= limit: break
    return out
