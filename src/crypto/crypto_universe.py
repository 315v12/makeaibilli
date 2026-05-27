"""crypto_universe.py — coins we analyze (Coinbase USD pairs).
EXCLUDED per request: BTC, LTC, USDT, BNB, USDC, SOL, ADA."""

EXCLUDE = {"BTC","LTC","USDT","BNB","USDC","SOL","ADA"}

# Liquid Coinbase USD pairs (ex-excluded). Stablecoins/wrapped excluded too.
_COINS = [
    "ETH","XRP","DOGE","AVAX","LINK","DOT","MATIC","ATOM","UNI","SHIB",
    "XLM","ALGO","FIL","ICP","ETC","NEAR","APE","AAVE","GRT","SAND",
    "MANA","CRV","COMP","MKR","SNX","CHZ","ENJ","BAT","ZRX","DASH",
    "EOS","XTZ","KSM","FET","RNDR","INJ","SUI","APT","ARB","OP",
    "LDO","IMX","HBAR","QNT","AXS","GALA","FLOW","EGLD","THETA","RUNE",
]

def crypto_pairs() -> list[str]:
    return [f"{c}-USD" for c in _COINS if c not in EXCLUDE]

def crypto_symbols() -> list[str]:
    return [c for c in _COINS if c not in EXCLUDE]
