"""names.py — ticker -> full company name. Static map for known names;
falls back to any name captured from IPO/news signals, else the ticker."""

NAMES = {
 "AAPL":"Apple Inc.","MSFT":"Microsoft Corp.","NVDA":"NVIDIA Corp.","GOOGL":"Alphabet Inc.",
 "AMZN":"Amazon.com Inc.","META":"Meta Platforms Inc.","AVGO":"Broadcom Inc.","ORCL":"Oracle Corp.",
 "CRM":"Salesforce Inc.","ADBE":"Adobe Inc.","AMD":"Advanced Micro Devices","INTC":"Intel Corp.",
 "CSCO":"Cisco Systems","IBM":"IBM Corp.","QCOM":"Qualcomm Inc.","TXN":"Texas Instruments",
 "NOW":"ServiceNow Inc.","INTU":"Intuit Inc.","AMAT":"Applied Materials","MU":"Micron Technology",
 "UNH":"UnitedHealth Group","JNJ":"Johnson & Johnson","LLY":"Eli Lilly & Co.","ABBV":"AbbVie Inc.",
 "MRK":"Merck & Co.","PFE":"Pfizer Inc.","TMO":"Thermo Fisher","ABT":"Abbott Labs","DHR":"Danaher Corp.",
 "BMY":"Bristol-Myers Squibb","JPM":"JPMorgan Chase","BAC":"Bank of America","WFC":"Wells Fargo",
 "GS":"Goldman Sachs","MS":"Morgan Stanley","BLK":"BlackRock Inc.","C":"Citigroup Inc.",
 "SCHW":"Charles Schwab","AXP":"American Express","SPGI":"S&P Global","V":"Visa Inc.","MA":"Mastercard",
 "WMT":"Walmart Inc.","COST":"Costco Wholesale","HD":"Home Depot","LOW":"Lowe's","TGT":"Target Corp.",
 "NKE":"Nike Inc.","MCD":"McDonald's Corp.","SBUX":"Starbucks Corp.","PG":"Procter & Gamble",
 "KO":"Coca-Cola Co.","PEP":"PepsiCo Inc.","PM":"Philip Morris","XOM":"Exxon Mobil","CVX":"Chevron Corp.",
 "CAT":"Caterpillar Inc.","BA":"Boeing Co.","GE":"GE Aerospace","HON":"Honeywell","UPS":"UPS Inc.",
 "RTX":"RTX Corp.","LMT":"Lockheed Martin","DE":"Deere & Co.","UNP":"Union Pacific","DIS":"Walt Disney Co.",
 "NFLX":"Netflix Inc.","CMCSA":"Comcast Corp.","T":"AT&T Inc.","VZ":"Verizon","TMUS":"T-Mobile US",
 "TSLA":"Tesla Inc.","F":"Ford Motor Co.","GM":"General Motors","PLTR":"Palantir Technologies",
 "SMCI":"Super Micro Computer","MRVL":"Marvell Technology","ARM":"Arm Holdings","DELL":"Dell Technologies",
 "SNOW":"Snowflake Inc.","CRWD":"CrowdStrike","PANW":"Palo Alto Networks","NET":"Cloudflare Inc.",
 "DDOG":"Datadog Inc.","ANET":"Arista Networks","ASML":"ASML Holding","TSM":"Taiwan Semi",
 "NFLX":"Netflix Inc.","UBER":"Uber Technologies","ABNB":"Airbnb Inc.","SHOP":"Shopify Inc.",
 "SOFI":"SoFi Technologies","HOOD":"Robinhood Markets","RIVN":"Rivian Automotive","LCID":"Lucid Group",
}
_dynamic = {}

def register_name(ticker: str, name: str):
    if ticker and name:
        _dynamic[ticker.upper()] = name

def name_of(ticker: str) -> str:
    t = (ticker or "").upper()
    return NAMES.get(t) or _dynamic.get(t) or t

# Crypto-native tickers we will NOT recommend (but their news can still feed signals)
CRYPTO_BLOCK = {"COIN","MSTR","MARA","RIOT","HOOD","CLSK","HUT","BITF","BTBT","WULF",
                "CIFR","IREN","BTC","ETH","GBTC","BITO","COINBASE","SQ","BKKT","CAN"}
