# ══════════════════════════════════════════════════════════════════════════════
# Growlio — Trading Command Center
# Merged: Original Growlio + Portfolio Risk + TradeFlow + Market Dashboard +
#         Trade Journal + Position Sizer + AI Analyst
# ══════════════════════════════════════════════════════════════════════════════
 
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use("Agg")
from matplotlib.ticker import PercentFormatter
import seaborn as sns
import sqlite3
import feedparser
import requests
import json
import re
import io
import os
import time
from datetime import datetime, date, timedelta
 
# ── Optional imports (won't crash if missing) ─────────────────────────────────
try:
    import anthropic as _anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False
 
try:
    from openai import OpenAI as _OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
 
try:
    import gspread
    from google.oauth2.service_account import Credentials
    HAS_GCP = True
except ImportError:
    HAS_GCP = False
 
# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════
st.set_page_config(page_title="Growlio 📈", layout="wide", page_icon="📈")
 
st.markdown("""
<style>
section[data-testid="stSidebar"] { background-color: #111 !important; }
section[data-testid="stSidebar"] * { color: #e3e3e3 !important; }
.stRadio > div { background-color: #1a1a1a !important; padding: 8px 12px !important; border-radius: 10px !important; }
.stRadio label { color: #e3e3e3 !important; font-weight: 600 !important; }
.metric-card { background:#1a1a1a; border-radius:10px; padding:16px 20px; border:0.5px solid #2a2a2a; }
.metric-card .lbl { font-size:11px; color:#666; text-transform:uppercase; letter-spacing:.06em; margin-bottom:5px; }
.metric-card .val { font-size:22px; font-weight:700; color:#f0f0f0; }
</style>
""", unsafe_allow_html=True)
 
# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 📈 Growlio")
    st.markdown("---")
    page = st.radio("Navigate", [
        "📊 Market Dashboard",
        "🌱 Growlio Analyzer",
        "💼 Portfolio Risk",
        "📈 TradeFlow",
        "📓 Trade Journal",
        "📐 Position Sizer",
        "🧠 AI Analyst",
    ], label_visibility="collapsed")
    st.markdown("---")
    st.markdown("**API Keys**")
    anthropic_key = st.text_input("Anthropic key", type="password", placeholder="sk-ant-...", key="ant_key")
    openai_key = st.text_input("OpenAI key", type="password", placeholder="sk-...", key="oai_key")
    st.markdown("---")
    st.markdown("<p style='font-size:11px;color:#444;'>Growlio · Built by Gildr</p>", unsafe_allow_html=True)
 
page_name = page.split(" ", 1)[1]
 
# ══════════════════════════════════════════════════════════════════════════════
# SHARED HELPERS
# ══════════════════════════════════════════════════════════════════════════════
 
@st.cache_data(ttl=300)
def yf_fast(sym):
    try:
        info = yf.Ticker(sym).fast_info
        return {"price": info.last_price, "prev": info.previous_close}
    except:
        return {"price": None, "prev": None}
 
@st.cache_data(ttl=600)
def yf_history(tickers, start, end):
    try:
        data = yf.download(tickers, start=start, end=end, group_by="ticker", auto_adjust=True, progress=False)
        return data
    except Exception as e:
        st.error(f"Data error: {e}")
        return None
 
@st.cache_data(ttl=600)
def yf_prices(tickers, start, end):
    df = yf.download(tickers, start=start, end=end, auto_adjust=True, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        close = df["Close"].copy()
    else:
        close = df[["Close"]].copy()
        close.columns = [tickers[0]] if isinstance(tickers, list) else [tickers]
    return close.dropna(how="all")
 
def pct_chg(price, prev):
    if price and prev and prev != 0:
        return (price - prev) / prev * 100
    return None
 
def fmt_chg(c):
    if c is None: return "—"
    return f"{'+' if c>=0 else ''}{c:.2f}%"
 
def time_ago(t):
    try:
        diff = datetime.now() - datetime(*t[:6])
        m = int(diff.total_seconds() / 60)
        if m < 60: return f"{m}m ago"
        if m < 1440: return f"{m//60}h ago"
        return f"{m//1440}d ago"
    except: return ""
 
def cat_of(title):
    tl = title.lower()
    if any(w in tl for w in ["fed","rate","inflation","powell","fomc"]): return "🏦 FED"
    if any(w in tl for w in ["earn","profit","revenue","eps","quarter"]): return "📊 EARNINGS"
    if any(w in tl for w in ["nvidia","apple","meta","google","microsoft","ai","tech","chip"]): return "💻 TECH"
    if any(w in tl for w in ["oil","energy","opec"]): return "⚡ ENERGY"
    if any(w in tl for w in ["bitcoin","crypto","eth","btc"]): return "🪙 CRYPTO"
    return "📰 MARKETS"
 
def fetch_rss_news(feeds):
    articles = []
    for url, src in feeds:
        try:
            feed = feedparser.parse(url)
            for e in feed.entries[:5]:
                title = e.get("title", "").strip()
                link = e.get("link", "#")
                pub = e.get("published_parsed")
                desc = re.sub(r"<[^>]+>", "", e.get("summary", ""))[:180].strip()
                if title and len(title) > 15 and not any(a["title"] == title for a in articles):
                    articles.append({"title": title, "link": link, "pub": pub, "desc": desc, "src": src})
        except: pass
    return articles
 
def fetch_news_ticker(ticker):
    try:
        url = f"https://news.google.com/rss/search?q={ticker}+stock&hl=en-US&gl=US&ceid=US:en"
        feed = feedparser.parse(url)
        return [{"title": e.title, "url": e.link, "date": e.get("published", "")} for e in feed.entries[:8]]
    except:
        return []
 
def ann_metrics(returns, rf=0.0):
    mu = returns.mean() * 252
    vol = returns.std() * np.sqrt(252)
    sharpe = (mu - rf) / vol if (isinstance(vol, float) and vol != 0) else (mu - rf) / vol.replace(0, np.nan)
    return mu, vol, sharpe
 
def calc_pnl(t):
    if t["dir"] == "Long":
        return round((t["exit"] - t["entry"]) * t["shares"], 2)
    return round((t["entry"] - t["exit"]) * t["shares"], 2)
 
def calc_r(t):
    if not t.get("stop"): return None
    risk = (t["entry"] - t["stop"]) * t["shares"] if t["dir"] == "Long" else (t["stop"] - t["entry"]) * t["shares"]
    return round(calc_pnl(t) / risk, 2) if risk > 0 else None
 
# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1 — MARKET DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
if page_name == "Market Dashboard":
    st.markdown("# 📊 Market Dashboard")
 
    now = datetime.now()
    h, wd = now.hour, now.weekday()
    if wd >= 5: status, dot = "Weekend — Closed", "🔴"
    elif 9 <= h < 16: status, dot = "Market Open", "🟢"
    elif 4 <= h < 9: status, dot = "Pre-Market", "🟡"
    elif 16 <= h < 20: status, dot = "After-Hours", "🟡"
    else: status, dot = "Market Closed", "🔴"
    st.markdown(f"{dot} **{status}** · {now.strftime('%I:%M %p ET')}")
    st.divider()
 
    # Indices
    st.markdown("### Major Indices")
    idx_map = {"S&P 500": "^GSPC", "NASDAQ": "^IXIC", "DOW": "^DJI", "VIX": "^VIX"}
    cols = st.columns(4)
    for i, (name, sym) in enumerate(idx_map.items()):
        d = yf_fast(sym)
        chg = pct_chg(d["price"], d["prev"])
        with cols[i]:
            st.metric(name, f"{d['price']:,.2f}" if d["price"] else "—", fmt_chg(chg),
                      delta_color="normal" if (chg or 0) >= 0 else "inverse")
    st.divider()
 
    # Watchlist tape
    st.markdown("### Watchlist")
    tape_syms = ["NVDA","AAPL","MSFT","META","GOOGL","AMZN","TSLA","PLTR","AMD","TSM","AVGO","ORCL"]
    wcols = st.columns(len(tape_syms))
    for i, sym in enumerate(tape_syms):
        d = yf_fast(sym)
        chg = pct_chg(d["price"], d["prev"])
        with wcols[i]:
            icon = "🟢" if (chg or 0) >= 0 else "🔴"
            st.markdown(f"**{sym}**  \n${d['price']:.2f}" if d["price"] else f"**{sym}**  \n—")
            st.markdown(f"{icon} {fmt_chg(chg)}")
    st.divider()
 
    col_l, col_r = st.columns(2)
 
    # Movers
    with col_l:
        st.markdown("### Top Movers")
        mover_syms = ["NVDA","META","AAPL","MSFT","AMZN","GOOGL","TSLA","PLTR","AMD","NFLX","AVGO","ORCL","TSM","INTC"]
        mdata = []
        for sym in mover_syms:
            d = yf_fast(sym)
            chg = pct_chg(d["price"], d["prev"])
            if d["price"] and chg is not None:
                mdata.append({"Symbol": sym, "Price": f"${d['price']:.2f}", "Change": f"{chg:+.2f}%", "_c": chg})
        mdata.sort(key=lambda x: x["_c"], reverse=True)
        tg, tl = st.tabs(["▲ Gainers", "▼ Losers"])
        clean = lambda lst: pd.DataFrame([{k:v for k,v in d.items() if k!="_c"} for d in lst])
        with tg: st.dataframe(clean(mdata[:5]), hide_index=True, use_container_width=True)
        with tl: st.dataframe(clean(mdata[-5:][::-1]), hide_index=True, use_container_width=True)
 
    # Sectors
    with col_r:
        st.markdown("### Sectors")
        sec_map = {"Technology":"XLK","Financials":"XLF","Healthcare":"XLV","Energy":"XLE",
                   "Consumer":"XLY","Industrials":"XLI","Utilities":"XLU","Real Estate":"XLRE"}
        for name, sym in sec_map.items():
            d = yf_fast(sym)
            chg = pct_chg(d["price"], d["prev"])
            icon = "🟢" if (chg or 0) >= 0 else "🔴"
            st.markdown(f"{icon} **{name}** — {fmt_chg(chg)}")
 
    st.divider()
    col_fg, col_crypto = st.columns(2)
 
    # Fear & Greed
    with col_fg:
        st.markdown("### Fear & Greed Index")
        try:
            r = requests.get("https://production.dataviz.cnn.io/index/fearandgreed/graphdata", timeout=5)
            d = r.json()
            score = round(d["fear_and_greed"]["score"])
            rating = d["fear_and_greed"]["rating"].replace("_", " ").title()
            col = "🔴" if score < 30 else "🟡" if score < 50 else "🟢" if score > 70 else "⚪"
            st.metric("CNN Fear & Greed", f"{score} / 100", rating)
            st.progress(score / 100)
            st.markdown(f"{col} **{rating}**")
        except:
            st.info("Fear & Greed data unavailable")
 
    # Crypto
    with col_crypto:
        st.markdown("### Crypto")
        for name, sym in {"Bitcoin":"BTC-USD","Ethereum":"ETH-USD","Solana":"SOL-USD"}.items():
            d = yf_fast(sym)
            chg = pct_chg(d["price"], d["prev"])
            st.metric(name, f"${d['price']:,.2f}" if d["price"] else "—", fmt_chg(chg),
                      delta_color="normal" if (chg or 0) >= 0 else "inverse")
 
    st.divider()
 
    # News
    st.markdown("### Market News")
    articles = fetch_rss_news([
        ("https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC&region=US&lang=en-US", "Yahoo Finance"),
        ("https://feeds.marketwatch.com/marketwatch/topstories/", "MarketWatch"),
        ("https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114", "CNBC"),
    ])
    if not articles:
        articles = [
            {"title":"S&P 500 climbs as tech sector leads broad market rally","src":"MarketWatch","pub":None,"link":"#","desc":"Technology shares drove gains as investors rotated into growth names."},
            {"title":"Federal Reserve holds rates steady, signals patience","src":"Yahoo Finance","pub":None,"link":"#","desc":"Fed voted to maintain benchmark rates amid ongoing inflation uncertainty."},
            {"title":"NVIDIA surges on record data center revenue beat","src":"CNBC","pub":None,"link":"#","desc":"Quarterly data center revenue surpassed Wall Street estimates on AI demand."},
            {"title":"Treasury yields edge lower as bond market stabilizes","src":"MarketWatch","pub":None,"link":"#","desc":"US bond yields retreated after a volatile week, offering relief to tech valuations."},
            {"title":"Oil falls on rising US crude inventory build","src":"Yahoo Finance","pub":None,"link":"#","desc":"Crude prices declined after inventory data showed a larger-than-expected build."},
        ]
    for a in articles[:8]:
        c1, c2 = st.columns([7, 1])
        with c1:
            st.markdown(f"**{a['title']}**")
            if a.get("desc"):
                st.markdown(f"<span style='color:#888;font-size:12px'>{a['desc']}</span>", unsafe_allow_html=True)
            ta = time_ago(a["pub"]) if a.get("pub") else ""
            st.markdown(f"<span style='color:#555;font-size:11px'>{a['src']}{' · '+ta if ta else ''} · {cat_of(a['title'])}</span>", unsafe_allow_html=True)
        with c2:
            if a.get("link","#") != "#":
                st.link_button("Read →", a["link"])
        st.divider()
 
# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2 — GROWLIO ANALYZER (original)
# ══════════════════════════════════════════════════════════════════════════════
elif page_name == "Growlio Analyzer":
    st.title("🌱 Growlio — Investment Analyzer")
 
    st.sidebar.header("Stock Settings")
    tickers_input = st.sidebar.text_input("Tickers (comma separated)", "AAPL, MSFT, TSLA", key="ga_tickers")
    start_ga = st.sidebar.date_input("Start Date", date(2023, 1, 1), key="ga_start")
    end_ga = st.sidebar.date_input("End Date", date.today(), key="ga_end")
    sheet_key = st.sidebar.text_input("Google Sheet ID (optional)", "", key="ga_sheet")
    tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]
 
    data = yf_history(tickers, start_ga, end_ga)
    if data is None or data.empty:
        st.warning("No data found for these tickers.")
        st.stop()
 
    # Metrics
    st.subheader("📈 Stock Metrics")
    cols = st.columns(len(tickers))
    for i, ticker in enumerate(tickers):
        try:
            last = data[ticker]["Close"].iloc[-1]
            first = data[ticker]["Close"].iloc[0]
            chg = (last - first) / first * 100
            cols[i].metric(ticker, f"${float(last):.2f}", f"{float(chg):.2f}%")
        except:
            cols[i].warning(f"No data for {ticker}")
 
    # Comparison chart
    st.subheader("📉 Stock Price Comparison")
    fig = go.Figure()
    for ticker in tickers:
        try:
            fig.add_trace(go.Scatter(x=data[ticker].index, y=data[ticker]["Close"], mode="lines", name=ticker))
        except: pass
    fig.update_layout(title="Stock Prices", xaxis_title="Date", yaxis_title="Price (USD)",
                      plot_bgcolor="#0d0d0d", paper_bgcolor="#0d0d0d", font_color="#f0f0f0")
    st.plotly_chart(fig, use_container_width=True)
 
    # Per-stock detail
    st.subheader("🔍 Detailed Analysis")
    if st.button("🔄 Refresh News for All Tickers"):
        st.info("Fetching latest news...")
 
    for ticker in tickers:
        st.markdown(f"## {ticker}")
        try:
            df = data[ticker].copy()
            df["50MA"] = df["Close"].rolling(50).mean()
            df["200MA"] = df["Close"].rolling(200).mean()
            df["Volatility"] = df["Close"].rolling(20).std()
            df["Signal"] = (df["50MA"] > df["200MA"]) & (df["50MA"].shift(1) <= df["200MA"].shift(1))
            buy_signals = df[df["Signal"]]
 
            fig2 = go.Figure(data=[go.Candlestick(
                x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"], name="Candles")])
            fig2.add_trace(go.Scatter(x=df.index, y=df["50MA"], mode="lines", name="50MA", line=dict(color="#60a5fa")))
            fig2.add_trace(go.Scatter(x=df.index, y=df["200MA"], mode="lines", name="200MA", line=dict(color="#fbbf24")))
            fig2.add_trace(go.Scatter(x=buy_signals.index, y=buy_signals["Close"], mode="markers",
                marker=dict(symbol="triangle-up", color="#4ade80", size=10), name="Buy Signal"))
            fig2.update_layout(title=f"{ticker} — Price, MAs & Buy Signals",
                               plot_bgcolor="#0d0d0d", paper_bgcolor="#0d0d0d", font_color="#f0f0f0")
            st.plotly_chart(fig2, use_container_width=True)
 
            vol_fig = go.Figure()
            vol_fig.add_trace(go.Scatter(x=df.index, y=df["Volatility"], mode="lines", line=dict(color="#f87171")))
            vol_fig.update_layout(title=f"{ticker} 20-Day Rolling Volatility",
                                  plot_bgcolor="#0d0d0d", paper_bgcolor="#0d0d0d", font_color="#f0f0f0")
            st.plotly_chart(vol_fig, use_container_width=True)
 
            # News
            st.subheader(f"📰 {ticker} News")
            articles = fetch_news_ticker(ticker)
            if not articles:
                st.info("No news found.")
            else:
                headlines = []
                for a in articles:
                    st.markdown(f"- [{a['title']}]({a['url']}) — {a['date'][:16] if a['date'] else ''}")
                    headlines.append(a["title"])
 
                # AI Summary
                st.subheader(f"🤖 Why Did {ticker} Move?")
                if openai_key and HAS_OPENAI:
                    oai = _OpenAI(api_key=openai_key)
                    combined = " | ".join(headlines[:8])
                    try:
                        resp = oai.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[
                                {"role":"system","content":"You are a financial analyst who explains simply."},
                                {"role":"user","content":f"Summarize in plain English why {ticker} might have moved today based on these headlines: {combined}. Under 2 sentences. Finish with a one-sentence 'Lesson:'."}
                            ], temperature=0.7
                        )
                        st.info(resp.choices[0].message.content.strip())
                    except Exception as e:
                        st.warning(f"OpenAI error: {e}")
                else:
                    st.info("Add your OpenAI key in the sidebar for AI summaries.")
        except Exception as e:
            st.warning(f"Could not process {ticker}: {e}")
 
# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3 — PORTFOLIO RISK (original)
# ══════════════════════════════════════════════════════════════════════════════
elif page_name == "Portfolio Risk":
    st.title("💼 Portfolio Risk Dashboard")
    st.caption("Sharpe, beta, diversification metrics, efficient frontier")
 
    def clean_weights(raw_tickers, raw_weights):
        tks = [t.strip().upper() for t in raw_tickers.split(",") if t.strip()]
        wts = np.array([float(w.strip()) for w in raw_weights.split(",") if w.strip()])
        if len(tks) != len(wts): raise ValueError("Tickers and weights must match in count.")
        if (wts < 0).any(): raise ValueError("Weights must be non-negative.")
        if wts.sum() == 0: raise ValueError("Weights sum to 0.")
        return tks, wts / wts.sum()
 
    def portfolio_series(prices, weights):
        norm = prices / prices.iloc[0]
        return (norm * weights).sum(axis=1)
 
    def beta_vs_benchmark(asset_rets, bench_rets):
        var_b = bench_rets.var()
        if var_b == 0: return pd.Series({c: np.nan for c in asset_rets.columns})
        return pd.Series({c: np.cov(asset_rets[c].dropna(), bench_rets.dropna())[0,1] / var_b for c in asset_rets.columns})
 
    def risk_contributions(weights, cov):
        w = np.asarray(weights).reshape(-1,1)
        port_var = float(w.T @ cov.values @ w)
        if port_var <= 0: return np.zeros(len(weights)), np.zeros(len(weights)), 0
        mcr = (cov.values @ w).flatten() / np.sqrt(port_var)
        pcr = (w.flatten() * (cov.values @ w).flatten()) / port_var
        return mcr, pcr, np.sqrt(port_var)
 
    def diversification_stats(weights, corr):
        hhi = float(np.sum(np.square(weights)))
        C = corr.replace([np.inf,-np.inf], np.nan).fillna(0).values
        n = C.shape[0]
        avg_corr = float(np.mean(C[np.triu_indices(n,1)])) if n > 1 else np.nan
        return hhi, 1 - hhi, avg_corr
 
    def random_frontier(returns, n_port=3000, rf=0.0):
        mu, Sigma = returns.mean().values*252, returns.cov().values*252
        n = len(mu)
        rr, vv, sh = [], [], []
        for _ in range(n_port):
            w = np.random.rand(n); w /= w.sum()
            mp = float(w@mu); vp = float(np.sqrt(w@Sigma@w))
            rr.append(mp); vv.append(vp); sh.append((mp-rf)/vp if vp!=0 else np.nan)
        return pd.DataFrame({"Return":rr,"Volatility":vv,"Sharpe":sh})
 
    def template_excel():
        buf = io.BytesIO()
        pd.DataFrame({"Ticker":["AAPL","MSFT","TSLA"],"Weight":[0.4,0.4,0.2]}).to_excel(buf, index=False, sheet_name="weights", engine="xlsxwriter")
        buf.seek(0); return buf
 
    st.sidebar.header("Portfolio Inputs")
    mode = st.sidebar.radio("Input Method", ["Manual","Upload Excel"], key="pr_mode")
    start_pr = st.sidebar.date_input("Start Date", date(2022,1,1), key="pr_start")
    end_pr = st.sidebar.date_input("End Date", date.today(), key="pr_end")
    rf_pct = st.sidebar.number_input("Risk-free rate (%)", 0.0, 10.0, 0.0, 0.1, key="pr_rf")
    rf = rf_pct / 100
    benchmark = st.sidebar.text_input("Benchmark", "^GSPC", key="pr_bench")
 
    if mode == "Manual":
        tr_raw = st.sidebar.text_input("Tickers", "AAPL, MSFT, TSLA", key="pr_tr")
        wt_raw = st.sidebar.text_input("Weights", "0.4, 0.4, 0.2", key="pr_wt")
        try: tickers, weights = clean_weights(tr_raw, wt_raw)
        except Exception as e: st.error(f"Weight error: {e}"); st.stop()
    else:
        uploaded = st.sidebar.file_uploader("Upload Excel", type=["xlsx"], key="pr_up")
        st.sidebar.download_button("Download template", template_excel(), "template.xlsx")
        if not uploaded: st.info("Upload an Excel file or switch to Manual."); st.stop()
        try:
            wdf = pd.read_excel(uploaded, sheet_name="weights")
            tickers = [str(t).upper().strip() for t in wdf["Ticker"].tolist()]
            weights = np.array(wdf["Weight"].astype(float).tolist())
            weights /= weights.sum()
        except Exception as e: st.error(f"Excel error: {e}"); st.stop()
 
    prices = yf_prices(tickers, start_pr, end_pr)
    if prices.empty: st.warning("No price data."); st.stop()
 
    try:
        bench_px = yf_prices([benchmark], start_pr, end_pr).iloc[:,0]
        bench_rets = bench_px.pct_change().dropna()
    except: bench_rets = None
 
    rets = prices.pct_change().dropna()
    port = portfolio_series(prices, weights)
    port_rets = port.pct_change().dropna()
    p_mu, p_vol, p_sharpe = ann_metrics(port_rets, rf)
 
    # KPIs
    cA,cB,cC,cD = st.columns(4)
    cA.metric("Annual Return", f"{float(p_mu)*100:.2f}%")
    cB.metric("Annual Volatility", f"{float(p_vol)*100:.2f}%")
    cC.metric("Sharpe Ratio", f"{float(p_sharpe):.2f}")
    cD.metric("Holdings", str(len(tickers)))
 
    # Charts
    st.subheader("📈 Portfolio Value & Rolling Volatility")
    c1, c2 = st.columns(2)
    with c1:
        fig, ax = plt.subplots(figsize=(6,4))
        ax.plot(port.index, port.values, color="#60a5fa")
        ax.set_facecolor("#0d0d0d"); fig.patch.set_facecolor("#0d0d0d")
        ax.tick_params(colors="#888"); ax.set_title("Portfolio Value (Start=1.0)", color="#f0f0f0")
        ax.grid(True, alpha=0.2)
        st.pyplot(fig, use_container_width=True)
    with c2:
        roll = port_rets.rolling(21).std() * np.sqrt(252)
        fig2, ax2 = plt.subplots(figsize=(6,4))
        ax2.plot(roll.index, roll.values, color="#f87171")
        ax2.set_facecolor("#0d0d0d"); fig2.patch.set_facecolor("#0d0d0d")
        ax2.tick_params(colors="#888"); ax2.set_title("Rolling 1M Volatility", color="#f0f0f0")
        ax2.yaxis.set_major_formatter(PercentFormatter(1.0)); ax2.grid(True, alpha=0.2)
        st.pyplot(fig2, use_container_width=True)
 
    # Asset metrics
    st.subheader("📊 Asset Metrics")
    a_mu, a_vol, a_sh = ann_metrics(rets, rf)
    mdf = pd.DataFrame({"Ann Return": a_mu, "Ann Volatility": a_vol, "Sharpe": a_sh})
    if bench_rets is not None:
        mdf[f"Beta vs {benchmark}"] = beta_vs_benchmark(rets, bench_rets)
    st.dataframe(mdf.style.format({c: ("{:.2%}" if "Ann" in c else "{:.2f}") for c in mdf.columns}), use_container_width=True)
 
    # Risk contributions
    st.subheader("🧩 Risk Decomposition")
    cov = rets.cov() * 252
    corr = rets.corr()
    mcr, pcr, pv = risk_contributions(weights, cov)
    hhi, div, avg_c = diversification_stats(weights, corr)
    r1,r2,r3 = st.columns(3)
    r1.metric("Portfolio Volatility", f"{pv*100:.2f}%")
    r2.metric("Diversification Score", f"{div:.3f}")
    r3.metric("Avg Pairwise Corr", f"{avg_c:.2f}" if not np.isnan(avg_c) else "—")
 
    fig3, ax3 = plt.subplots(figsize=(7,4))
    ax3.bar(tickers, pcr*100, color="#60a5fa")
    ax3.set_facecolor("#0d0d0d"); fig3.patch.set_facecolor("#0d0d0d")
    ax3.tick_params(colors="#888"); ax3.set_title("% Contribution to Risk", color="#f0f0f0")
    ax3.yaxis.set_major_formatter(PercentFormatter(100)); ax3.grid(True, axis="y", alpha=0.2)
    st.pyplot(fig3, use_container_width=True)
 
    fig4, ax4 = plt.subplots(figsize=(6,5))
    im = ax4.imshow(corr.values, cmap="coolwarm", vmin=-1, vmax=1)
    ax4.set_xticks(range(len(tickers))); ax4.set_xticklabels(tickers, rotation=45, ha="right", color="#888")
    ax4.set_yticks(range(len(tickers))); ax4.set_yticklabels(tickers, color="#888")
    ax4.set_facecolor("#0d0d0d"); fig4.patch.set_facecolor("#0d0d0d")
    ax4.set_title("Correlation Heatmap", color="#f0f0f0")
    plt.colorbar(im, ax=ax4, fraction=0.046, pad=0.04)
    st.pyplot(fig4, use_container_width=True)
 
    # Efficient frontier
    st.subheader("🌈 Efficient Frontier")
    n_sims = st.slider("Random portfolios", 1000, 10000, 3000, 1000)
    frontier = random_frontier(rets, n_sims, rf)
    fig5, ax5 = plt.subplots(figsize=(7,5))
    sc = ax5.scatter(frontier["Volatility"], frontier["Return"], c=frontier["Sharpe"], cmap="viridis", s=8, alpha=0.4)
    ax5.scatter([float(p_vol)], [float(p_mu)], c="red", s=100, label="Your Portfolio", zorder=5)
    ax5.set_facecolor("#0d0d0d"); fig5.patch.set_facecolor("#0d0d0d")
    ax5.tick_params(colors="#888"); ax5.set_title("Risk/Return Cloud", color="#f0f0f0")
    ax5.set_xlabel("Volatility", color="#888"); ax5.set_ylabel("Return", color="#888")
    ax5.grid(True, alpha=0.2); ax5.legend(labelcolor="#f0f0f0", facecolor="#1a1a1a")
    plt.colorbar(sc, ax=ax5, label="Sharpe")
    st.pyplot(fig5, use_container_width=True)
 
    st.subheader("⬇️ Export")
    st.download_button("Download Asset Metrics (CSV)", mdf.to_csv().encode(), "asset_metrics.csv", "text/csv")
    st.download_button("Download Prices (CSV)", prices.to_csv().encode(), "prices.csv", "text/csv")
 
    with st.expander("📝 Resume notes"):
        st.markdown("- Modeled Sharpe ratio, beta, and diversification (HHI, correlations, risk contributions)\n- Visualized efficient frontier via Monte Carlo simulation\n- Built with Python, Matplotlib, and Streamlit")
 
# ══════════════════════════════════════════════════════════════════════════════
# PAGE 4 — TRADEFLOW (original)
# ══════════════════════════════════════════════════════════════════════════════
elif page_name == "TradeFlow":
    st.title("📈 TradeFlow Analyzer")
    st.markdown("Synthetic trade data with SQL + anomaly detection")
 
    np.random.seed(42)
    n = 5000
    timestamps = [datetime.now() - timedelta(minutes=i) for i in range(n)]
    prices_tf = np.random.normal(100, 2, n).round(2)
    volumes_tf = np.random.randint(10, 1000, n)
    df_tf = pd.DataFrame({"trade_id": range(1, n+1), "timestamp": timestamps, "price": prices_tf, "volume": volumes_tf})
 
    if st.checkbox("Show sample trades"):
        st.dataframe(df_tf.head(20))
 
    st.subheader("Run SQL on Trades")
    query = st.text_area("SQL query:", "SELECT AVG(price) as avg_price, SUM(volume) as total_volume FROM trades", height=100)
    if st.button("▶ Run Query"):
        try:
            conn = sqlite3.connect(":memory:")
            df_tf.to_sql("trades", conn, index=False, if_exists="replace")
            result = pd.read_sql_query(query, conn)
            st.dataframe(result)
            conn.close()
        except Exception as e:
            st.error(f"SQL error: {e}")
 
    st.subheader("Liquidity Patterns")
    df_tf["minute"] = pd.to_datetime(df_tf["timestamp"]).dt.floor("min")
    liq = df_tf.groupby("minute")["volume"].sum().reset_index()
    fig_liq = go.Figure()
    fig_liq.add_trace(go.Scatter(x=liq["minute"], y=liq["volume"], mode="lines", line=dict(color="#60a5fa")))
    fig_liq.update_layout(title="Volume per Minute", plot_bgcolor="#0d0d0d", paper_bgcolor="#0d0d0d", font_color="#f0f0f0")
    st.plotly_chart(fig_liq, use_container_width=True)
 
    st.subheader("Anomaly Detection (3σ Rule)")
    pm, ps = df_tf["price"].mean(), df_tf["price"].std()
    outliers = df_tf[(df_tf["price"] > pm + 3*ps) | (df_tf["price"] < pm - 3*ps)]
    if not outliers.empty:
        st.warning(f"Detected {len(outliers)} abnormal trades")
        st.dataframe(outliers.head(10))
    else:
        st.success("No price anomalies detected.")
 
    st.subheader("Price vs Volume")
    fig_pv = px.scatter(df_tf.sample(500), x="price", y="volume", opacity=0.4,
                        color_discrete_sequence=["#60a5fa"])
    fig_pv.update_layout(plot_bgcolor="#0d0d0d", paper_bgcolor="#0d0d0d", font_color="#f0f0f0")
    st.plotly_chart(fig_pv, use_container_width=True)
 
    # Volume distribution
    st.subheader("Volume Distribution")
    fig_vd = px.histogram(df_tf, x="volume", nbins=50, color_discrete_sequence=["#4ade80"])
    fig_vd.update_layout(plot_bgcolor="#0d0d0d", paper_bgcolor="#0d0d0d", font_color="#f0f0f0")
    st.plotly_chart(fig_vd, use_container_width=True)
 
    # Price OHLC simulation
    st.subheader("Simulated OHLC — First 100 Trades")
    sim = df_tf.head(100).copy()
    sim["open"] = sim["price"].shift(1).fillna(sim["price"])
    sim["high"] = sim[["price","open"]].max(axis=1) + np.random.uniform(0,0.5,100)
    sim["low"] = sim[["price","open"]].min(axis=1) - np.random.uniform(0,0.5,100)
    fig_ohlc = go.Figure(data=[go.Candlestick(
        x=sim["trade_id"], open=sim["open"], high=sim["high"], low=sim["low"], close=sim["price"])])
    fig_ohlc.update_layout(title="Simulated OHLC", plot_bgcolor="#0d0d0d", paper_bgcolor="#0d0d0d", font_color="#f0f0f0", xaxis_rangeslider_visible=False)
    st.plotly_chart(fig_ohlc, use_container_width=True)
 
# ══════════════════════════════════════════════════════════════════════════════
# PAGE 5 — TRADE JOURNAL
# ══════════════════════════════════════════════════════════════════════════════
elif page_name == "Trade Journal":
    st.markdown("# 📓 Trade Journal")
 
    if "trades" not in st.session_state:
        st.session_state.trades = []
    trades = st.session_state.trades
 
    if trades:
        pnls = [calc_pnl(t) for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        total_pnl = round(sum(pnls), 2)
        win_rate = round(len(wins)/len(pnls)*100) if pnls else 0
        avg_win = round(sum(wins)/len(wins)) if wins else 0
        avg_loss = round(sum(losses)/len(losses)) if losses else 0
        expectancy = round((win_rate/100)*avg_win + (1-win_rate/100)*avg_loss)
        gw = sum(wins); gl = abs(sum(losses))
        pf = round(gw/gl, 2) if gl > 0 else None
        rs = [calc_r(t) for t in trades if calc_r(t) is not None]
        avg_r = round(sum(rs)/len(rs), 2) if rs else None
        c1,c2,c3,c4,c5,c6 = st.columns(6)
        c1.metric("Total P&L", f"${total_pnl:+,.0f}")
        c2.metric("Win Rate", f"{win_rate}%")
        c3.metric("Trades", len(trades))
        c4.metric("Expectancy", f"${expectancy:+,.0f}")
        if pf: c5.metric("Profit Factor", pf)
        if avg_r: c6.metric("Avg R", f"{avg_r:+.2f}R")
        st.divider()
 
    tab1, tab2, tab3 = st.tabs(["➕ Log Trade", "📋 History", "📊 Analytics"])
 
    with tab1:
        with st.form("trade_form"):
            c1,c2,c3,c4 = st.columns(4)
            ticker = c1.text_input("Ticker", placeholder="AAPL").upper().strip()
            direction = c2.selectbox("Direction", ["Long","Short"])
            trade_date = c3.date_input("Date", value=date.today())
            setup = c4.text_input("Setup", placeholder="Breakout, VWAP...")
            c1,c2,c3,c4 = st.columns(4)
            entry = c1.number_input("Entry ($)", min_value=0.0, step=0.01, format="%.2f")
            exit_p = c2.number_input("Exit ($)", min_value=0.0, step=0.01, format="%.2f")
            shares = c3.number_input("Shares", min_value=1, step=1)
            stop = c4.number_input("Stop ($) optional", min_value=0.0, step=0.01, format="%.2f")
            notes = st.text_area("Notes", placeholder="Why you took the trade, what happened...")
            if st.form_submit_button("✚ Log Trade", use_container_width=True):
                if not ticker or entry == 0 or exit_p == 0:
                    st.error("Fill in ticker, entry, and exit price.")
                else:
                    t = {"id":int(time.time()*1000),"ticker":ticker,"dir":direction,"date":str(trade_date),
                         "entry":entry,"exit":exit_p,"shares":int(shares),"stop":stop if stop>0 else None,"setup":setup,"notes":notes}
                    st.session_state.trades.append(t)
                    st.success(f"Logged — P&L: ${calc_pnl(t):+,.2f}")
                    st.rerun()
 
    with tab2:
        if not trades:
            st.info("No trades yet.")
        else:
            fc1,fc2,fc3 = st.columns(3)
            fdir = fc1.selectbox("Direction", ["All","Long","Short"])
            fres = fc2.selectbox("Result", ["All","Wins","Losses"])
            ftick = fc3.text_input("Ticker search")
            f = [t for t in trades if
                 (fdir=="All" or t["dir"]==fdir) and
                 (fres=="All" or (fres=="Wins" and calc_pnl(t)>0) or (fres=="Losses" and calc_pnl(t)<0)) and
                 (not ftick or ftick.upper() in t["ticker"])]
            f.sort(key=lambda x: x["date"], reverse=True)
            rows = [{"Ticker":t["ticker"],"Dir":t["dir"],"Date":t["date"],"Entry":f"${t['entry']:.2f}",
                     "Exit":f"${t['exit']:.2f}","Shares":t["shares"],"P&L":f"${calc_pnl(t):+,.2f}",
                     "R": f"{calc_r(t):+.2f}R" if calc_r(t) else "—","Setup":t.get("setup","—")} for t in f]
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
            if st.button("🗑 Clear all trades"):
                st.session_state.trades = []
                st.rerun()
 
    with tab3:
        if not trades:
            st.info("Log some trades to see analytics.")
        else:
            s = sorted(trades, key=lambda x: x["date"])
            pnls = [calc_pnl(t) for t in s]
            labels = [f"{t['ticker']} {t['date'][5:]}" for t in s]
            running = []; total = 0
            for p in pnls: total += p; running.append(round(total,2))
 
            fig1 = go.Figure()
            fig1.add_trace(go.Scatter(x=labels, y=running, mode="lines+markers",
                line=dict(color="#60a5fa",width=2), fill="tozeroy", fillcolor="rgba(96,165,250,0.07)"))
            fig1.update_layout(title="Equity Curve", plot_bgcolor="#0d0d0d", paper_bgcolor="#0d0d0d",
                font_color="#f0f0f0", height=280, xaxis=dict(showgrid=False,tickangle=-45), yaxis=dict(gridcolor="#282828"))
            st.plotly_chart(fig1, use_container_width=True)
 
            fig2 = go.Figure()
            fig2.add_trace(go.Bar(x=labels, y=pnls, marker_color=["#4ade80" if p>=0 else "#f87171" for p in pnls]))
            fig2.update_layout(title="P&L per Trade", plot_bgcolor="#0d0d0d", paper_bgcolor="#0d0d0d",
                font_color="#f0f0f0", height=220, xaxis=dict(showgrid=False,tickangle=-45), yaxis=dict(gridcolor="#282828"))
            st.plotly_chart(fig2, use_container_width=True)
 
            ic1, ic2 = st.columns(2)
            with ic1:
                st.markdown("**P&L by Setup**")
                bs = {}
                for t in trades:
                    k = t.get("setup") or "Untagged"
                    if k not in bs: bs[k] = {"pnl":0,"wins":0,"total":0}
                    p = calc_pnl(t); bs[k]["pnl"] = round(bs[k]["pnl"]+p,2); bs[k]["total"] += 1
                    if p > 0: bs[k]["wins"] += 1
                st.dataframe(pd.DataFrame([{"Setup":k,"P&L":f"${v['pnl']:+,.0f}","Win%":f"{round(v['wins']/v['total']*100)}%"}
                    for k,v in sorted(bs.items(),key=lambda x:-x[1]["pnl"])]), hide_index=True, use_container_width=True)
            with ic2:
                st.markdown("**P&L by Day of Week**")
                bd = {}
                for t in trades:
                    try:
                        d = pd.Timestamp(t["date"]).day_name()[:3]
                        bd[d] = round(bd.get(d,0)+calc_pnl(t),2)
                    except: pass
                st.dataframe(pd.DataFrame([{"Day":k,"P&L":f"${v:+,.0f}"} for k,v in sorted(bd.items(),key=lambda x:-x[1])]),
                    hide_index=True, use_container_width=True)
 
            st.divider()
            csv = pd.DataFrame([{**t,"pnl":calc_pnl(t),"r":calc_r(t)} for t in trades]).to_csv(index=False)
            st.download_button("⬇ Download CSV", csv, "growlio_trades.csv", "text/csv")
 
# ══════════════════════════════════════════════════════════════════════════════
# PAGE 6 — POSITION SIZER
# ══════════════════════════════════════════════════════════════════════════════
elif page_name == "Position Sizer":
    st.markdown("# 📐 Position Sizer")
    st.markdown("Calculate your exact share count and risk before you enter.")
    st.divider()
 
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### Parameters")
        account = st.number_input("Account size ($)", min_value=100.0, value=25000.0, step=500.0)
        risk_pct = st.slider("Risk per trade (%)", min_value=0.1, max_value=5.0, value=1.0, step=0.1)
        direction = st.selectbox("Direction", ["Long","Short"])
        cc1, cc2 = st.columns(2)
        entry = cc1.number_input("Entry price ($)", min_value=0.01, value=150.0, step=0.01)
        stop = cc2.number_input("Stop price ($)", min_value=0.01, value=145.0, step=0.01)
        target = st.number_input("Target price ($) — optional", min_value=0.0, value=0.0, step=0.01)
 
        st.markdown("---")
        auto_ticker = st.text_input("Auto-fill entry from ticker (optional)", placeholder="NVDA").upper()
        if auto_ticker and st.button("Fetch live price"):
            d = yf_fast(auto_ticker)
            if d["price"]:
                st.success(f"{auto_ticker}: ${d['price']:.2f}")
            else:
                st.error("Could not fetch price.")
 
    with c2:
        st.markdown("### Result")
        rps = abs(entry - stop)
        if rps > 0:
            risk_dollar = round(account * risk_pct / 100, 2)
            shares = int(risk_dollar / rps)
            pos_size = round(shares * entry, 2)
            pct_acc = round(pos_size / account * 100, 1)
 
            m1,m2 = st.columns(2)
            m1.metric("Shares", f"{shares:,}")
            m2.metric("Position size", f"${pos_size:,.2f}")
            m3,m4 = st.columns(2)
            m3.metric("$ at risk", f"-${risk_dollar:,.2f}")
            m4.metric("% of account", f"{pct_acc}%")
            m5,m6 = st.columns(2)
            m5.metric("Risk per share", f"${rps:.2f}")
 
            if target > 0:
                reward = abs(target - entry)
                rr = round(reward / rps, 2)
                profit = round(shares * reward, 2)
                m6.metric("R:R ratio", f"1 : {rr}")
                st.success(f"If target hit: **+${profit:,.2f}** profit")
                if rr < 1.5: st.warning("R:R below 1.5 — consider skipping this trade.")
                elif rr >= 3: st.success("Strong R:R — great risk/reward setup.")
 
            st.divider()
            if pct_acc > 10: st.error(f"⚠️ {pct_acc}% of account — this is high. Reduce shares.")
            elif pct_acc > 5: st.warning(f"{pct_acc}% of account — moderate risk.")
            else: st.success(f"✅ {pct_acc}% of account — well sized.")
            if risk_pct > 2: st.warning(f"Risking {risk_pct}% per trade is aggressive. Most pros risk 0.5–1%.")
        else:
            st.error("Entry and stop prices must be different.")
 
    st.divider()
    st.markdown("""
### 📚 Position sizing rules
- **1% rule** — never risk more than 1% of your account on a single trade
- **2% max** — absolute ceiling for most retail traders
- **R:R minimum** — aim for at least 1.5:1 before entering
- **Concentration** — no single position over 10% of account
- **Consecutive losses** — after 3 losses in a row, cut size in half
""")
 
# ══════════════════════════════════════════════════════════════════════════════
# PAGE 7 — AI ANALYST
# ══════════════════════════════════════════════════════════════════════════════
elif page_name == "AI Analyst":
    st.markdown("# 🧠 AI Stock Analyst")
    st.markdown("Enter any ticker and get a full investment thesis — bull case, bear case, price target.")
    st.divider()
 
    c1, c2 = st.columns([2,2])
    ticker = c1.text_input("Ticker", placeholder="NVDA").upper().strip()
    horizon = c2.selectbox("Horizon", ["Long-term (3–5 years)","Medium-term (1–2 years)","Short-term (3–6 months)"])
    quick = st.pills("Quick picks", ["NVDA","AAPL","META","MSFT","GOOGL","AMZN","PLTR","AMD","TSLA","TSM","AVGO","ORCL"])
    if quick: ticker = quick
 
    if st.button("✦ Analyze", use_container_width=True, type="primary"):
        if not ticker:
            st.error("Enter a ticker.")
        elif not anthropic_key:
            st.error("Enter your Anthropic API key in the sidebar.")
        elif not HAS_ANTHROPIC:
            st.error("Install the anthropic package: pip install anthropic")
        else:
            # Get live data context
            price_ctx = ""
            try:
                info = yf.Ticker(ticker).info
                price_ctx = (
                    f"Price: ${info.get('currentPrice', info.get('regularMarketPrice','N/A'))} | "
                    f"52w High: ${info.get('fiftyTwoWeekHigh','N/A')} | "
                    f"52w Low: ${info.get('fiftyTwoWeekLow','N/A')} | "
                    f"Market cap: ${info.get('marketCap',0)/1e9:.1f}B | "
                    f"P/E: {info.get('trailingPE','N/A')} | "
                    f"Fwd P/E: {info.get('forwardPE','N/A')} | "
                    f"Revenue growth: {info.get('revenueGrowth',0)*100:.1f}% | "
                    f"Gross margin: {info.get('grossMargins',0)*100:.1f}% | "
                    f"Analyst target: ${info.get('targetMeanPrice','N/A')} | "
                    f"Recommendation: {info.get('recommendationKey','N/A')}"
                )
            except: pass
 
            # Recent news context
            news_ctx = ""
            try:
                articles = fetch_news_ticker(ticker)
                if articles:
                    news_ctx = "Recent headlines: " + " | ".join([a["title"] for a in articles[:5]])
            except: pass
 
            with st.spinner(f"Analyzing {ticker}..."):
                try:
                    client = _anthropic.Anthropic(api_key=anthropic_key)
                    prompt = f"""Analyze {ticker} for a {horizon} investment horizon.
 
Live market data: {price_ctx}
{news_ctx}
 
You are a professional equity analyst. Be specific with actual numbers. Think like a long-term growth investor.
 
Respond ONLY with valid JSON, no markdown fences, no extra text:
{{
  "verdict": "STRONG BUY or BUY or HOLD or SELL or AVOID",
  "verdict_reason": "one crisp sentence with a specific fact or number",
  "thesis": "2-3 sentences on the core long-term investment thesis",
  "bull_case": ["specific point with data", "specific point with data", "specific point with data"],
  "bear_case": ["specific risk with context", "specific risk", "specific risk"],
  "catalysts": ["near-term catalyst with timeline", "catalyst with timeline"],
  "entry_note": "1 sentence on current valuation and whether now is a good entry",
  "support": "key support price level or range e.g. $180-185",
  "target": "realistic price target for the horizon with brief rationale",
  "position_size": "small or medium or large"
}}"""
 
                    msg = client.messages.create(
                        model="claude-sonnet-4-20250514", max_tokens=1000,
                        messages=[{"role":"user","content":prompt}]
                    )
                    text = msg.content[0].text
                    m = re.search(r'\{[\s\S]*\}', text.replace("```json","").replace("```","").strip())
                    a = json.loads(m.group(0) if m else text)
 
                    vc = {"STRONG BUY":"🟢","BUY":"🟢","HOLD":"🟡","SELL":"🔴","AVOID":"🔴"}.get(a.get("verdict","HOLD"),"⚪")
                    st.markdown(f"## {vc} {ticker} — {a.get('verdict','—')}")
                    st.markdown(f"*{a.get('verdict_reason','')}*")
                    st.divider()
 
                    cl, cr = st.columns(2)
                    with cl:
                        st.markdown("### 📌 Core Thesis")
                        st.markdown(a.get("thesis","—"))
                        st.markdown("### 🟢 Bull Case")
                        for b in a.get("bull_case",[]): st.markdown(f"- {b}")
                    with cr:
                        st.markdown("### 🔴 Bear Case / Risks")
                        for b in a.get("bear_case",[]): st.markdown(f"- {b}")
                        st.markdown("### ⚡ Near-Term Catalysts")
                        for c in a.get("catalysts",[]): st.markdown(f"- {c}")
 
                    st.divider()
                    m1,m2,m3 = st.columns(3)
                    m1.metric("Key Support", a.get("support","—"))
                    m2.metric(f"Price Target", a.get("target","—"))
                    m3.metric("Position Size", a.get("position_size","—").title())
                    st.info(f"📋 **Entry note:** {a.get('entry_note','')}")
 
                except Exception as e:
                    if "401" in str(e): st.error("Invalid API key.")
                    elif "429" in str(e): st.error("Rate limited — wait a moment.")
                    else: st.error(f"Error: {e}")
 
    st.caption("AI analysis is for informational purposes only, not financial advice.")
 
# ══════════════════════════════════════════════════════════════════════════════
# FOOTER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown("""
<div style='text-align:center;padding:12px 0;'>
  <span style='color:#444;font-size:12px;'>
    📈 Growlio · Built by Gildr · 
    <a href='https://github.com' style='color:#555;'>GitHub</a> · 
    Not financial advice
  </span>
</div>
""", unsafe_allow_html=True)
