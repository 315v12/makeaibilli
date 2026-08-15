# makeaibilli 🗽

Web-intelligence-first market engine for **stocks and crypto**. It scrapes the
open web, processes what it finds against real market data, and produces ranked
shortlists of what to look at — with data-derived buy/sell triggers pulled from
each asset's own chart. Runs on a homelab via Podman. Not financial advice.

---

## What it does, in one breath

Gather information from across the web → process it → re-process it against the
market's real performance → produce a ranked list of opportunities, refreshed on
a fixed cycle. Stocks and crypto each get their own page.

---

## The scan cycle (90 minutes total)

The engine deliberately separates **gathering data** from **making decisions**,
so your ranked lists stay stable instead of churning every few minutes.

| Job | Every | What it does |
|-----|-------|--------------|
| **Light scrape** | 30 min | Pulls fast sources (news, Reddit, StockTwits, Finviz, influencers) + crypto web/social into the database. Does **not** change the lists. |
| **Hard scrape** | 60 min | Deep gather: Fortune 500 by company name, IPO calendar, SEC filings, congressional trades. Still doesn't change the lists. |
| **Decisions** | 90 min | The only step that recalculates the ranked lists. Reads everything gathered, scores it, ranks it. |

On boot it runs one hard scrape + one decision pass so the board isn't empty,
then settles into the cycle above.

---

## How a decision is made (the pipeline)

1. **Scrape the web.** Every source pushes "signals" (a headline, a sentiment, a
   ticker/coin) into a 15-day SQLite memory.
2. **First pass — intel.** Signals are grouped per ticker/coin. Each gets an
   "intel score": how strongly the world's news, filings, whale moves, and social
   chatter point at it (earnings and IPOs weigh heaviest).
3. **Second pass — market validation.** Each candidate's real market data is
   pulled (prices, momentum, trend, volume). Junk/illiquid names are filtered out.
   Stocks use Yahoo data; crypto uses Coinbase candles.
4. **Score per horizon.** Every name gets three scores — short-term (0–72h),
   long-term (4–30d), and Hold (1–18mo) — blending intel with momentum/trend.
5. **Smooth for stability.** Each score is blended (EWMA) with that name's recent
   history from the database, so a #1 stays near the top unless something real
   changes — no whipsawing.
6. **Rank.** Top names per horizon are published to the dashboard.

---

## Buy/sell triggers — where the numbers come from

Triggers are **derived from each asset's own price structure**, never generic
market timing. For every pick the engine computes, from that asset's own chart:

- Support levels (20-day low, 50/200-day moving averages, 52-week low)
- Resistance levels (20-day high, 52-week high)
- An ATR-scaled measured target (sized to the asset's own volatility)
- A structure-based stop
- Plus any real scheduled catalyst (earnings/IPO date)

So you get 2–5 specific buy triggers and 2–5 sell triggers per asset, each tied
to a concrete price level or date — nothing repeats across names.

---

## The pages

- **Stocks (🗽):** Short-term · Long-term · Hold · IPOs (companies going public
  within ~5 days, max 10).
- **Crypto:** Short-term · Long-term · Hold · Emerging (coins with the strongest
  fresh momentum + volume, max 10). Coinbase data, 24/7. Excludes BTC, LTC, USDT,
  BNB, USDC, SOL, ADA from picks (their news still informs other assets).
- **Settings (⚙️):** live Debug feed (everything the engine is doing) + scraper
  Status and database size.

Click any pick → **View** opens an interactive chart and the full trigger list.
The side nav (gold buttons on the right edge) jumps between Stocks, Crypto, and
Settings. Drop a `logo` image in `data/` for the stocks emblem and a `prestige`
image for the crypto emblem.

---

## Data sources

News RSS, Reddit (public JSON), StockTwits, Finviz, SEC filings, congressional
trades, market-mover mentions, Finnhub earnings + IPO calendars, Fortune/S&P 500
company-name news, and for crypto: Coinbase REST candles, crypto RSS, Reddit
crypto subs, and DuckDuckGo web search.

---

## Architecture

Three containers (Podman, host-networked): **redis** (in-memory scratchpad),
**scraper** (the engine), **dashboard** (Streamlit on :8501). One SQLite file in
`data/` holds 15 days of signals + decisions and auto-purges older data — no
database server to manage.

---

## Run it

```bash
cp .env.template .env        # add your free Finnhub API key (stocks). Crypto needs none.
./build.sh                   # builds with a progress bar, then starts everything
# dashboard: http://<your-ip>:8501
```

Tunable in `.env`: `SCAN_INTERVAL_MINUTES` (30), `HEAVY_SWEEP_MINUTES` (60),
`DECISION_INTERVAL_MINUTES` (90), `RETENTION_DAYS` (15), `MAX_CANDIDATES` (150).

---

## Disclaimer

Informational tool only. **Not financial advice.** No software can predict the
market; day trading carries real risk of loss. Do your own research.

## Decision engine — multi-factor composite scoring (v3.1)

Ranking is driven by a six-factor composite, each factor z-scored across the
universe so they're comparable, then blended differently per horizon:

- **Momentum** — 12-1 month return (Jegadeesh-Titman), blended with 6-month and 1-month.
- **Trend strength** — price vs 50/200-day EMAs, golden-cross posture, 52-week range position.
- **Mean reversion** — oversold (low RSI / near 20-day low) scores high; for short-horizon dip buying.
- **Volume** — today's volume vs the asset's own 20-day average.
- **Relative strength** — the asset's 5-day move minus its category's average.
- **Intel** — the existing news/Reddit/filings/congress score (still the lead).

Per-tier weighting:
- SHORT (0-72h): 40% mean-reversion, 25% volume, 20% intel, 15% relative strength
- LONG (4-30d): 30% momentum, 25% trend, 20% intel, 15% volume, 10% mean-reversion
- HOLD (1-18mo): 45% momentum, 35% trend, 20% intel

A market-regime tilt (from breadth — % of universe above its 200-day) shifts weight
toward momentum in trending markets and toward mean-reversion in choppy ones. A genuine
scheduled catalyst (earnings/IPO/congressional buying) gets a score floor so it stays
visible regardless of chart posture.

This shifts the odds and stabilizes ranking. It does not predict the future or guarantee
returns — every factor here is standard quant practice.

## v3.2 changes

- **Unique tabs.** Each asset is assigned to its single best-fit horizon (greedy,
  strongest-first with fallback), so no asset appears in more than one tab. Every
  tab stays as full as the candidate pool allows.
- **30-day memory** (was 15). Signals and decisions are retained for 30 days per asset.
- **Database drives the decision.** Each cycle reads the 30-day stored signals
  (per-coin/per-stock signal counts add a conviction bonus) and the stored decision
  history (EWMA-smoothed) before producing the final rank. Combined with the
  cross-sectional z-scoring (every asset measured against every other), the final
  rank is a function of the whole database, not just the current snapshot.

## v4.0 changes

- **Forward projections.** Every pick now carries an expected-move projection: a
  likely price RANGE over the tier's horizon (≈2 sessions / 2-3 weeks / 3 months),
  derived from the asset's volatility (ATR, scaled by √time) and a capped momentum
  drift. Shown as a 1-sigma band (~68% odds) plus a wider 2-sigma band (~95%),
  centered on a drift-adjusted estimate. It is a probability range, NOT a guarantee —
  earnings, news, and gaps can break any band.
- **Pre-market passes.** The container runs on America/New_York time and fires extra
  decision cycles at 08:40 and 09:25 ET, so fresh forward projections exist before
  the 9:30 open — what to expect today, calculated before today starts.
- **IPOs are first-class assets.** Recently detected IPO tickers are merged into the
  candidate universe every cycle. The moment an IPO is trading it gets full factor
  scoring, a projection, triggers, and a chart like any other asset. The IPO tab now
  has a View button: trading IPOs open their full detail; not-yet-listed ones show an
  info card. Universe refreshes continuously (well within "daily").
