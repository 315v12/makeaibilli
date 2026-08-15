"""crypto_universe.py — coins we analyze (Coinbase USD pairs).
EXCLUDED per request: BTC, LTC, USDT, BNB, USDC, SOL, ADA.

The list is the curated baseline UNIONED with any new coin the
new_coin_scraper has detected on Coinbase — so freshly listed coins
automatically enter the analysis universe."""

import os, json

EXCLUDE = {"BTC","LTC","USDT","BNB","USDC","SOL","ADA"}

# Liquid Coinbase USD pairs (ex-excluded). Stablecoins/wrapped excluded too.
_COINS = [
    "ETH","XRP","DOGE","AVAX","LINK","DOT","MATIC","ATOM","UNI","SHIB",
    "XLM","ALGO","FIL","ICP","ETC","NEAR","APE","AAVE","GRT","SAND",
    "MANA","CRV","COMP","MKR","SNX","CHZ","ENJ","BAT","ZRX","DASH",
    "EOS","XTZ","KSM","FET","RNDR","INJ","SUI","APT","ARB","OP",
    "LDO","IMX","HBAR","QNT","AXS","GALA","FLOW","EGLD","THETA","RUNE",
]

_KNOWN_PRODUCTS = "/data/known_products.json"


def _dynamic_coins() -> list:
    """Read the Coinbase products snapshot maintained by new_coin_scraper
    and pull out the base currencies. Empty if the snapshot doesn't exist yet."""
    if not os.path.exists(_KNOWN_PRODUCTS):
        return []
    try:
        pairs = json.load(open(_KNOWN_PRODUCTS))
    except Exception:
        return []
    out = []
    for pid in pairs:
        if pid.endswith("-USD"):
            sym = pid.replace("-USD", "").upper()
            if sym and sym not in EXCLUDE and 1 <= len(sym) <= 8:
                out.append(sym)
    return out


def _all_symbols() -> list:
    seen = set(); out = []
    for s in _COINS + _dynamic_coins():
        if s not in EXCLUDE and s not in seen:
            seen.add(s); out.append(s)
    return out


def crypto_pairs() -> list[str]:
    return [f"{c}-USD" for c in _all_symbols()]


def crypto_symbols() -> list[str]:
    return _all_symbols()

