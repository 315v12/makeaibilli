# makeaibilli v3.0 🗽 + 🪙

Web-intel-first market engine for STOCKS and CRYPTO.

## Stocks (🗽 main page)
Scrapes news/Reddit/StockTwits/SEC/Congress/influencers/earnings/IPO + Fortune 500
by company name. Ranks 90 (30 short / 30 long / 30 extra-long) every 15 min.
Data-derived buy/sell triggers from each stock's own chart. EWMA-smoothed ranks.

## Crypto (🪙 separate page — click the spinning gold emblem)
- Coinbase public REST API for candles (no key, no FIX). WebSocket is the
  upgrade path for live ticks; REST polling fits the scan model.
- Multi-source intel: crypto RSS (CoinDesk, Cointelegraph, Decrypt, ...),
  Reddit crypto subs, and DuckDuckGo web search per coin.
- Same data-derived trigger logic as stocks, from each coin's own candles.
- Excludes BTC, LTC, USDT, BNB, USDC, SOL, ADA from picks.
- 24/7 — re-ranks every scan.

Navigation: the spinning gold prestige-style emblem (top of the stocks page)
links to the crypto page; on the crypto page it sits where the 🗽 is and links back.

## Run (Podman homelab)
    tar -xzf makeaibilli_v3.0.tar.gz && cd makeaibilli
    cp .env.template .env        # add Finnhub key (stocks). Crypto needs no key.
    podman-compose build --no-cache
    podman-compose up -d
    # http://<ip>:8501   (crypto: the spinning emblem, or ?page=crypto)

## DB
Single SQLite file in ./data, auto-created, 15-day retention. Stocks + crypto
decisions share it (crypto rows keyed "C:SYM"). No server to manage.

## Disclaimer
Informational only. Not financial advice. No system predicts the market.
