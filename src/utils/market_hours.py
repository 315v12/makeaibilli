from datetime import datetime, time
import pytz

ET = pytz.timezone("America/New_York")

def now_et():
    return datetime.now(ET)

def is_market_open():
    n = now_et()
    return n.weekday() < 5 and time(9,30) <= n.time() <= time(16,0)

def is_premarket():
    n = now_et()
    return n.weekday() < 5 and time(8,0) <= n.time() < time(9,30)

def is_afterhours():
    n = now_et()
    return n.weekday() < 5 and time(16,0) < n.time() <= time(17,0)

def should_scan():
    return is_market_open() or is_premarket() or is_afterhours()

def market_status_label():
    if is_market_open(): return "OPEN"
    if is_premarket(): return "PRE-MARKET"
    if is_afterhours(): return "AFTER-HOURS"
    return "CLOSED"
