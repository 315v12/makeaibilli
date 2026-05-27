import json, os, redis
from datetime import datetime
from typing import Optional

_client: Optional[redis.Redis] = None

def get_client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.Redis(host=os.getenv("REDIS_HOST","localhost"),
                              port=int(os.getenv("REDIS_PORT",6379)), decode_responses=True)
    return _client

def push_alert(alert: dict):
    r = get_client()
    alert["timestamp"] = datetime.now().isoformat()
    r.lpush("alerts:live", json.dumps(alert))
    r.ltrim("alerts:live", 0, 399)   # hold all 90 (was 49 — that silently dropped short-term)

def get_alerts() -> list:
    return [json.loads(x) for x in get_client().lrange("alerts:live", 0, -1)]

def clear_alerts():
    get_client().delete("alerts:live")

def set_scraper_status(name: str, status: str, detail: str = ""):
    get_client().hset("scrapers:status", name, json.dumps({
        "status": status, "detail": detail,
        "updated": datetime.now().strftime("%I:%M %p ET")}))

def get_scraper_statuses() -> dict:
    return {k: json.loads(v) for k, v in get_client().hgetall("scrapers:status").items()}

def push_signal(signal: dict):
    r = get_client()
    queue = "crypto:signals:queue" if signal.get("asset") == "crypto" else "signals:queue"
    r.lpush(queue, json.dumps(signal))
    r.ltrim(queue, 0, 1499)
    # persist to the 15-day store
    try:
        from utils.store import save_signal
        save_signal(signal)
    except Exception:
        pass

def pop_signals(count: int = 50) -> list:
    r = get_client()
    pipe = r.pipeline()
    for _ in range(count):
        pipe.rpop("signals:queue")
    return [json.loads(x) for x in pipe.execute() if x is not None]

def get_watchlist() -> list:
    return get_client().lrange("watchlist", 0, -1)

def add_to_watchlist(ticker: str):
    r = get_client()
    if ticker.upper() not in get_watchlist():
        r.lpush("watchlist", ticker.upper())

def remove_from_watchlist(ticker: str):
    get_client().lrem("watchlist", 0, ticker.upper())

def open_position(pos: dict):
    get_client().hset("positions", pos["ticker"], json.dumps(pos))

def close_position(ticker: str):
    get_client().hdel("positions", ticker)

def get_positions() -> list:
    return [json.loads(v) for v in get_client().hgetall("positions").values()]

def set_market_stats(stats: dict):
    get_client().set("market:stats", json.dumps(stats), ex=300)

def get_market_stats() -> dict:
    raw = get_client().get("market:stats")
    return json.loads(raw) if raw else {}


def expire_stale_alerts():
    """Remove alerts past their expiry. Called every cycle so the board stays live."""
    from datetime import datetime
    r = get_client()
    raw = r.lrange("alerts:live", 0, -1)
    kept = []
    for x in raw:
        a = json.loads(x)
        exp = a.get("expiry")
        if exp:
            try:
                if datetime.utcnow() <= datetime.fromisoformat(exp):
                    kept.append(x)
            except Exception:
                kept.append(x)
        else:
            kept.append(x)
    r.delete("alerts:live")
    if kept:
        r.rpush("alerts:live", *kept)



# ── live activity log (debug feed shown in the dashboard) ─────────────────────
import logging as _logging

def log_event(msg: str, level: str = "INFO"):
    """Push one line to the live activity feed."""
    try:
        from datetime import datetime
        entry = json.dumps({
            "ts": datetime.now().strftime("%H:%M:%S"),
            "level": level,
            "msg": str(msg)[:300],
        })
        r = get_client()
        r.lpush("debug:log", entry)
        r.ltrim("debug:log", 0, 299)
    except Exception:
        pass

def get_log() -> list:
    """Newest first."""
    try:
        return [json.loads(x) for x in get_client().lrange("debug:log", 0, -1)]
    except Exception:
        return []

class RedisLogHandler(_logging.Handler):
    """Routes every log line into the dashboard's live activity feed."""
    def emit(self, record):
        try:
            log_event(record.getMessage(), record.levelname)
        except Exception:
            pass


# ── crypto queue + alerts (separate from stocks) ──────────────────────────────
def pop_crypto_signals(n: int = 800) -> list:
    r = get_client(); out = []
    for _ in range(n):
        v = r.rpop("crypto:signals:queue")
        if v is None: break
        try: out.append(json.loads(v))
        except Exception: pass
    return out

def push_crypto_alert(alert: dict):
    r = get_client()
    r.lpush("crypto:alerts:live", json.dumps(alert))
    r.ltrim("crypto:alerts:live", 0, 399)

def get_crypto_alerts() -> list:
    return [json.loads(x) for x in get_client().lrange("crypto:alerts:live", 0, -1)]

def clear_crypto_alerts():
    get_client().delete("crypto:alerts:live")


def set_crypto_emerging(items: list):
    get_client().set("crypto:emerging", json.dumps(items))

def get_crypto_emerging() -> list:
    v = get_client().get("crypto:emerging")
    try: return json.loads(v) if v else []
    except Exception: return []
