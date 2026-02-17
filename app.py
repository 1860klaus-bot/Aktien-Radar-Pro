import streamlit as st
import yfinance as yf
import pandas as pd
import time
import feedparser
import urllib.parse
from datetime import datetime

# --- 0. SICHERHEITS-CHECK ---
try:
    import feedparser
except ImportError:
    st.error("⚠️ Modul 'feedparser' fehlt! Bitte in `requirements.txt` ergänzen.")
    st.stop()

st.set_page_config(page_title="Aktien-Radar Global", page_icon="🌍", layout="wide")
st.title("💎 Aktien-Radar: Global (News & Experten)")

# --- 1. DATENBANKEN (WIKIFOLIO WERTE & LINKS) ---

# 🟢 STEFAN WALDHAUSER (HGI) - High-Tech Stock Picking
# Die 15 Werte exakt aus deiner Liste
HGI_PORTFOLIO = "IAC, ANGI, PYPL, MNDY, LYFT, ABNB, UPWK, UBER, PATH, TWLO, ESTC, GOOGL, PSTG, ANET, SHOP" 
HGI_WIKI_URL = "https://www.wikifolio.com/de/de/w/wf0stwtech"
HGI_SUBSTACK_URL = "https://waldhauser.substack.com"

# 🔵 SIMON WEISHAR (SZEW) - Szew Grundinvestment
# Aktuelle Top-Holdings (Szew Grundinvestment / Data Driven)
SZEW_PORTFOLIO = "ANGI, TRN.L, RMV.L, YOU.L, EUK.DE, MONY.L, OTB.L, NU, TTD"
SZEW_WIKI_URL = "https://www.wikifolio.com/de/de/w/wf00szew01"
SZEW_SUBSTACK_URL = "https://szew.substack.com"

# Standard-Listen
DAX_LISTE = "716460, 723610, 840400, 710000, 766403, 555750, BASF11, BAY001, 519000, 514000, 623100, ENAG99, A1EWWW, 543900, CBK100, 581005, DTR0CK, 604843, 843002, PAG911, 703712, SHL100, A1ML7J, 938914"
US_TECH_LISTE = "865985, 870747, 906866, A1CX3T, 918422, A14Y6F, A1JWVX, 552484, A14R7U, A1J5X3, A2QP7J, 851399"
GLOBAL_TOP_LISTE = "865985, 870747, 918422, 716460, 723610, 840400, 850663, 856958, A0M240, 850517"
FAVORITEN_LISTE = "NVDA, TSLA, ANGI, PLTR, COIN, AMD, RHM.DE, TUI1.DE, LHA.DE, 865985"

WKN_MAP = {
    "716460": "SAP.DE", "SAP": "SAP.DE", "723610": "SIE.DE", "SIEMENS": "SIE.DE", "840400": "ALV.DE", "ALLIANZ": "ALV.DE",
    "710000": "MBG.DE", "MERCEDES": "MBG.DE", "766403": "VOW3.DE", "VW": "VOW3.DE", "555750": "DTE.DE", "TELEKOM": "DTE.DE",
    "BASF11": "BAS.DE", "BASF": "BAS.DE", "BAY001": "BAYN.DE", "BAYER": "BAYN.DE", "519000": "BMW.DE", "BMW": "BMW.DE",
    "543900": "CON.DE", "CONTINENTAL": "CON.DE", "CBK100": "CBK.DE", "COMMERZBANK": "CBK.DE", "514000": "DBK.DE", "DEUTSCHE BANK": "DBK.DE",
    "581005": "DB1.DE", "DEUTSCHE BOERSE": "DB1.DE", "DTR0CK": "DTG.DE", "DAIMLER TRUCK": "DTG.DE", "ENAG99": "EOAN.DE", "EON": "EOAN.DE",
    "A1EWWW": "ADS.DE", "ADIDAS": "ADS.DE", "604843": "HEN3.DE", "HENKEL": "HEN3.DE", "623100": "IFX.DE", "INFINEON": "IFX.DE",
    "843002": "MUV2.DE", "MUENCHENER RUECK": "MUV2.DE", "PAG911": "P911.DE", "PORSCHE": "P911.DE", "703712": "RWE.DE", "RWE": "RWE.DE",
    "SHL100": "SHL.DE", "SIEMENS HEALTH": "SHL.DE", "A1ML7J": "VNA.DE", "VONOVIA": "VNA.DE", "938914": "AIR.DE", "AIRBUS": "AIR.DE",
    "703000": "RHM.DE", "RHEINMETALL": "RHM.DE", "TUAG50": "TUI1.DE", "TUI": "TUI1.DE", "823212": "LHA.DE", "LUFTHANSA": "LHA.DE",
    "865985": "AAPL", "APPLE": "AAPL", "870747": "MSFT", "MICROSOFT": "MSFT", "906866": "AMZN", "AMAZON": "AMZN",
    "A1CX3T": "TSLA", "TESLA": "TSLA", "918422": "NVDA", "NVIDIA": "NVDA", "A14Y6F": "GOOGL", "ALPHABET": "GOOGL",
    "A1JWVX": "META", "META": "META", "552484": "NFLX", "NETFLIX": "NFLX", "A14R7U": "PYPL", "PAYPAL": "PYPL",
    "A1J5X3": "ANGI", "ANGI": "ANGI", "A2QP7J": "GME", "GAMESTOP": "GME", "A0F5UF": "PLTR", "PALANTIR": "PLTR",
    "A2QP7J": "COIN", "COINBASE": "COIN", "863186": "AMD", "AMD": "AMD", "850663": "KO", "COCA COLA": "KO",
    "856958": "MCD", "MCDONALDS": "MCD", "A0M240": "V", "VISA": "V", "851399": "IBM", "IBM": "IBM",
    "860853": "DIS", "DISNEY": "DIS", "850517": "JPM", "JP MORGAN": "JPM", "A0YJQ2": "BRK-B", "BERKSHIRE": "BRK-B"
}

# --- HELPER FUNKTIONEN ---
def get_google_news(query_term):
    try:
        search_query = urllib.parse.quote(f"{query_term} Aktie")
        rss_url = f"https://news.google.com/rss/search?q={search_query}&hl=de&gl=DE&ceid=DE:de"
        feed = feedparser.parse(rss_url)
        news_items = []
        for entry in feed.entries[:3]: 
            pub_date = entry.published[:16] if hasattr(entry, 'published') else ""
            news_items.append({'title': entry.title, 'link': entry.link, 'publisher': getattr(entry, 'source', {}).get('title', 'News'), 'published': pub_date})
        return news_items
    except: return []

def get_rss_feed(rss_url):
    try:
        feed = feedparser.parse(rss_url)
        news_items = []
        for entry in feed.entries[:3]:
            pub_date = entry.published[:16] if hasattr(entry, 'published') else ""
            news_items.append({'title': entry.title, 'link': entry.link, 'published': pub_date})
        return news_items
    except: return []

def load_list(ticker_string):
    st.session_state.ticker_text = ticker_string

# --- 2. SEITENLEISTE ---
st.sidebar.header("1. Listen laden")

if 'ticker_text' not in st.session_state: st.session_state.ticker_text = FAVORITEN_LISTE
if 'scan_results' not in st.session_state: st.session_state.scan_results = None
if 'scan_news' not in st.session_state: st.session_state.scan_news = {}
if 'last_update' not in st.session_state: st.session_state.last_update = None

col1, col2 = st.sidebar.columns(2)
with col1:
    st.button("🇩🇪 DAX Liste", on_click=load_list, args=(DAX_LISTE,))
with col2:
    st.button("🇺🇸 US Tech", on_click=load_list, args=(US_TECH_LISTE,))

col3, col4 = st.sidebar.columns(2)
with col3:
    st.button("🌍 Global", on_click=load_list, args=(GLOBAL_TOP_LISTE,))
with col4:
    st.button("⭐ Favoriten", on_click=load_list, args=(FAVORITEN_LISTE,))

ticker_input = st.sidebar.text_area("Aktien-Liste (Kürzel kommagetrennt)", key="ticker_text", height=150)

st.sidebar.header("3. Steuerung")
rsi_limit = st.sidebar.slider("Max. RSI (14 Tage)", 10, 100, 87)
auto_refresh = st.sidebar.toggle("⏱️ Live-Modus", value=False)

st.sidebar.divider()
st.sidebar.header("4. Wikifolio-Portfolios")
st.sidebar.button("📥 HGI (Waldhauser) laden", on_click=load_list, args=(HGI_PORTFOLIO,))
st.sidebar.button("📥 Szew (Simon Weishar) laden", on_click=load_list, args=(SZEW_PORTFOLIO,))

show_experts = st.sidebar.checkbox("🧠 Experten-Briefing anzeigen", value=True)

# --- 3. HAUPTPROGRAMM ---
start_scan = st.button("🚀 Scanner starten", type="primary")
should_scan = start_scan or auto_refresh

if should_scan:
    raw_inputs = [t.strip().upper() for t in ticker_input.split(",") if t.strip()]
    tickers = []
    for item in raw_inputs:
        if item in WKN_MAP: tickers.append(WKN_MAP[item])
        else: tickers.append(item)
            
    temp_results = []
    temp_news = {}
    
    if not auto_refresh:
        progress_bar = st.progress(0)
        status_text = st.empty()
    
    total_tickers = len(tickers)
    for i, ticker in enumerate(tickers):
        if not auto_refresh:
            status_text.text(f"Analysiere ({i+1}/{total_tickers}): {ticker}...")
            
        try:
            stock = yf.Ticker(ticker)
            df_hist = stock.history(period="300d")
            
            if not df_hist.empty and len(df_hist) > 200:
                delta = df_hist['Close'].diff()
                gain = delta.where(delta > 0, 0)
                loss = -delta.where(delta < 0, 0)
                avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
                avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
                rsi_val = 100 - (100 / (1 + (avg_gain / avg_loss))).iloc[-1]
                
                sma_50 = df_hist['Close'].rolling(window=50).mean().iloc[-1]
                sma_200 = df_hist['Close'].rolling(window=200).mean().iloc[-1]
                current_price = df_hist['Close'].iloc[-1]
                
                live_price = stock.info.get('currentPrice') or current_price
                prev_close = stock.info.get('previousClose') or df_hist['Close'].iloc[-2]
                change_pct = ((live_price - prev_close) / prev_close) * 100
                
                lookback = 10
                recent_50 = df_hist['Close'].rolling(window=50).mean().iloc[-lookback:]
                recent_200 = df_hist['Close'].rolling(window=200).mean().iloc[-lookback:]
                trend_signal = "Neutral"
                
                if sma_50 > sma_200:
                    if (recent_50 < recent_200).any(): trend_signal = "✨ GOLDENES KREUZ (Neu)"
                    else: trend_signal = "📈 Aufwärtstrend"
                elif sma_50 < sma_200:
                    if (recent_50 > recent_200).any(): trend_signal = "💀 Todeskreuz (Neu)"
                    else: trend_signal = "📉 Abwärtstrend"
                
                info = stock.info
                full_name = info.get('longName') or info.get('shortName') or ticker
                currency = info.get('currency', '?')
                target = info.get('targetMeanPrice', 0)
                upside = ((target - current_price) / current_price) * 100 if target and current_price else 0
                rev_growth = info.get('revenueGrowth', 0) 
                earn_growth = info.get('earningsGrowth', 0)
                peg_ratio = info.get('pegRatio') or info.get('trailingPegRatio')
                status = "Unterbewertet" if (upside > 15 and rsi_val < 45) else "Neutral"
                if upside < 0: status = "Überbewertet"

                if rsi_val <= rsi_limit:
                    temp_results.append({
                        "Name": full_name, 
                        "Kürzel": ticker, 
                        "Kurs": f"{round(live_price, 2)} {currency}",
                        "Analysten-Ziel": f"{round(target, 2)} {currency}" if target else "N/A", 
                        "Potenzial %": round(upside, 1),
                        "Tages-Trend": f"{'+' if change_pct > 0 else ''}{round(change_pct, 2)}%",
                        "RSI (14)": round(float(rsi_val), 1), 
                        "Trend-Signal": trend_signal,
                        "Umsatz-Wachst.": f"{round(rev_growth * 100, 1)}%" if rev_growth else "N/A",
                        "PEG": round(peg_ratio, 2) if peg_ratio else "N/A", 
                        "Bewertung": status
                    })
                    temp_news[ticker] = get_google_news(full_name.split(" ")[0])
        except Exception: continue
        if not auto_refresh: progress_bar.progress((i + 1) / total_tickers)
            
    if not auto_refresh:
        status_text.empty()
        progress_bar.empty()
    
    st.session_state.scan_results = temp_results
    st.session_state.scan_news = temp_news
    st.session_state.last_update = datetime.now().strftime("%H:%M:%S")

# B) ANZEIGE
if st.session_state.scan_results:
    results = st.session_state.scan_results
    news_data = st.session_state.scan_news
    last_up = st.session_state.last_update
    
    st.markdown(f"**Stand:** {last_up}")
    st.subheader(f"🌍 Marktanalyse ({len(results)} Treffer)")
    df_res = pd.DataFrame(results)
    
    def style_percent_color(val):
        if isinstance(val, str) and "%" in val:
            try:
                num = float(val.replace('%', '').replace('+', '').strip())
                return 'color: green' if num > 0 else 'color: red'
            except: return ''
        return ''

    def style_trend(val):
        if "GOLDENES" in str(val): return 'color: #006400; font-weight: bold; background-color: #e6ffe6' 
        if "Abwärtstrend" in str(val) or "Todeskreuz" in str(val): return 'color: red; font-weight: bold'
        if "Aufwärtstrend" in str(val): return 'color: green'
        return ''

    display_cols = ["Name", "Kürzel", "Kurs", "Analysten-Ziel", "Potenzial %", "Tages-Trend", "RSI (14)", "Trend-Signal", "Umsatz-Wachst.", "PEG", "Bewertung"]
    st.dataframe(df_res[display_cols].style
                    .applymap(style_trend, subset=['Trend-Signal'])
                    .applymap(style_percent_color, subset=['Tages-Trend', 'Potenzial %']), 
                    use_container_width=True)
    
    st.divider()
    st.subheader("📉 Profi-Chart")
    ticker_list = [f"{r['Name']} ({r['Kürzel']})" for r in results]
    selected_option = st.selectbox("Aktie auswählen:", ticker_list, key="chart_select")
    selected_ticker = selected_option.split("(")[-1].replace(")", "")
    
    if selected_ticker:
        chart_stock = yf.Ticker(selected_ticker)
        chart_df = chart_stock.history(period="2y")
        if not chart_df.empty:
            chart_df['SMA 200'] = chart_df['Close'].rolling(window=200).mean()
            chart_df['SMA 50'] = chart_df['Close'].rolling(window=50).mean()
            st.line_chart(chart_df.iloc[-250:][['Close', 'SMA 200', 'SMA 50']])

    if show_experts:
        st.divider()
        st.subheader("🧠 Experten-Briefing")
        col1, col2 = st.columns(2)
        with col1:
            st.info("📊 **Stefan Waldhauser (HGI)**")
            c1a, c1b = st.columns(2)
            c1a.link_button("📈 Wikifolio Trades", HGI_WIKI_URL, use_container_width=True)
            c1b.link_button("📝 Substack / Blog", HGI_SUBSTACK_URL, use_container_width=True)
            wh_news = get_rss_feed("https://high-tech-investing.de/feed/")
            for item in wh_news: st.markdown(f"• [{item['title']}]({item['link']})")
        with col2:
            st.info("🐻 **Simon Weishar (Szew)**")
            c2a, c2b = st.columns(2)
            c2a.link_button("📈 Wikifolio Trades", SZEW_WIKI_URL, use_container_width=True)
            c2b.link_button("📝 Substack", SZEW_SUBSTACK_URL, use_container_width=True)
            sz_news = get_rss_feed("https://szew.substack.com/feed")
            for item in sz_news: st.markdown(f"• [{item['title']}]({item['link']})")

    st.divider()
    st.subheader("📰 News zur Aktie")
    if news_data and selected_ticker:
        for item in news_data.get(selected_ticker, []):
            st.markdown(f"• **[{item['title']}]({item['link']})**")
            st.caption(f"{item['publisher']} | {item['published']}")

if auto_refresh:
    time.sleep(60)
    st.rerun()
