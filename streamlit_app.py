import streamlit as st
import yfinance as yf
import pandas as pd
import json
import os
import re
import requests
import feedparser
import plotly.graph_objects as go
from datetime import date, datetime
import time

st.set_page_config(page_title="Growlio", page_icon="📈", layout="wide")

# ── Session state ──────────────────────────────────────────────────────────────
if "trades" not in st.session_state:
    st.session_state.trades = []
if "page" not in st.session_state:
    st.session_state.page = "Dashboard"

# ── Sidebar nav ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("# 📈 Growlio")
    st.markdown("---")
    page = st.radio("Navigate", ["📊 Dashboard", "📓 Trade Journal", "🧠 AI Analyst", "📐 Position Sizer"], label_visibility="collapsed")
    st.markdown("---")
    api_key = st.text_input("Anthropic API key", type="password", placeholder="sk-ant-...", help="Only needed for AI Analyst. Get one at console.anthropic.com")
    st.markdown("<p style='font-size:11px;color:#555;'>Built by Gildr · No subscription</p>", unsafe_allow_html=True)

page = page.split(" ", 1)[1]

# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
if page == "Dashboard":
    st.markdown("# 📊 Market Dashboard")

    # Market status
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
    idx = {"S&P 500": "^GSPC", "NASDAQ": "^IXIC", "DOW": "^DJI", "VIX": "^VIX"}
    cols = st.columns(4)
    for i, (name, sym) in enumerate(idx.items()):
        with cols[i]:
            try:
                info = yf.Ticker(sym).fast_info
                price = info.last_price
                chg = (price - info.previous_close) / info.previous_close * 100
                st.metric(name, f"{price:,.2f}", f"{chg:+.2f}%", delta_color="normal" if chg >= 0 else "inverse")
            except:
                st.metric(name, "—", "—")

    st.divider()

    # Watchlist
    st.markdown("### Watchlist")
    syms = ["NVDA","AAPL","MSFT","META","GOOGL","AMZN","TSLA","PLTR","AMD","TSM"]
    wcols = st.columns(len(syms))
    for i, sym in enumerate(syms):
        with wcols[i]:
            try:
                info = yf.Ticker(sym).fast_info
                price = info.last_price
                chg = (price - info.previous_close) / info.previous_close * 100
                st.markdown(f"**{sym}**  \n${price:.2f}  \n{'🟢' if chg>=0 else '🔴'} {chg:+.2f}%")
            except:
                st.markdown(f"**{sym}**  \n—")

    st.divider()
    col_l, col_r = st.columns(2)

    # Movers
    with col_l:
        st.markdown("### Top Movers")
        mover_syms = ["NVDA","META","AAPL","MSFT","AMZN","GOOGL","TSLA","PLTR","AMD","NFLX","AVGO","ORCL","TSM","INTC"]
        mdata = []
        for sym in mover_syms:
            try:
                info = yf.Ticker(sym).fast_info
                p = info.last_price
                chg = (p - info.previous_close) / info.previous_close * 100
                mdata.append({"Symbol": sym, "Price": f"${p:.2f}", "Change": f"{chg:+.2f}%", "_c": chg})
            except: pass
        mdata.sort(key=lambda x: x["_c"], reverse=True)
        tg, tl = st.tabs(["▲ Gainers", "▼ Losers"])
        with tg:
            st.dataframe(pd.DataFrame([{k:v for k,v in d.items() if k!="_c"} for d in mdata[:5]]), hide_index=True, use_container_width=True)
        with tl:
            st.dataframe(pd.DataFrame([{k:v for k,v in d.items() if k!="_c"} for d in mdata[-5:][::-1]]), hide_index=True, use_container_width=True)

    # Sectors
    with col_r:
        st.markdown("### Sectors")
        secs = {"Technology":"XLK","Financials":"XLF","Healthcare":"XLV","Energy":"XLE","Consumer":"XLY","Industrials":"XLI","Utilities":"XLU"}
        for name, sym in secs.items():
            try:
                info = yf.Ticker(sym).fast_info
                chg = (info.last_price - info.previous_close) / info.previous_close * 100
                st.markdown(f"{'🟢' if chg>=0 else '🔴'} **{name}** — {chg:+.2f}%")
            except: pass

    st.divider()
    col_fg, col_crypto = st.columns(2)

    # Fear & Greed
    with col_fg:
        st.markdown("### Fear & Greed Index")
        try:
            r = requests.get("https://production.dataviz.cnn.io/index/fearandgreed/graphdata", timeout=5)
            d = r.json()
            score = round(d["fear_and_greed"]["score"])
            rating = d["fear_and_greed"]["rating"].replace("_"," ").title()
            col = "🔴" if score<30 else "🟡" if score<50 else "🟢" if score>70 else "⚪"
            st.metric("CNN Fear & Greed", f"{score} / 100", rating)
            st.progress(score/100)
            st.markdown(f"{col} **{rating}**")
        except:
            st.info("Fear & Greed unavailable")

    # Crypto
    with col_crypto:
        st.markdown("### Crypto")
        for name, sym in {"Bitcoin":"BTC-USD","Ethereum":"ETH-USD","Solana":"SOL-USD"}.items():
            try:
                info = yf.Ticker(sym).fast_info
                p = info.last_price
                chg = (p - info.previous_close) / info.previous_close * 100
                st.metric(name, f"${p:,.2f}", f"{chg:+.2f}%", delta_color="normal" if chg>=0 else "inverse")
            except:
                st.metric(name, "—", "—")

    st.divider()

    # News
    st.markdown("### Market News")
    def time_ago(t):
        try:
            diff = datetime.now() - datetime(*t[:6])
            m = int(diff.total_seconds()/60)
            return f"{m}m ago" if m<60 else f"{m//60}h ago" if m<1440 else f"{m//1440}d ago"
        except: return ""
    def cat_of(t):
        tl=t.lower()
        if any(w in tl for w in ["fed","rate","inflation","powell"]): return "🏦 FED"
        if any(w in tl for w in ["earn","profit","revenue","eps"]): return "📊 EARNINGS"
        if any(w in tl for w in ["nvidia","apple","meta","google","microsoft","ai","tech"]): return "💻 TECH"
        if any(w in tl for w in ["oil","energy","opec"]): return "⚡ ENERGY"
        if any(w in tl for w in ["bitcoin","crypto","eth"]): return "🪙 CRYPTO"
        return "📰 MARKETS"

    articles = []
    for url, src in [
        ("https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC&region=US&lang=en-US","Yahoo Finance"),
        ("https://feeds.marketwatch.com/marketwatch/topstories/","MarketWatch"),
        ("https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114","CNBC"),
    ]:
        try:
            feed = feedparser.parse(url)
            for e in feed.entries[:4]:
                title = e.get("title","").strip()
                link = e.get("link","#")
                pub = e.get("published_parsed")
                desc = re.sub(r"<[^>]+>","",e.get("summary",""))[:180].strip()
                if title and len(title)>15 and not any(a["title"]==title for a in articles):
                    articles.append({"title":title,"link":link,"pub":pub,"desc":desc,"src":src})
        except: pass

    if not articles:
        articles = [
            {"title":"S&P 500 climbs as tech sector leads broad market rally","src":"MarketWatch","pub":None,"link":"#","desc":"Technology shares drove gains across major US indexes as investors rotated into growth names."},
            {"title":"Federal Reserve holds rates steady, signals patience on cuts","src":"Yahoo Finance","pub":None,"link":"#","desc":"Fed officials voted to maintain the benchmark lending rate amid ongoing inflation uncertainty."},
            {"title":"NVIDIA surges on record data center revenue beat","src":"CNBC","pub":None,"link":"#","desc":"The chipmaker posted quarterly data center revenue far above Wall Street estimates driven by AI demand."},
            {"title":"Treasury yields edge lower as bond market stabilizes","src":"MarketWatch","pub":None,"link":"#","desc":"US government bond yields retreated slightly after a volatile week."},
            {"title":"Oil falls on rising US crude inventories","src":"Yahoo Finance","pub":None,"link":"#","desc":"Crude oil prices declined after weekly inventory data showed a larger-than-expected build."},
        ]

    for a in articles[:8]:
        c1, c2 = st.columns([7,1])
        with c1:
            st.markdown(f"**{a['title']}**")
            if a.get("desc"): st.markdown(f"<span style='color:#888;font-size:12px'>{a['desc']}</span>", unsafe_allow_html=True)
            st.markdown(f"<span style='color:#555;font-size:11px'>{a['src']}{' · '+time_ago(a['pub']) if a.get('pub') else ''} · {cat_of(a['title'])}</span>", unsafe_allow_html=True)
        with c2:
            if a.get("link","#") != "#":
                st.link_button("Read →", a["link"])
        st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# TRADE JOURNAL
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Trade Journal":
    st.markdown("# 📓 Trade Journal")

    def calc_pnl(t):
        return round((t["exit"]-t["entry"])*t["shares"] if t["dir"]=="Long" else (t["entry"]-t["exit"])*t["shares"], 2)
    def calc_r(t):
        if not t.get("stop"): return None
        risk = (t["entry"]-t["stop"])*t["shares"] if t["dir"]=="Long" else (t["stop"]-t["entry"])*t["shares"]
        return round(calc_pnl(t)/risk, 2) if risk > 0 else None

    trades = st.session_state.trades

    if trades:
        pnls = [calc_pnl(t) for t in trades]
        wins = [p for p in pnls if p>0]; losses = [p for p in pnls if p<0]
        total_pnl = round(sum(pnls),2)
        win_rate = round(len(wins)/len(pnls)*100)
        avg_win = round(sum(wins)/len(wins)) if wins else 0
        avg_loss = round(sum(losses)/len(losses)) if losses else 0
        expectancy = round((win_rate/100)*avg_win+(1-win_rate/100)*avg_loss)
        gw=sum(wins); gl=abs(sum(losses)); pf=round(gw/gl,2) if gl>0 else None
        rs=[calc_r(t) for t in trades if calc_r(t) is not None]
        avg_r=round(sum(rs)/len(rs),2) if rs else None
        c1,c2,c3,c4,c5,c6=st.columns(6)
        c1.metric("Total P&L",f"${total_pnl:+,.0f}")
        c2.metric("Win Rate",f"{win_rate}%")
        c3.metric("Trades",len(trades))
        c4.metric("Expectancy",f"${expectancy:+,.0f}")
        if pf: c5.metric("Profit Factor",pf)
        if avg_r: c6.metric("Avg R",f"{avg_r:+.2f}R")
        st.divider()

    tab1,tab2,tab3 = st.tabs(["➕ Log Trade","📋 History","📊 Analytics"])

    with tab1:
        with st.form("tf"):
            c1,c2,c3,c4=st.columns(4)
            ticker=c1.text_input("Ticker",placeholder="AAPL").upper().strip()
            direction=c2.selectbox("Direction",["Long","Short"])
            trade_date=c3.date_input("Date",value=date.today())
            setup=c4.text_input("Setup",placeholder="Breakout, VWAP...")
            c1,c2,c3,c4=st.columns(4)
            entry=c1.number_input("Entry ($)",min_value=0.0,step=0.01,format="%.2f")
            exit_p=c2.number_input("Exit ($)",min_value=0.0,step=0.01,format="%.2f")
            shares=c3.number_input("Shares",min_value=1,step=1)
            stop=c4.number_input("Stop ($) optional",min_value=0.0,step=0.01,format="%.2f")
            notes=st.text_area("Notes",placeholder="Why you took it, what happened...")
            if st.form_submit_button("✚ Log Trade", use_container_width=True):
                if not ticker or entry==0 or exit_p==0:
                    st.error("Fill in ticker, entry, and exit.")
                else:
                    t={"id":int(time.time()*1000),"ticker":ticker,"dir":direction,"date":str(trade_date),"entry":entry,"exit":exit_p,"shares":int(shares),"stop":stop if stop>0 else None,"setup":setup,"notes":notes}
                    st.session_state.trades.append(t)
                    st.success(f"Logged — P&L: ${calc_pnl(t):+,.2f}")
                    st.rerun()

    with tab2:
        if not trades:
            st.info("No trades yet.")
        else:
            fc1,fc2,fc3=st.columns(3)
            fdir=fc1.selectbox("Direction",["All","Long","Short"])
            fres=fc2.selectbox("Result",["All","Wins","Losses"])
            ftick=fc3.text_input("Ticker search")
            f=[t for t in trades if (fdir=="All" or t["dir"]==fdir) and (fres=="All" or (fres=="Wins" and calc_pnl(t)>0) or (fres=="Losses" and calc_pnl(t)<0)) and (not ftick or ftick.upper() in t["ticker"])]
            f.sort(key=lambda x:x["date"],reverse=True)
            rows=[{"Ticker":t["ticker"],"Dir":t["dir"],"Date":t["date"],"Entry":f"${t['entry']:.2f}","Exit":f"${t['exit']:.2f}","Shares":t["shares"],"P&L":f"${calc_pnl(t):+,.2f}","R":f"{calc_r(t):+.2f}R" if calc_r(t) else "—","Setup":t.get("setup","—")} for t in f]
            st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
            if st.button("🗑 Clear all trades"):
                st.session_state.trades=[]
                st.rerun()

    with tab3:
        if not trades:
            st.info("Log some trades to see analytics.")
        else:
            s=sorted(trades,key=lambda x:x["date"])
            pnls=[calc_pnl(t) for t in s]
            labels=[f"{t['ticker']} {t['date'][5:]}" for t in s]
            running=[]; total=0
            for p in pnls: total+=p; running.append(round(total,2))
            fig1=go.Figure()
            fig1.add_trace(go.Scatter(x=labels,y=running,mode="lines+markers",line=dict(color="#60a5fa",width=2),fill="tozeroy",fillcolor="rgba(96,165,250,0.07)"))
            fig1.update_layout(title="Equity Curve",plot_bgcolor="#161616",paper_bgcolor="#0d0d0d",font_color="#f0f0f0",height=280,margin=dict(l=10,r=10,t=40,b=10),xaxis=dict(showgrid=False,tickangle=-45,tickfont=dict(size=10)),yaxis=dict(gridcolor="#282828"))
            st.plotly_chart(fig1,use_container_width=True)
            fig2=go.Figure()
            fig2.add_trace(go.Bar(x=labels,y=pnls,marker_color=["#4ade80" if p>=0 else "#f87171" for p in pnls]))
            fig2.update_layout(title="P&L per Trade",plot_bgcolor="#161616",paper_bgcolor="#0d0d0d",font_color="#f0f0f0",height=220,margin=dict(l=10,r=10,t=40,b=10),xaxis=dict(showgrid=False,tickangle=-45,tickfont=dict(size=10)),yaxis=dict(gridcolor="#282828"))
            st.plotly_chart(fig2,use_container_width=True)
            ic1,ic2=st.columns(2)
            with ic1:
                st.markdown("**P&L by Setup**")
                bs={}
                for t in trades:
                    k=t.get("setup") or "Untagged"
                    if k not in bs: bs[k]={"pnl":0,"wins":0,"total":0}
                    p=calc_pnl(t); bs[k]["pnl"]=round(bs[k]["pnl"]+p,2); bs[k]["total"]+=1
                    if p>0: bs[k]["wins"]+=1
                st.dataframe(pd.DataFrame([{"Setup":k,"P&L":f"${v['pnl']:+,.0f}","Win%":f"{round(v['wins']/v['total']*100)}%"} for k,v in sorted(bs.items(),key=lambda x:-x[1]["pnl"])]),hide_index=True,use_container_width=True)
            with ic2:
                st.markdown("**P&L by Day**")
                bd={}
                for t in trades:
                    try:
                        d=pd.Timestamp(t["date"]).day_name()[:3]
                        bd[d]=round(bd.get(d,0)+calc_pnl(t),2)
                    except: pass
                st.dataframe(pd.DataFrame([{"Day":k,"P&L":f"${v:+,.0f}"} for k,v in sorted(bd.items(),key=lambda x:-x[1])]),hide_index=True,use_container_width=True)
            st.divider()
            csv=pd.DataFrame([{**t,"pnl":calc_pnl(t),"r":calc_r(t)} for t in trades]).to_csv(index=False)
            st.download_button("⬇ Download CSV",csv,"growlio_trades.csv","text/csv")

# ══════════════════════════════════════════════════════════════════════════════
# AI ANALYST
# ══════════════════════════════════════════════════════════════════════════════
elif page == "AI Analyst":
    st.markdown("# 🧠 AI Stock Analyst")
    st.markdown("Enter any ticker and get a full investment thesis — bull case, bear case, price target.")
    st.divider()

    c1,c2=st.columns([2,2])
    ticker=c1.text_input("Ticker",placeholder="NVDA").upper().strip()
    horizon=c2.selectbox("Horizon",["Long-term (3–5 years)","Medium-term (1–2 years)","Short-term (3–6 months)"])
    quick=st.pills("Quick picks",["NVDA","AAPL","META","MSFT","GOOGL","AMZN","PLTR","AMD","TSLA","TSM"])
    if quick: ticker=quick

    if st.button("✦ Analyze",use_container_width=True,type="primary"):
        if not ticker: st.error("Enter a ticker.")
        elif not api_key: st.error("Enter your Anthropic API key in the sidebar.")
        else:
            price_ctx=""
            try:
                info=yf.Ticker(ticker).info
                price_ctx=f"Price: ${info.get('currentPrice',info.get('regularMarketPrice','N/A'))} | 52w High: ${info.get('fiftyTwoWeekHigh','N/A')} | 52w Low: ${info.get('fiftyTwoWeekLow','N/A')} | Market cap: ${info.get('marketCap',0)/1e9:.1f}B | P/E: {info.get('trailingPE','N/A')} | Fwd P/E: {info.get('forwardPE','N/A')} | Revenue growth: {info.get('revenueGrowth',0)*100:.1f}% | Analyst target: ${info.get('targetMeanPrice','N/A')} | Recommendation: {info.get('recommendationKey','N/A')}"
            except: pass

            with st.spinner(f"Analyzing {ticker}..."):
                try:
                    import anthropic
                    client=anthropic.Anthropic(api_key=api_key)
                    msg=client.messages.create(
                        model="claude-sonnet-4-20250514",max_tokens=1000,
                        messages=[{"role":"user","content":f"Analyze {ticker} for {horizon}.\nLive data: {price_ctx}\nBe specific with numbers. Think like a long-term growth investor.\nRespond ONLY with valid JSON no markdown:\n{{\"verdict\":\"STRONG BUY or BUY or HOLD or SELL or AVOID\",\"verdict_reason\":\"one sentence with specific fact\",\"thesis\":\"2-3 sentences\",\"bull_case\":[\"point\",\"point\",\"point\"],\"bear_case\":[\"risk\",\"risk\",\"risk\"],\"catalysts\":[\"catalyst\",\"catalyst\"],\"entry_note\":\"1 sentence on valuation\",\"support\":\"key support level\",\"target\":\"price target with rationale\",\"position_size\":\"small or medium or large\"}}"}]
                    )
                    text=msg.content[0].text
                    m=re.search(r'\{[\s\S]*\}',text.replace("```json","").replace("```","").strip())
                    a=json.loads(m.group(0) if m else text)
                    vc={"STRONG BUY":"🟢","BUY":"🟢","HOLD":"🟡","SELL":"🔴","AVOID":"🔴"}.get(a.get("verdict","HOLD"),"⚪")
                    st.markdown(f"## {vc} {ticker} — {a.get('verdict','—')}")
                    st.markdown(f"*{a.get('verdict_reason','')}*")
                    st.divider()
                    cl,cr=st.columns(2)
                    with cl:
                        st.markdown("### 📌 Core Thesis")
                        st.markdown(a.get("thesis","—"))
                        st.markdown("### 🟢 Bull Case")
                        for b in a.get("bull_case",[]): st.markdown(f"- {b}")
                    with cr:
                        st.markdown("### 🔴 Bear Case")
                        for b in a.get("bear_case",[]): st.markdown(f"- {b}")
                        st.markdown("### ⚡ Catalysts")
                        for c in a.get("catalysts",[]): st.markdown(f"- {c}")
                    st.divider()
                    m1,m2,m3=st.columns(3)
                    m1.metric("Key Support",a.get("support","—"))
                    m2.metric("Price Target",a.get("target","—"))
                    m3.metric("Position Size",a.get("position_size","—").title())
                    st.info(f"📋 {a.get('entry_note','')}")
                except Exception as e:
                    st.error(f"Error: {e}")

    st.caption("AI analysis is for informational purposes only, not financial advice.")

# ══════════════════════════════════════════════════════════════════════════════
# POSITION SIZER
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Position Sizer":
    st.markdown("# 📐 Position Sizer")
    st.markdown("Calculate your exact share count before you enter a trade.")
    st.divider()

    c1,c2=st.columns(2)
    with c1:
        st.markdown("### Parameters")
        account=st.number_input("Account size ($)",min_value=100.0,value=25000.0,step=500.0)
        risk_pct=st.slider("Risk per trade (%)",min_value=0.1,max_value=5.0,value=1.0,step=0.1)
        direction=st.selectbox("Direction",["Long","Short"])
        cc1,cc2=st.columns(2)
        entry=cc1.number_input("Entry ($)",min_value=0.01,value=150.0,step=0.01)
        stop=cc2.number_input("Stop ($)",min_value=0.01,value=145.0,step=0.01)
        target=st.number_input("Target ($) — optional",min_value=0.0,value=0.0,step=0.01)

    with c2:
        st.markdown("### Result")
        risk_dollar=round(account*risk_pct/100,2)
        rps=abs(entry-stop)
        if rps>0:
            shares=int(risk_dollar/rps)
            pos_size=round(shares*entry,2)
            pct_acc=round(pos_size/account*100,1)
            m1,m2=st.columns(2)
            m1.metric("Shares",f"{shares:,}")
            m2.metric("Position size",f"${pos_size:,.2f}")
            m3,m4=st.columns(2)
            m3.metric("$ at risk",f"-${risk_dollar:,.2f}")
            m4.metric("% of account",f"{pct_acc}%")
            m5,m6=st.columns(2)
            m5.metric("Risk per share",f"${rps:.2f}")
            if target>0:
                reward=abs(target-entry)
                rr=round(reward/rps,2)
                profit=round(shares*reward,2)
                m6.metric("R:R ratio",f"1 : {rr}")
                st.success(f"If target hit: **+${profit:,.2f}**")
                if rr<1.5: st.warning("R:R below 1.5 — consider skipping.")
                elif rr>=3: st.success("Strong R:R setup.")
            st.divider()
            if pct_acc>10: st.error(f"⚠️ {pct_acc}% of account is high — reduce shares.")
            elif pct_acc>5: st.warning(f"{pct_acc}% of account — moderate risk.")
            else: st.success(f"{pct_acc}% of account — well sized.")
            if risk_pct>2: st.warning(f"Risking {risk_pct}% is aggressive. Pro traders risk 0.5–1%.")
        else:
            st.error("Entry and stop must be different.")

    st.divider()
    st.markdown("""
**Position sizing rules:**
- **1% rule** — never risk more than 1% per trade
- **R:R minimum** — aim for at least 1.5:1 before entering
- **Max concentration** — no single position over 10% of account
""")
