"""main.py — makeaibilli v2 orchestrator.
Two clocks:
  • LIGHT scan  every 15 min  — scrape fast sources + re-rank the 90 list
  • HEAVY sweep every 60 min  — add Fortune 500 + IPO calendar, deep reprocess
Scrapes/processes 24/7 regardless of market hours. 30-day SQLite memory.
"""
import os, sys, time, logging, schedule, socket
socket.setdefaulttimeout(20)  # no network call hangs forever
from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, os.path.dirname(__file__))

from utils.state import set_scraper_status, expire_stale_alerts, log_event, RedisLogHandler
from utils.store import init as db_init, purge_old, db_stats
from analysis.scorer import run_scoring_cycle

import scrapers.news_scraper       as news
import scrapers.reddit_scraper     as reddit
import scrapers.stocktwits_scraper as stocktwits
import scrapers.sec_scraper        as sec
import scrapers.congress_scraper   as congress
import scrapers.finviz_scraper     as finviz
import scrapers.influencer_scraper as influencer
import scrapers.earnings_scraper   as earnings
import scrapers.ipo_scraper        as ipo
import scrapers.company_news_scraper as company_news
import scrapers.new_coin_scraper    as new_coins
import crypto.crypto_scrapers as crypto_scrapers
from crypto.crypto_scorer import run_crypto_cycle

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("makeaibilli")
_root = logging.getLogger()
if not any(isinstance(h, RedisLogHandler) for h in _root.handlers):
    h = RedisLogHandler(); h.setLevel(logging.INFO); _root.addHandler(h)

# ── Cadence (90-min decision cycle) ───────────────────────────────────────────
# SCRAPE_MIN : light scraping (gather data only — does NOT change the lists)
# HARD_MIN   : hard scrape (Fortune 500 + IPO + deep sources)
# DECISION_MIN: how often the ranked lists are actually recalculated (every 90 min)
SCRAPE_MIN   = int(os.getenv("SCAN_INTERVAL_MINUTES", 30))
HARD_MIN     = int(os.getenv("HEAVY_SWEEP_MINUTES", 60))
DECISION_MIN = int(os.getenv("DECISION_INTERVAL_MINUTES", 90))

LIGHT_SOURCES = [("news",news),("reddit",reddit),("stocktwits",stocktwits),
                 ("finviz",finviz),("influencer",influencer)]
HEAVY_SOURCES = [("sec",sec),("congress",congress),("earnings",earnings),("ipo",ipo),
                 ("new_coins",new_coins),("fortune500_news",company_news)]

def _scrape(sources):
    for name_, mod in sources:
        try:
            log.info(f"  running {name_}...")
            log.info(f"  {name_}: {mod.run()}")
        except Exception as e:
            log.warning(f"  {name_} error: {e}")

def light_scrape():
    """Gather fast sources + crypto into the 30-day store. Does NOT change the lists."""
    log.info(f"── LIGHT scrape ({SCRAPE_MIN}m): gathering data (no new decisions) ──")
    _scrape(LIGHT_SOURCES)
    try:
        log.info("  running crypto web/social...")
        log.info(f"  crypto signals: {crypto_scrapers.run()}")
    except Exception as e:
        log.warning(f"  crypto scrape error: {e}")

def hard_scrape():
    """Deep gather: Fortune 500 by name + IPO calendar + filings. Still no new decisions."""
    log.info(f"══ HARD scrape ({HARD_MIN}m): Fortune 500 + IPO + filings ══")
    _scrape(LIGHT_SOURCES + HEAVY_SOURCES)
    try:
        purge_old()
    except Exception as e:
        log.warning(f"  purge_old error (ignoring): {e}")

def make_decisions():
    """The ONLY thing that changes the ranked lists. Runs every 90 min."""
    log.info(f"★ DECISIONS ({DECISION_MIN}m): recalculating the 90-list + crypto ★")
    try:
        expire_stale_alerts()
    except Exception as e:
        log.warning(f"  expire_stale_alerts error: {e}")
    try:
        r = run_scoring_cycle(include_fortune=True)
        log.info(f"  90-list: {r['short']} short · {r['long']} long · {r['xlong']} hold")
    except Exception as e:
        log.error(f"  STOCK decision error: {e}", exc_info=True)
    try:
        cr = run_crypto_cycle()
        log.info(f"  crypto-list: {cr['short']} short · {cr['long']} long · {cr['xlong']} hold")
    except Exception as e:
        log.error(f"  CRYPTO decision error: {e}", exc_info=True)
    try:
        st = db_stats()
        log.info(f"  done · DB: {st['signals']} signals, {st['size_mb']}MB (30-day window)")
    except Exception: pass

def main():
    log.info("makeaibilli v4.0 starting (stocks + crypto)")
    try:
        db_init()
        log.info("SQLite store ready (30-day memory)")
    except Exception as e:
        log.error(f"db_init error: {e}", exc_info=True)
    # Boot: hard scrape, then make the first decisions so the board isn't empty,
    # then settle into the 90-minute decision cycle. Wrap each so one failure
    # cannot prevent the others — no more crash loops.
    try: hard_scrape()
    except Exception as e: log.error(f"boot hard_scrape error: {e}", exc_info=True)
    try: make_decisions()
    except Exception as e: log.error(f"boot make_decisions error: {e}", exc_info=True)
    log.info(f"Boot complete. Cycle: scrape every {SCRAPE_MIN}m, hard every {HARD_MIN}m, "
             f"DECISIONS every {DECISION_MIN}m · dashboard :8501")
    schedule.every(SCRAPE_MIN).minutes.do(light_scrape)
    schedule.every(HARD_MIN).minutes.do(hard_scrape)
    schedule.every(DECISION_MIN).minutes.do(make_decisions)
    schedule.every(6).hours.do(purge_old)
    # Pre-market passes so fresh forward projections exist BEFORE the 9:30 open.
    # Container TZ is America/New_York (set in docker-compose), so these fire in ET.
    try:
        schedule.every().day.at("08:40").do(make_decisions)   # pre-market
        schedule.every().day.at("09:25").do(make_decisions)   # just before the open
    except Exception as e:
        log.warning(f"  could not schedule pre-market runs: {e}")
    while True:
        schedule.run_pending(); time.sleep(20)

if __name__ == "__main__":
    main()
