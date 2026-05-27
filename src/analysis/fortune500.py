"""
fortune500.py — large-cap universe (~500 names). Pulls the S&P 500 list
(symbol + company name) dynamically and caches it; registers names so the
plan shows full company names. Falls back to a static list if offline.
"""
import io, requests
import pandas as pd
from analysis.names import register_name

_CACHE = None
_FALLBACK = [
 "AAPL","MSFT","NVDA","GOOGL","AMZN","META","AVGO","ORCL","CRM","ADBE","AMD","INTC",
 "CSCO","IBM","QCOM","TXN","NOW","INTU","AMAT","MU","UNH","JNJ","LLY","ABBV","MRK",
 "PFE","TMO","ABT","DHR","BMY","JPM","BAC","WFC","GS","MS","BLK","C","SCHW","AXP",
 "SPGI","V","MA","WMT","COST","HD","LOW","TGT","NKE","MCD","SBUX","PG","KO","PEP",
 "PM","XOM","CVX","CAT","BA","GE","HON","UPS","RTX","LMT","DE","UNP","DIS","NFLX",
 "CMCSA","T","VZ","TMUS","TSLA","F","GM",
]

def fortune_tickers() -> list[str]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    try:
        resp = requests.get("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
                            headers={"User-Agent":"makeaibilli/2.0"}, timeout=12)
        resp.raise_for_status()
        tables = pd.read_html(io.StringIO(resp.text))
        df = tables[0]
        syms = [str(s).replace(".", "-") for s in df["Symbol"].tolist()]
        for sym, name in zip(syms, df["Security"].tolist()):
            register_name(sym, str(name))
        _CACHE = syms
    except Exception:
        _CACHE = _FALLBACK
    return _CACHE
