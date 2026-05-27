"""
universe.py — the full pool we analyze, organized by category.
The system scores ALL of these, compares each against its category peers
AND the whole field, then surfaces only the top 30. Penny/illiquid junk
is filtered out at runtime (price > $5, real volume).
"""

# Tech-focused, but broad enough to make the competition meaningful.
UNIVERSE = {
    "Semiconductors": [
        "NVDA","AMD","INTC","QCOM","MU","AVGO","MRVL","TXN","AMAT","LRCX",
        "KLAC","ASML","TSM","ARM","ON","MCHP","NXPI","ADI","SWKS","QRVO",
    ],
    "Software": [
        "MSFT","CRM","ORCL","ADBE","NOW","SNOW","CRWD","PANW","ZS","DDOG",
        "NET","PLTR","TEAM","WDAY","INTU","FTNT","MDB","HUBS","PATH","S",
    ],
    "Internet & Media": [
        "GOOGL","META","AMZN","NFLX","DIS","SPOT","RBLX","SNAP","PINS",
        "ABNB","UBER","DASH","BKNG","TTD","ROKU",
    ],
    "Hardware & Devices": [
        "AAPL","DELL","HPQ","ANET","SMCI","WDC","STX","HPE","JBL","VRT",
    ],
    "Fintech": [
        "HOOD","SOFI","PYPL","AFRM","SQ","BILL","NU","UPST","TOST","FI",
    ],
    "EV & Auto Tech": [
        "TSLA","RIVN","LCID","NIO","XPEV","LI",
    ],
}

# Flat, de-duplicated list of every ticker we pull data for
def all_tickers() -> list[str]:
    seen, out = set(), []
    for names in UNIVERSE.values():
        for t in names:
            if t not in seen:
                seen.add(t); out.append(t)
    return out

# Reverse map: ticker -> its category
def category_of(ticker: str) -> str:
    for cat, names in UNIVERSE.items():
        if ticker in names:
            return cat
    return "Other"

# Filter thresholds — drop "useless" stocks from the analysis
MIN_PRICE = 5.0          # no penny stocks
MIN_AVG_VOLUME = 1_000_000   # must be liquid enough to actually trade
