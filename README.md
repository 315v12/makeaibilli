# makeaibilli — trading intelligence dashboard

A self-hosted stock and crypto scanner that runs 24/7 on your own hardware,
scrapes news, filings, and social chatter, ranks the results with a real
multi-factor model, and shows you disciplined forward projections and
buy/sell triggers before the market opens.

**Runs entirely on your machine.** No cloud costs, no data sent anywhere,
no ads. Your Finnhub key stays local; your database stays local.

**v3.0 — final.** Honest about what software can and can't do: it ranks
assets, projects likely ranges with confidence bands, and surfaces catalysts
you'd otherwise miss. It does not predict exact future prices. Nothing here
is financial advice.

---

## Table of contents

1. [What you get](#what-you-get)
2. [Requirements](#requirements)
3. [Step 1 — Get a free Finnhub API key](#step-1--get-a-free-finnhub-api-key)
4. [Step 2 — Download and extract](#step-2--download-and-extract)
5. [Step 3 — Configure your .env](#step-3--configure-your-env)
6. [Step 4 — Build and run](#step-4--build-and-run)
7. [Step 5 — Open the dashboard](#step-5--open-the-dashboard)
8. [Using the dashboard](#using-the-dashboard)
9. [Daily operation](#daily-operation)
10. [Troubleshooting](#troubleshooting)
11. [How the engine works (brief)](#how-the-engine-works-brief)
12. [File layout](#file-layout)
13. [Honest caveats](#honest-caveats)

---

## What you get

Two web pages served from your machine, one for stocks and one for crypto,
each with the same shape:

- **Short-term (0–72h)** · **Long-term (4–30d)** · **Hold (1–18mo)** — every
  asset appears in exactly one tab, ranked by a factor composite that's
  z-scored across the whole universe.
- **IPOs** / **New listings** — upcoming and recently traded IPOs (stocks)
  and coins newly listed on Coinbase (crypto). Both auto-enter the analysis
  universe the moment they start trading.
- **Newly Listed** tab — IPOs that are now trading, with the full analysis.
- **Emerging** tab (crypto) — coins with the strongest fresh momentum +
  volume surge that didn't already place in a tier.

Tap **View →** on any asset for:
- A forward **expected-move projection** — the likely price range for the
  next 2 sessions / 2-3 weeks / 3 months, with confidence bands.
- **Buy triggers** and **sell triggers** — specific price levels for that
  asset, derived from its own chart structure.
- **Factor breakdown** — momentum, trend, mean-reversion, volume, relative
  strength, intel — the z-scores driving its rank.
- **Position calculator** — enter quantity + price, get the total cost.
- **About** — real description, founders, founding date, headquarters
  (Wikipedia/Wikidata for stocks, CoinGecko for crypto).
- **Full-screen TradingView chart** (with an "Open in TradingView" link
  for the best mobile experience).

Pre-market decision passes at **08:40 and 09:25 ET** — you have fresh
projections before the 9:30 open.

---

## Requirements

- **Linux host** (tested on Ubuntu 22). macOS or Windows-with-WSL2 will work
  if you can install podman-compose there.
- **~4GB RAM free** (an 8GB machine is comfortable).
- **~5GB free disk** (databases grow slowly, plus a couple hundred MB for
  container images).
- **Podman + podman-compose** installed. Docker also works if you swap
  `podman-compose` for `docker-compose` throughout.
- **Internet connection** — the engine scrapes web sources 24/7.
- **A Finnhub free-tier API key** (next step).

Install podman-compose on Ubuntu:
```bash
sudo apt install -y podman
pip3 install --user podman-compose
```

---

## Step 1 — Get a free Finnhub API key

Finnhub provides the earnings calendar and IPO calendar. Free tier is 60
API calls/minute — more than enough for makeaibilli.

1. Go to **https://finnhub.io/**
2. Click **Get free API key** (top right).
3. Sign up with an email (no credit card required).
4. Verify your email address.
5. On the dashboard, copy the key labelled **API Key** — it's a ~40-character
   string of letters and digits.
6. Keep this window open — you'll paste the key into `.env` in Step 3.

**Free tier limits:** 60 requests per minute, unlimited daily. makeaibilli
throttles itself to stay well under this.

You do **not** need any other API keys. Reddit, StockTwits, SEC EDGAR,
Congress trades, Coinbase, Yahoo, Wikipedia, and CoinGecko are all called
without authentication.

---

## Step 2 — Download and extract

Grab the release tarball `makeaibilli_v3.0.tar.gz` (from this repo's
Releases page or wherever you're distributing it). Put it in your home
folder and extract:

```bash
cd ~
tar -xzf makeaibilli_v3.0.tar.gz
cd makeaibilli
```

You'll now have a folder tree like:

```
makeaibilli/
├── build.sh              # one-command build + run
├── docker-compose.yaml
├── docker/               # Dockerfiles for scraper + dashboard
├── src/                  # all the Python
├── data/                 # runtime data (databases + custom logos)
├── requirements.txt
├── .env.template         # copy this to .env in Step 3
├── .gitignore
├── README.md
└── VERSION.txt
```

---

## Step 3 — Configure your .env

Copy the template and paste in your Finnhub key:

```bash
cp .env.template .env
nano .env
```

The one line you MUST change:

```
FINNHUB_API_KEY=paste-your-key-here
```

Save and close (`Ctrl+X`, then `Y`, then `Enter` in nano). Everything else
in `.env` has sensible defaults; adjust only if you know what you're doing.

**Optional custom logos.** Drop two files into `data/` if you want your
own branding on the header:
- `data/logo`  — shown on the Stocks page
- `data/prestige` — shown on the Crypto page

Any image format (PNG, JPEG, GIF, WEBP, SVG) works. No extension required —
the dashboard sniffs the file type from its bytes.

---

## Step 4 — Build and run

One command:

```bash
./build.sh
```

This runs `podman-compose build --no-cache` with a progress bar (the raw
pip output would flood your terminal), then starts three containers:
`redis`, `makeaibilli_scraper_1`, `makeaibilli_dashboard_1`.

First build takes 3-5 minutes depending on your network. Subsequent builds
are faster.

**When it finishes**, you'll see:

```
✅  Running.  Dashboard:  http://localhost:8501
    (from your phone:    http://192.168.x.x:8501 )
```

If you'd rather run the raw commands:
```bash
podman-compose build --no-cache
podman-compose up -d
```

---

## Step 5 — Open the dashboard

**On the same machine:** open **http://localhost:8501** in a browser.

**From your phone (same Wi-Fi):**

1. Get the machine's LAN address:
   ```bash
   hostname -I
   ```
   Grab the first number that starts with `192.168.` or `10.` — that's your
   home-network address.

2. On your phone, open Safari and go to:
   ```
   http://192.168.x.x:8501
   ```
   (using the real number from step 1)

3. Tap **Share → Add to Home Screen** to get an app-like icon on your phone.

**Firewall gotcha:** if the phone can't connect, allow port 8501:
```bash
sudo ufw allow 8501
```

## First-cycle warm-up

The dashboard loads instantly, but the picks fill in a couple of minutes
after startup — the engine has to do one hard scrape and one decision pass
before Short/Long/Hold populate. IPOs appear first (pulled from the Finnhub
calendar), then the ranked tabs, then Emerging and New listings.

If you see empty tabs 5 minutes after boot, check the log:
```bash
podman logs --tail 60 makeaibilli_scraper_1
```

---

## Using the dashboard

### Side navigation
Vertical icon strip on the right edge:
- 📈 or your custom logo — Stocks page
- Prestige emblem — Crypto page
- ⚙️ — Settings (Debug feed + Status)

### Stocks page — 5 tabs

| Tab | What's in it |
|---|---|
| **Short-term** | Top 30 stocks best suited to a 0–72h horizon |
| **Long-term** | Top 30 for 4–30 days |
| **Hold** | Top 30 for 1–18 months |
| **Newly Listed** | IPOs now trading, with full analysis |
| **IPOs** | Upcoming / not-yet-trading, with rich profile bullets |

Every asset appears in exactly one of Short/Long/Hold — no repeats.

### Crypto page — 5 tabs
Same shape, plus **Emerging** (fresh momentum) and **Newly Listed**
(recently added to Coinbase).

### Detail view (tap View → on any asset)
Top-to-bottom:
1. **Ticker + name + status chips** (price, today's change, category, tier).
2. **📊 Open full chart →** button — dedicated chart page with TradingView.
3. **Projected range (forward)** — likely price band over the tier's horizon,
   plus a wider 2-sigma band. This is a probability range from volatility +
   momentum, not a promise.
4. **Why it's on the list** — bullet points explaining what drove the rank.
5. **About this company/coin** — Wikipedia/Wikidata (stocks) or CoinGecko
   (crypto) facts: description, founders, founded, headquarters, categories.
6. **Factor breakdown** — the six z-scores driving the rank.
7. **Position calculator** — units × price = total cost. Just a calculator,
   not an order form.
8. **BUY triggers** — specific price levels to buy at, each with why.
9. **SELL triggers** — profit targets and stop-loss levels.

### Chart page (tap 📊 Open full chart →)
Full-screen TradingView with RSI + moving averages pre-loaded. If it looks
cramped on your phone, tap **Open in TradingView ↗** in the top-right for
the real, unconstrained TradingView experience.

### Settings → Status
- Per-scraper health dots (green/yellow/red) with the latest count and time.
- Database size: signals count, decisions count, MB on disk, per-asset DB count.

### Settings → Debug
Live event feed from every scraper and decision cycle. Handy when something
seems off.

---

## Daily operation

### Watch what it's doing right now
```bash
podman logs -f makeaibilli_scraper_1
```

You'll see a pattern like:
```
23:15:00  ○ light scrape  · news:47 reddit:32 stocktwits:12 …
23:45:00  ● hard scrape   · Fortune 500 + IPO + filings
00:00:00  ★ DECISIONS     · 30 short · 30 long · 30 hold
                          · [crypto] 20 short · 20 long · 20 hold
```

### Restart cleanly
```bash
cd ~/makeaibilli
podman-compose down
./build.sh
```

### Stop
```bash
cd ~/makeaibilli
podman-compose down
```

### Update to a new version
```bash
cd ~/makeaibilli
podman-compose down
tar -xzf ../makeaibilli_v4.x.tar.gz    # merges over; preserves data/ and .env
./build.sh
```

Your `data/` folder (databases, custom logos) and `.env` (Finnhub key)
are never touched by extraction — the tarball only overwrites source files.

### Sync to GitHub (optional)
```bash
cd ~/makeaibilli
git add -A
git commit -m "your change"
git push
```

`.gitignore` blocks `.env` and `data/` from being committed. Verify with
`git status` before any push.

---

## Troubleshooting

**"Env file does not exist" error on build**
You skipped Step 3. Run `cp .env.template .env` and paste your Finnhub key.

**Containers stuck in "Created" state**
```bash
podman rm -f -a
./build.sh
```

**Redis connection refused**
Check that `REDIS_HOST=127.0.0.1` (not `redis`) in `.env`, and that all
three services are on host networking — this is set correctly in the
shipped `docker-compose.yaml`. Restart with `./build.sh`.

**Dashboard loads but tabs are empty for more than 10 minutes**
```bash
podman logs --tail 100 makeaibilli_scraper_1
```
Look for exceptions. Most commonly: an invalid Finnhub key (rate-limited
response), or Yahoo Finance temporarily throttling your IP.

**Phone can't reach the dashboard on the same Wi-Fi**
```bash
sudo ufw allow 8501
```
And confirm both devices are on the same network (not one on 5GHz and one
on guest Wi-Fi).

**Chart looks cramped on phone**
Use the **Open in TradingView ↗** link in the top-right of the chart page.
That opens the real TradingView site — full-screen, fully interactive,
no iframe constraints.

**"Your push would publish a private email address" from GitHub**
Your GitHub account has private email on. Use your no-reply address:
```bash
git config user.email "12345678+yourusername@users.noreply.github.com"
git commit --amend --reset-author --no-edit
git push
```
Find your no-reply email at https://github.com/settings/emails.

**Podman error about "short-name resolution"**
Fully-qualified image names are already used in the shipped
`docker-compose.yaml` (`docker.io/library/redis:7-alpine` etc.). If you
customized it, revert or add `docker.io/` prefixes.

---

## How the engine works (brief)

**Per-asset SQLite storage.** Every stock and coin gets its own database
file at `data/assets/<TICKER>.db`, holding 30 days of signals and decisions.

**Two-clock cadence:**
- **Light scrape** every 30 min — news, Reddit, StockTwits, Finviz,
  influencer chatter. Data-only, does NOT change the ranked lists.
- **Hard scrape** every 60 min — Fortune 500 by name, SEC filings, Congress
  trades, earnings calendar, IPO calendar, new Coinbase listings. Still
  data-only.
- **Decisions** every 90 min — the ONLY thing that changes the tabs. Reads
  the fresh queue + the 30-day store, runs the factor model, ranks, projects,
  writes back.
- **Pre-market passes** at 08:40 and 09:25 ET so fresh projections exist
  before the 9:30 open.

**Six-factor composite ranking:**
- Momentum (12-1 blend), Trend strength, Mean-reversion, Volume, Relative
  strength, Intel. Each z-scored across the universe. Per-tier weighting
  (short favors mean-reversion + volume; hold favors momentum + trend).
- **Regime tilt** from market breadth: trending market → boost momentum;
  choppy → boost mean-reversion.
- **EWMA smoothing** against the stored decision history so ranks are
  sticky, not whipsaw.

**Forward projections:** volatility (ATR) sets the band width, scaled by √time
so longer horizons are wider. Capped momentum drift sets the center bias.
1-sigma band ≈ 68% odds, 2-sigma ≈ 95% — if moves were normal, which they
aren't in reality (gaps, news). Treat as odds, not certainty.

---

## File layout

```
makeaibilli/
├── build.sh                        # one-shot build + start
├── docker-compose.yaml             # 3 services on host networking
├── docker/
│   ├── Dockerfile.scraper
│   └── Dockerfile.dashboard
├── .env.template                   # copy to .env
├── .env                            # your keys (gitignored)
├── .gitignore                      # blocks .env, data/, __pycache__
├── data/                           # runtime state (gitignored)
│   ├── assets/                     # one <TICKER>.db per asset
│   ├── enrich/                     # cached Wikipedia/CoinGecko facts
│   ├── known_products.json         # Coinbase product snapshot
│   ├── logo                        # optional: your Stocks header image
│   └── prestige                    # optional: your Crypto header image
├── requirements.txt
├── README.md                       # this file
├── VERSION.txt
└── src/
    ├── main.py                     # orchestrator: schedules + boot
    ├── scrapers/                   # every data source
    │   ├── news_scraper.py
    │   ├── reddit_scraper.py
    │   ├── stocktwits_scraper.py
    │   ├── finviz_scraper.py
    │   ├── influencer_scraper.py
    │   ├── sec_scraper.py
    │   ├── congress_scraper.py
    │   ├── earnings_scraper.py
    │   ├── ipo_scraper.py          # + Finnhub profile enrichment
    │   ├── company_news_scraper.py # Fortune 500 by name
    │   ├── new_coin_scraper.py     # Coinbase new-listing detection
    │   └── asset_enricher.py       # Wikipedia + Wikidata + CoinGecko
    ├── analysis/
    │   ├── universe.py             # curated stock list
    │   ├── fortune500.py           # dynamic Fortune 500
    │   ├── names.py                # ticker→name map + crypto_block
    │   ├── ranking.py              # yfinance market data + filters
    │   ├── technical.py            # pure-pandas RSI/MACD/EMA/VWAP/ATR
    │   ├── factors.py              # multi-factor composite scoring
    │   ├── projection.py           # forward expected-move
    │   ├── plan.py                 # per-asset buy/sell triggers
    │   └── scorer.py               # the ranking pipeline
    ├── crypto/
    │   ├── crypto_universe.py      # static + dynamic Coinbase pairs
    │   ├── crypto_scrapers.py      # RSS + Reddit + web search
    │   ├── coinbase.py             # public REST + candles
    │   └── crypto_scorer.py        # crypto ranking pipeline
    ├── dashboard/
    │   └── app.py                  # Streamlit UI
    └── utils/
        ├── state.py                # Redis (queues, alerts, watchlist)
        └── store.py                # per-asset SQLite persistence
```

---

## Honest caveats

- **Not financial advice.** This is a tool that ranks assets, projects
  ranges, and surfaces catalysts. Every trade is your call, made with your
  money, at your risk.
- **No prediction is exact.** Anything claiming to know tomorrow's close is
  lying. What you get is a range with odds — size your positions accordingly.
- **Day trading is high variance.** Most retail day traders lose money net
  of costs. Cash-account settlement rules (T+2 stocks, T+1 options) apply.
- **Taxes matter.** Short-term gains are ordinary income; keep records of
  wash-sale losses. Talk to a CPA before your first big year.
- **Every quant factor in here is public and crowded.** The edge is the
  intel layer + your willingness to read catalysts on smaller names that
  institutional money ignores. The factors just make sure the ranking is
  disciplined once a name surfaces.
- **The engine has zero access to your broker.** It never sees your account,
  never places an order. You execute manually.
- **Data sources.** Finnhub free tier, Coinbase public REST, Yahoo Finance,
  Wikipedia, CoinGecko, SEC EDGAR, public RSS feeds. Respect each source's
  terms of use.

Trade well. Trade small at first. Read every trigger and every projection
before you act on it.
