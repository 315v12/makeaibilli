"""app.py — makeaibilli v2 dashboard.
Statue of Liberty branding. Three tiers (short / long / extra-long), 30 each.
Full company names, decision bullets, time-window buy/sell guidance.
No SPY/QQQ/VIX, no market-status, no dollar values, no risk/reward."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import streamlit as st
from dotenv import load_dotenv
load_dotenv()

from utils.state import (get_alerts, get_scraper_statuses, get_log, get_crypto_alerts)
from utils.store import db_stats

st.set_page_config(page_title="makeaibilli", page_icon="🗽", layout="wide")
st.markdown("""<style>
.stApp{background:#0e1117;} .block-container{padding:2.2rem 1.5rem 1rem;max-width:1300px;}
.brand{display:flex;align-items:center;gap:12px;line-height:1.4;padding-top:6px;}
.brand h1{font-size:30px;font-weight:700;color:#fff;margin:0;line-height:1.4;}
.row{background:#1a1d27;border-radius:10px;padding:12px 16px;margin-bottom:8px;border-left:4px solid #2b3550;}
.row-cat{border-left-color:#FFD23F !important;background:#211f14 !important;}
.buy{background:#0F3D1F;border-radius:8px;padding:10px 14px;margin:6px 0;color:#4ADE80;font-size:13px;line-height:1.6;}
.sell{background:#3D1A00;border-radius:8px;padding:10px 14px;margin:6px 0;color:#FB923C;font-size:13px;line-height:1.6;}
.chip{background:#252836;color:#9aa;padding:2px 8px;border-radius:20px;font-size:11px;margin-right:4px;}
/* fixed clickable side navigation stack */
.sidenav{position:fixed;right:14px;top:32%;z-index:9999;display:flex;flex-direction:column;
  gap:20px;align-items:center;}
.navbtn{text-decoration:none;text-align:center;display:block;}
.navbtn .cap{display:block;font-size:10px;font-weight:700;margin-top:2px;letter-spacing:.5px;}
.navbtn:hover{filter:brightness(1.2);}
a.navlink{text-decoration:none;}
</style>""", unsafe_allow_html=True)


# Custom logos from the data folder (host: makeaibilli/data/  ->  container: /data).
#   file named 'logo'      -> used for STOCKS
#   file named 'prestige'  -> used for CRYPTO
# Extension optional — the type is detected from the file's contents.
import base64, glob
_LOGO_CACHE = {}

def _sniff_mime(b: bytes):
    if b[:8] == b'\x89PNG\r\n\x1a\n':                 return "image/png"
    if b[:3] == b'\xff\xd8\xff':                       return "image/jpeg"
    if b[:6] in (b'GIF87a', b'GIF89a'):                return "image/gif"
    if b[:4] == b'RIFF' and b[8:12] == b'WEBP':        return "image/webp"
    s = b.lstrip()[:5].lower()
    if s.startswith(b'<?xml') or s.startswith(b'<svg'): return "image/svg+xml"
    return None

def _logo_uri(keyword: str):
    if keyword in _LOGO_CACHE:
        return _LOGO_CACHE[keyword]
    uri = None
    cands = [p for p in glob.glob("/data/*")
             if keyword in os.path.basename(p).lower() and not p.endswith(".db")]
    for f in sorted(cands):
        try:
            with open(f, "rb") as fh:
                b = fh.read()
            mime = _sniff_mime(b)
            if not mime:
                continue
            uri = f"data:{mime};base64," + base64.b64encode(b).decode()
            break
        except Exception:
            continue
    _LOGO_CACHE[keyword] = uri
    return uri

def logo_html(kind="crypto", px=46):
    """kind 'crypto' -> data/prestige* ; kind 'stocks' -> data/logo* ; else gold SVG."""
    uri = _logo_uri("prestige" if kind == "crypto" else "logo")
    if uri:
        return (f'<img src="{uri}" width="{px}" height="{px}" '
                f'style="vertical-align:middle;border-radius:50%;object-fit:cover;'
                f'box-shadow:0 0 6px rgba(255,210,63,.5)">')
    return prestige_svg(px)


# Original gold prestige-style emblem (static). Not a copy of any game's art.
def prestige_svg(px=46):
    return f'''<svg width="{px}" height="{px}" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg"
        style="filter:drop-shadow(0 0 5px rgba(255,210,63,.55));vertical-align:middle">
      <defs>
        <radialGradient id="gold" cx="50%" cy="38%" r="65%">
          <stop offset="0%" stop-color="#FFF6CC"/><stop offset="40%" stop-color="#FFD23F"/>
          <stop offset="78%" stop-color="#C8941A"/><stop offset="100%" stop-color="#6E4F0C"/>
        </radialGradient>
        <linearGradient id="rim" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#FFE9A0"/><stop offset="100%" stop-color="#8a6a12"/>
        </linearGradient>
      </defs>
      <circle cx="50" cy="50" r="47" fill="url(#rim)"/>
      <circle cx="50" cy="50" r="42" fill="url(#gold)" stroke="#5a430b" stroke-width="1.5"/>
      <circle cx="50" cy="50" r="33" fill="none" stroke="#fff3c4" stroke-width="1.2" opacity="0.5"/>
      <!-- wings / laurels -->
      <path d="M22 58 Q10 48 18 33 Q24 44 30 50" fill="none" stroke="#7A5A0F" stroke-width="3.2" stroke-linecap="round"/>
      <path d="M78 58 Q90 48 82 33 Q76 44 70 50" fill="none" stroke="#7A5A0F" stroke-width="3.2" stroke-linecap="round"/>
      <!-- central star -->
      <path d="M50 22 L57.5 43 L80 43 L61.5 56 L69 78 L50 64 L31 78 L38.5 56 L20 43 L42.5 43 Z"
            fill="#FFFBE6" stroke="#8a6a12" stroke-width="1.4"/>
      <circle cx="50" cy="50" r="6" fill="#C8941A" stroke="#5a430b" stroke-width="1"/>
    </svg>'''

if "selected" not in st.session_state: st.session_state.selected = None


def _sidenav(page):
    links = []
    if page != "crypto":
        links.append(f'<a class="navbtn" href="?page=crypto" target="_self" title="Crypto">'
                     f'{logo_html("crypto",46)}<span class="cap" style="color:#FFD23F">CRYPTO</span></a>')
    if page != "stocks":
        links.append(f'<a class="navbtn" href="?page=stocks" target="_self" title="Stocks">'
                     f'{logo_html("stocks",44)}'
                     f'<span class="cap" style="color:#4ADE80">STOCKS</span></a>')
    links.append('<a class="navbtn" href="?page=settings" target="_self" title="Debug &amp; Status">'
                 '<span style="font-size:34px">⚙️</span>'
                 '<span class="cap" style="color:#9aa">SETTINGS</span></a>')
    st.markdown(f'<div class="sidenav">{"".join(links)}</div>', unsafe_allow_html=True)


def header(page="stocks"):
    if page == "crypto":
        st.markdown(
            f'<div class="brand">{logo_html("crypto",40)}'
            f'<h1>makeai<b>billi</b> <small style="color:#666;font-size:14px">crypto · v3.0</small></h1></div>',
            unsafe_allow_html=True)
    elif page == "settings":
        st.markdown('<div class="brand"><h1>makeai<b>billi</b> ⚙️ '
                    '<small style="color:#666;font-size:14px">settings</small></h1></div>',
                    unsafe_allow_html=True)
    else:
        st.markdown(
            f'<div class="brand">{logo_html("stocks",40)}'
            f'<h1>makeai<b>billi</b> <small style="color:#666;font-size:14px">v3.0</small></h1></div>',
            unsafe_allow_html=True)
    _sidenav(page)
    st.divider()


def detail(a):
    if st.button("← Back to list"):
        st.session_state.selected = None; st.rerun()
    chg = a["change_pct"]
    cat = f" &nbsp; {a['catalyst_stamp']}" if a.get("catalyst_stamp") else ""
    st.markdown(f"# {a['ticker']} — {a.get('name', a['ticker'])}{cat}", unsafe_allow_html=True)
    st.markdown(f"<span style='font-size:18px;color:#888'>${a['price']} "
                f"<span style='color:{'#4ADE80' if chg>=0 else '#F87171'}'>{'+' if chg>=0 else ''}{chg}% today</span></span> "
                f"&nbsp;<span class='chip'>{a['category']}</span>"
                f"<span class='chip'>{TIER_LABEL[a['tier']]}</span>", unsafe_allow_html=True)
    rs = a.get('rs_vs_category')
    peer = f" · vs peers {'+' if rs>=0 else ''}{rs}%" if rs is not None else (f" · 24h vol {a.get('vol_ratio','')}x" if a.get('vol_ratio') else "")
    st.caption(f"7-day move {'+' if a['perf_7d']>=0 else ''}{a['perf_7d']}%{peer}")

    # Chart button — opens dedicated full-screen chart page
    kind = "crypto" if a.get("category") == "Crypto" else "stocks"
    st.markdown(
        f'<a href="?page=chart&t={a["ticker"]}&kind={kind}" target="_self" '
        f'style="display:inline-block;background:#FFD23F;color:#000;padding:10px 20px;'
        f'border-radius:8px;font-weight:700;text-decoration:none;margin:8px 0">'
        f'📊 Open full chart →</a>', unsafe_allow_html=True)

    # ── forward projection (expected-move range) ──────────────────────────────
    proj = a.get("projection") or {}
    if proj:
        from analysis.projection import projection_sentence
        center, lo1, hi1 = proj["center"], proj["low_1s"], proj["high_1s"]
        lo2, hi2 = proj["low_2s"], proj["high_2s"]
        bias_color = "#4ADE80" if proj["exp_return_pct"] > 0.2 else "#F87171" if proj["exp_return_pct"] < -0.2 else "#FFD23F"
        st.markdown("#### Projected range (forward)")
        st.markdown(
            f"<div style='background:#10131a;border:1px solid #1c2230;border-radius:10px;padding:14px'>"
            f"<div style='font-size:13px;color:#9aa'>Likely range over ~{proj['horizon_days']} sessions</div>"
            f"<div style='font-size:24px;font-weight:800;color:{bias_color};margin:4px 0'>"
            f"${lo1} – ${hi1}</div>"
            f"<div style='font-size:13px;color:#9aa'>center ≈ <b style='color:#fff'>${center}</b> "
            f"&nbsp;·&nbsp; expected move ±{proj['band_pct']}% "
            f"&nbsp;·&nbsp; wider band ${lo2} – ${hi2}</div>"
            f"</div>", unsafe_allow_html=True)
        st.caption("Probability range from this asset's volatility + momentum — not a guarantee. "
                   "Earnings, news, and gaps can break any band.")

    st.markdown("#### Why it's on the list")
    for r in a.get("reasons", []):
        st.markdown(f"- {r}")

    # ── About this asset (Wikipedia / CoinGecko facts, cached 30 days) ───────
    try:
        from scrapers.asset_enricher import enrich_stock, enrich_crypto
        is_crypto = a.get("category") == "Crypto"
        with st.spinner("Looking up company / coin facts…"):
            info = (enrich_crypto(a["ticker"]) if is_crypto
                    else enrich_stock(a["ticker"], a.get("name","")))
        if info and (info.get("description") or info.get("founded")
                     or info.get("founders") or info.get("genesis_date")):
            st.markdown("#### About this " + ("coin" if is_crypto else "company"))
            if info.get("description"):
                st.markdown(info["description"])
            bullets = []
            def _b(label, value, fmt=None):
                if value in (None, "", 0, [], False): return
                bullets.append(f"**{label}:** " + (fmt(value) if fmt else str(value)))
            if is_crypto:
                _b("Name",              info.get("name"))
                _b("Genesis date",      info.get("genesis_date"))
                _b("Country of origin", info.get("country_origin"))
                _b("Hashing algorithm", info.get("hashing_algorithm"))
                _b("Block time",        info.get("block_time_minutes"), lambda v: f"~{v} min")
                _b("Categories",        info.get("categories"), lambda v: ", ".join(v))
                _b("Homepage",          info.get("homepage"))
                _b("GitHub",            info.get("github"), lambda v: " · ".join(v))
                if info.get("twitter"):   _b("Twitter / X", "@" + info["twitter"])
                if info.get("subreddit"): _b("Subreddit",   info["subreddit"])
            else:
                _b("Founded",      info.get("founded"))
                _b("Founders",     info.get("founders"), lambda v: ", ".join(v))
                _b("CEO",          info.get("ceo"))
                _b("Owners",       info.get("owners"), lambda v: ", ".join(v))
                _b("Headquarters", info.get("headquarters"))
                _b("Country",      info.get("country"))
                _b("Description",  info.get("short_description"))
                _b("Wikipedia",    info.get("wikipedia_url"))
            for b in bullets[:20]:
                st.markdown(f"- {b}")
            st.caption("Facts from Wikipedia / Wikidata (stocks) or CoinGecko (crypto). "
                       "First view fetches and caches; subsequent views are instant.")
    except Exception:
        pass

    fac = a.get("factors") or {}
    if fac:
        st.markdown("#### Factor breakdown")
        st.caption("Each is z-scored across the universe; the tier blends them differently "
                   "(short favors mean-reversion + volume, hold favors momentum + trend).")
        frows = "".join(
            f"<div style='display:flex;justify-content:space-between;padding:4px 0;"
            f"border-bottom:1px solid #1c1c22'><span style='color:#9aa'>{k}</span>"
            f"<b style='color:#FFD23F'>{v}</b></div>"
            for k, v in fac.items())
        st.markdown(f"<div style='font-size:13px'>{frows}</div>", unsafe_allow_html=True)

    # ── position calculator: units × price = total cost ───────────────────────
    tk = a["ticker"]
    st.markdown("#### Position calculator")
    cc = st.columns(2)
    with cc[0]:
        qty = st.number_input("How many units", min_value=0.0, value=10.0,
                              step=1.0, key=f"qty_{tk}")
    with cc[1]:
        px = st.number_input("Price each ($)", min_value=0.0, value=float(a["price"]),
                             step=0.01, format="%.4f", key=f"px_{tk}")
    st.text_input("Total cost ($)", value=f"{qty * px:,.2f}", disabled=True)
    st.caption("Type how many units and the price you'd pay — the total updates automatically. "
               "Price is prefilled with the current price but you can type any number. "
               "This is just a calculator, not an order.")

    st.markdown(f"#### BUY triggers ({len(a.get('buy_triggers',[]))})")
    erows = "".join(
        f"<div style='padding:6px 0;border-bottom:1px solid #14301d'>"
        f"<b style='color:#4ADE80'>{s['trigger']}</b>"
        f"<div style='font-size:12px;color:#6b8f7a'>{s['why']}</div></div>"
        for s in a.get('buy_triggers',[]))
    st.markdown(f"<div class='buy'>{erows or 'Not enough price history yet.'}</div>", unsafe_allow_html=True)

    st.markdown(f"#### SELL triggers ({len(a.get('sell_triggers',[]))})")
    xrows = "".join(
        f"<div style='padding:6px 0;border-bottom:1px solid #3a2410'>"
        f"<b style='color:#FB923C'>{s['trigger']}</b>"
        f"<div style='font-size:12px;color:#9c7a55'>{s['why']}</div></div>"
        for s in a.get('sell_triggers',[]))
    st.markdown(f"<div class='sell'>{xrows or 'Not enough price history yet.'}</div>", unsafe_allow_html=True)
    st.caption(f"Hold horizon: {a['hold_label']} · {a['exit_rule']}. "
               "Each trigger above is a specific price for this stock — act when price reaches it.")


def chart_page():
    """Dedicated full-screen chart page for a single asset."""
    import streamlit.components.v1 as components
    ticker = st.query_params.get("t", "")
    kind = st.query_params.get("kind", "stocks")
    if not ticker:
        st.error("No ticker specified."); return
    header(kind)  # show side nav so you can still navigate
    back_page = "crypto" if kind == "crypto" else "stocks"
    tv_symbol = f"COINBASE:{ticker}USD" if kind == "crypto" else ticker
    tv_url = (f"https://www.tradingview.com/chart/?symbol=COINBASE%3A{ticker}USD"
              if kind == "crypto" else
              f"https://www.tradingview.com/chart/?symbol={ticker}")
    st.markdown(
        f'<a href="?page={back_page}" target="_self" '
        f'style="color:#9aa;text-decoration:none;font-size:13px">← Back</a> '
        f'<span style="font-size:24px;font-weight:700;color:#fff;margin-left:8px">{ticker}</span> '
        f'<a href="{tv_url}" target="_blank" '
        f'style="float:right;color:#FFD23F;text-decoration:none;font-size:13px;font-weight:600">'
        f'Open in TradingView ↗</a>',
        unsafe_allow_html=True)
    # Tall, explicit dimensions — TradingView's "autosize" mis-reads Streamlit
    # iframes on mobile, leaving a top-trim view. Hard-set 100% width and a
    # large pixel height; let the component iframe match so the chart fills.
    H = 900
    chart_html = f'''
    <div class="tradingview-widget-container" style="height:{H}px;width:100%">
      <div id="tvchartfull" style="height:{H}px;width:100%"></div>
      <script type="text/javascript"
        src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js" async>
      {{
        "width": "100%", "height": "{H}",
        "symbol": "{tv_symbol}", "interval": "D", "timezone": "America/New_York",
        "theme": "dark", "style": "1", "locale": "en", "hide_side_toolbar": false,
        "allow_symbol_change": true, "withdateranges": true,
        "studies": ["MASimple@tv-basicstudies","RSI@tv-basicstudies"],
        "container_id": "tvchartfull"
      }}
      </script>
    </div>'''
    components.html(chart_html, height=H + 20, scrolling=True)
    st.caption("If the chart still looks cramped on your phone, tap "
               "**Open in TradingView ↗** above — it gives you the full native experience.")


TIER_LABEL = {"short":"Short-term · 0–72h","long":"Long-term · 4–30d","xlong":"Hold · 1–18mo"}

def tier_list(tier, source="stocks"):
    alerts_all = get_crypto_alerts() if source == "crypto" else get_alerts()
    alerts = [a for a in alerts_all if a.get("tier")==tier]
    alerts.sort(key=lambda x: x.get("rank",99))
    if not alerts:
        st.info("Building this list — first sweep runs on startup, then every 15 min."); return
    for a in alerts:
        chg = a["change_pct"]
        cls = "row row-cat" if a.get("catalyst_stamp") else "row"
        cat = f" {a['catalyst_stamp']}" if a.get("catalyst_stamp") else ""
        ci, cb = st.columns([5,1])
        with ci:
            st.markdown(f"""<div class="{cls}">
            <span style="font-size:14px;color:#FFD23F;font-weight:700">#{a.get('rank','')}</span>
            <span style="font-size:18px;font-weight:700;color:#fff;margin-left:8px">{a['ticker']}</span>
            <span style="font-size:13px;color:#aaa;margin-left:8px">{a.get('name','')}</span>{cat}
            <span style="font-size:13px;color:#888;margin-left:8px">${a['price']}</span>
            <span style="font-size:12px;color:{'#4ADE80' if chg>=0 else '#F87171'};margin-left:6px">{'+' if chg>=0 else ''}{chg}%</span>
            <div style="font-size:11px;color:#666;margin-top:4px">{a['category']} · 7d {'+' if a['perf_7d']>=0 else ''}{a['perf_7d']}% · hold {a.get('hold_label','')}</div>
            </div>""", unsafe_allow_html=True)
        with cb:
            st.write("")
            if st.button("View →", key=f"{source}{tier}{a['ticker']}", use_container_width=True):
                st.session_state.selected = (source, a['ticker']); st.rerun()



def ipo_list():
    from utils.store import get_recent_ipos
    ipos = get_recent_ipos(10)
    if not ipos:
        st.info("No upcoming IPOs detected in the last few days. The IPO calendar is checked on the hourly sweep."); return
    st.caption("Companies going public. Once one is trading it's analyzed like any other asset — "
               "tap View for its projection and chart. Updated daily.")
    live = {a["ticker"] for a in get_alerts()}
    for x in ipos:
        tk = x["ticker"]
        trading = tk in live
        ci, cb = st.columns([5,1])
        with ci:
            badge = ("<span style='font-size:11px;color:#4ADE80;margin-left:8px'>● trading — full analysis</span>"
                     if trading else
                     "<span style='font-size:11px;color:#FFD23F;margin-left:8px'>○ not trading yet</span>")
            st.markdown(f"""<div class="row">
            <span style="font-size:18px;font-weight:700;color:#fff">{tk}</span>
            <span style="font-size:13px;color:#aaa;margin-left:8px">{x.get('company_name','')}</span>
            <span style="font-size:12px;color:#FFD23F;margin-left:8px">{x.get('ipo_date','')}</span>{badge}
            <div style="font-size:12px;color:#888;margin-top:4px">{x.get('headline','')}</div>
            </div>""", unsafe_allow_html=True)
        with cb:
            st.write("")
            if st.button("View →", key=f"ipo{tk}", use_container_width=True):
                # Trading IPOs route to their full asset detail; others to an info card.
                st.session_state.selected = ("stocks", tk) if trading else ("ipo", tk)
                st.rerun()


def ipo_detail(ticker):
    from utils.store import get_recent_ipos
    if st.button("← Back to list"):
        st.session_state.selected = None; st.rerun()
    rec = next((x for x in get_recent_ipos(25) if x["ticker"] == ticker), None)
    st.markdown(f"# {ticker}", unsafe_allow_html=True)
    if not rec:
        st.info("This IPO is no longer in the recent window."); return
    st.markdown(f"<span style='font-size:16px;color:#aaa'>{rec.get('company_name','')}</span> "
                f"&nbsp;<span class='chip'>IPO</span>"
                f"<span class='chip'>{rec.get('ipo_date','')}</span>", unsafe_allow_html=True)

    # ── up to 20 bullets of collected info ───────────────────────────────────
    st.markdown("#### What we've collected")
    bullets = []
    def _add(label, value, fmt=None):
        if value is None or value == "" or value == 0 or value == "0":
            return
        bullets.append(f"**{label}:** " + (fmt(value) if fmt else str(value)))
    _add("Company",            rec.get("company_name"))
    _add("Ticker",             rec.get("ticker"))
    _add("Listing date",       rec.get("ipo_date") or rec.get("profile_ipo_date"))
    _add("Exchange",           rec.get("exchange"))
    _add("Status",             rec.get("status"))
    _add("Industry",           rec.get("industry"))
    _add("Country",            rec.get("country"))
    _add("Currency",           rec.get("currency"))
    _add("Price range",        rec.get("price_range"), lambda v: f"${v}")
    _add("Shares offered",     rec.get("number_of_shares"), lambda v: f"{int(v):,}")
    _add("Estimated raise",    rec.get("total_shares_value"), lambda v: f"${int(v):,}")
    _add("Market cap (est)",   rec.get("market_cap_mln"), lambda v: f"${v:,.0f}M")
    _add("Shares outstanding", rec.get("shares_outstanding_mln"), lambda v: f"{v:,.0f}M")
    _add("Website",            rec.get("weburl"))
    _add("Phone",              rec.get("phone"))
    _add("Source",             rec.get("source"))
    _add("Detected",           rec.get("ts"))
    _add("Headline",           rec.get("headline"))
    if rec.get("logo"):
        bullets.append(f"**Logo:** [{rec['logo']}]({rec['logo']})")
    # Pull anything else we stored that we didn't explicitly format
    seen_keys = {"company_name","ticker","ipo_date","profile_ipo_date","exchange","status",
                 "industry","country","currency","price_range","number_of_shares",
                 "total_shares_value","market_cap_mln","shares_outstanding_mln","weburl",
                 "phone","source","ts","headline","logo","tickers","payload","sentiment",
                 "type","id"}
    for k, v in rec.items():
        if k in seen_keys or v in (None,"",0,"0") or len(bullets) >= 20:
            continue
        bullets.append(f"**{k.replace('_',' ').title()}:** {v}")
    for b in bullets[:20]:
        st.markdown(f"- {b}")

    st.markdown("#### Projection")
    st.info("This company isn't trading yet, so there's no price history to project from. "
            "The moment it starts trading, it's pulled into the universe automatically and gets "
            "the same factor scoring, expected-move projection, triggers, and chart as every other "
            "asset — check back after the listing date. The universe refreshes daily.")


def emerging_list():
    from utils.state import get_crypto_emerging
    coins = get_crypto_emerging()
    if not coins:
        st.info("Emerging coins populate after the first crypto decision pass."); return
    st.caption("Coins with the strongest recent momentum + volume surge — fresh interest building. "
               "Tap View for triggers, projection, and a 20-bullet profile.")
    for x in coins:
        tk = x.get("ticker","")
        m = x.get('mom_5d', 0)
        ci, cb = st.columns([5,1])
        with ci:
            st.markdown(f"""<div class="row">
            <span style="font-size:18px;font-weight:700;color:#fff">{tk}</span>
            <span style="font-size:13px;color:#888;margin-left:8px">${x.get('price','')}</span>
            <span style="font-size:12px;color:{'#4ADE80' if m>=0 else '#F87171'};margin-left:8px">7d {'+' if m>=0 else ''}{m}%</span>
            <span style="font-size:12px;color:#9aa;margin-left:8px">vol {x.get('vol_ratio','')}x</span>
            </div>""", unsafe_allow_html=True)
        with cb:
            st.write("")
            if st.button("View →", key=f"em{tk}", use_container_width=True):
                st.session_state.selected = ("emerging", tk)
                st.rerun()


def new_coin_list():
    """Recently detected Coinbase listings — same View flow as IPOs."""
    from utils.store import get_recent_new_coins
    coins = get_recent_new_coins(15)
    if not coins:
        st.info("No new Coinbase listings detected. Checked on the hourly sweep — "
                "the first run takes a baseline snapshot, so new pairs show up from the second hour on."); return
    st.caption("Coins newly added to Coinbase. Tap View for the structured detail "
               "we've collected. Trading ones get full analysis automatically.")
    live = {a["ticker"] for a in get_crypto_alerts()}
    for x in coins:
        tk = x.get("ticker","")
        trading = tk in live
        ci, cb = st.columns([5,1])
        with ci:
            badge = ("<span style='font-size:11px;color:#4ADE80;margin-left:8px'>● in analysis</span>"
                     if trading else
                     "<span style='font-size:11px;color:#FFD23F;margin-left:8px'>○ joining universe</span>")
            st.markdown(f"""<div class="row">
            <span style="font-size:18px;font-weight:700;color:#fff">{tk}</span>
            <span style="font-size:13px;color:#aaa;margin-left:8px">{x.get('display_name','') or x.get('product_id','')}</span>{badge}
            <div style="font-size:12px;color:#888;margin-top:4px">{x.get('headline','')}</div>
            </div>""", unsafe_allow_html=True)
        with cb:
            st.write("")
            if st.button("View →", key=f"coin{tk}", use_container_width=True):
                st.session_state.selected = ("crypto", tk) if trading else ("newcoin", tk)
                st.rerun()


def coin_detail(ticker):
    """20-bullet structured detail for a newly listed coin."""
    from utils.store import get_recent_new_coins
    if st.button("← Back to list"):
        st.session_state.selected = None; st.rerun()
    rec = next((x for x in get_recent_new_coins(25) if x.get("ticker") == ticker), None)
    st.markdown(f"# {ticker}", unsafe_allow_html=True)
    if not rec:
        st.info("This new-listing record is no longer in the window."); return
    st.markdown(f"<span style='font-size:16px;color:#aaa'>{rec.get('display_name','') or rec.get('product_id','')}</span> "
                f"&nbsp;<span class='chip'>New Coinbase listing</span>", unsafe_allow_html=True)

    st.markdown("#### What we've collected")
    bullets = []
    def _add(label, value, fmt=None):
        if value is None or value == "" or value == 0 or value == "0" or value is False:
            return
        bullets.append(f"**{label}:** " + (fmt(value) if fmt else str(value)))
    _add("Symbol",         rec.get("ticker"))
    _add("Product id",     rec.get("product_id"))
    _add("Display name",   rec.get("display_name"))
    _add("Base currency",  rec.get("base_currency"))
    _add("Quote currency", rec.get("quote_currency"))
    _add("Status",         rec.get("status"))
    _add("Status message", rec.get("status_message"))
    _add("Trading disabled", rec.get("trading_disabled"))
    _add("Post only",      rec.get("post_only"))
    _add("Limit only",     rec.get("limit_only"))
    _add("Cancel only",    rec.get("cancel_only"))
    _add("Auction mode",   rec.get("auction_mode"))
    _add("Min market funds", rec.get("min_market_funds"), lambda v: f"${v}")
    _add("Base min size",  rec.get("base_min_size"))
    _add("Base max size",  rec.get("base_max_size"))
    _add("Base increment", rec.get("base_increment"))
    _add("Quote increment",rec.get("quote_increment"))
    _add("FX stablecoin",  rec.get("fx_stablecoin"))
    _add("Source",         rec.get("source"))
    _add("Detected at",    rec.get("detected_at") or rec.get("ts"))
    _add("Headline",       rec.get("headline"))
    for b in bullets[:20]:
        st.markdown(f"- {b}")

    st.markdown("#### Analysis")
    st.info("Once a candle history exists on Coinbase the engine pulls this coin into the "
            "regular cycle automatically — factor scoring, projection, triggers, chart. "
            "Brand-new listings often need a few hours of candles before the first analysis "
            "pass produces stable numbers.")


def tab_status():
    st.subheader("Engine status")
    try:
        s = db_stats()
        st.caption(f"30-day memory across **{s.get('assets',0)} per-asset databases** · "
                   f"{s['signals']} signals, {s['decisions']} decisions, {s['size_mb']}MB on disk")
    except Exception: pass
    for name, info in (get_scraper_statuses() or {}).items():
        dot = "🟢" if info.get("status")=="ok" else ("🟡" if info.get("status")=="warn" else "🔴")
        st.markdown(f"{dot} **{name}** <span style='font-size:12px;color:#666'>· {info.get('detail','')} · {info.get('updated','')}</span>", unsafe_allow_html=True)


def tab_activity():
    from datetime import datetime
    st.subheader("🌐 Live debug — engine activity")
    cols = st.columns([1,3])
    with cols[0]:
        if st.button("🔄 Refresh", use_container_width=True): st.rerun()
    with cols[1]:
        st.caption(f"Last loaded {datetime.now().strftime('%I:%M:%S %p')} · "
                   "newest first · tap Refresh for latest")
    rows = get_log()
    if not rows:
        st.warning("No activity yet. If this stays empty, the scraper isn't writing — "
                   "check that all 3 containers are up (podman ps).")
        return
    # quick health summary
    errs = sum(1 for r in rows if r.get("level")=="ERROR")
    warns = sum(1 for r in rows if r.get("level")=="WARNING")
    st.markdown(f"<span style='color:#F87171'>● {errs} errors</span> &nbsp; "
                f"<span style='color:#EF9F27'>● {warns} warnings</span> &nbsp; "
                f"<span style='color:#93C5FD'>● {len(rows)} log lines</span>", unsafe_allow_html=True)
    colors = {"ERROR":"#F87171","WARNING":"#EF9F27","INFO":"#93C5FD"}
    html = "".join(
        f"<div style='font-family:monospace;font-size:12px;padding:2px 0;border-bottom:1px solid #1a1d27'>"
        f"<span style='color:#555'>{r.get('ts','')}</span> "
        f"<span style='color:{colors.get(r.get('level','INFO'),'#9aa')};font-weight:600'>{r.get('level','')[:4]}</span> "
        f"<span style='color:#ccc'>{r.get('msg','')}</span></div>" for r in rows[:300])
    st.markdown(f"<div style='max-height:560px;overflow-y:auto;background:#0a0c10;border-radius:8px;padding:10px'>{html}</div>", unsafe_allow_html=True)



def crypto_page():
    header("crypto")
    if st.session_state.selected and st.session_state.selected[0] == "crypto":
        a = {x["ticker"]: x for x in get_crypto_alerts()}.get(st.session_state.selected[1])
        if a: detail(a); return
        st.session_state.selected = None
    if st.session_state.selected and st.session_state.selected[0] == "emerging":
        from utils.state import get_crypto_emerging
        em = {x["ticker"]: x for x in (get_crypto_emerging() or [])}.get(st.session_state.selected[1])
        if em: detail(em); return
        st.session_state.selected = None
    if st.session_state.selected and st.session_state.selected[0] == "newcoin":
        coin_detail(st.session_state.selected[1]); return
    tabs = st.tabs(["Short-term","Long-term","Hold","Emerging","Newly Listed"])
    with tabs[0]: tier_list("short","crypto")
    with tabs[1]: tier_list("long","crypto")
    with tabs[2]: tier_list("xlong","crypto")
    with tabs[3]: emerging_list()
    with tabs[4]: new_coin_list()


def newly_listed_stocks_list():
    """IPOs that have started trading — full analysis available, View routes to detail."""
    from utils.store import get_recent_ipos
    ipos = get_recent_ipos(25)
    live = {a["ticker"]: a for a in get_alerts()}
    listed = [x for x in ipos if x.get("ticker") in live]
    if not listed:
        st.info("No newly listed IPOs in the analysis yet. Recently traded IPOs appear here once "
                "the engine has enough price history to compute factors and a projection."); return
    st.caption("IPOs that are now trading and being analyzed. Each gets full triggers + projection. "
               "Tap View for the company profile + the same forward-looking analysis as any pick.")
    for x in listed:
        tk = x["ticker"]; a = live[tk]
        chg = a.get("change_pct", 0); price = a.get("price", 0)
        ci, cb = st.columns([5,1])
        with ci:
            st.markdown(f"""<div class="row">
            <span style="font-size:18px;font-weight:700;color:#fff">{tk}</span>
            <span style="font-size:13px;color:#aaa;margin-left:8px">{x.get('company_name','')}</span>
            <span style="font-size:12px;color:#FFD23F;margin-left:8px">listed {x.get('ipo_date','')}</span>
            <span style="font-size:13px;color:#888;margin-left:8px">${price}</span>
            <span style="font-size:12px;color:{'#4ADE80' if chg>=0 else '#F87171'};margin-left:8px">{'+' if chg>=0 else ''}{chg}% today</span>
            </div>""", unsafe_allow_html=True)
        with cb:
            st.write("")
            if st.button("View →", key=f"nls{tk}", use_container_width=True):
                st.session_state.selected = ("stocks", tk)
                st.rerun()


def stocks_page():
    header("stocks")
    if st.session_state.selected and st.session_state.selected[0] == "stocks":
        a = {x["ticker"]: x for x in get_alerts()}.get(st.session_state.selected[1])
        if a: detail(a); return
        st.session_state.selected = None
    if st.session_state.selected and st.session_state.selected[0] == "ipo":
        ipo_detail(st.session_state.selected[1]); return
    tabs = st.tabs(["Short-term","Long-term","Hold","Newly Listed","IPOs"])
    with tabs[0]: tier_list("short","stocks")
    with tabs[1]: tier_list("long","stocks")
    with tabs[2]: tier_list("xlong","stocks")
    with tabs[3]: newly_listed_stocks_list()
    with tabs[4]: ipo_list()


def settings_page():
    header("settings")
    tabs = st.tabs(["Debug","Status"])
    with tabs[0]: tab_activity()
    with tabs[1]: tab_status()


def main():
    page = st.query_params.get("page", "stocks")
    if page == "crypto":     crypto_page()
    elif page == "settings": settings_page()
    elif page == "chart":    chart_page()
    else:                    stocks_page()

if __name__ == "__main__":
    main()
