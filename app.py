import streamlit as st
import yfinance as yf
import pandas as pd
import time
import feedparser
import urllib.parse
from datetime import datetime

st.set_page_config(page_title="Aktien-Radar Global", page_icon="🌍", layout="wide")
st.title("💎 Aktien-Radar: Global (News & Experten)")

# --- 1. DATENBANKEN ---
DAX_LISTE = "716460, 723610, 840400, 710000, 766403, 555750, BASF11, BAY001, 519000, 514000, 623100, ENAG99, A1EWWW, 543900, CBK100, 581005, DTR0CK, 604843, 843002, PAG911, 703712, SHL100, A1ML7J, 938914"
US_TECH_LISTE = "865985, 870747, 906866, A1CX3T, 918422, A14Y6F, A1JWVX, 552484, A14R7U, A1J5X3, A2QP7J, 851399"
GLOBAL_TOP_LISTE = "865985, 870747, 918422, 716460, 723610, 840400, 850663, 856958, A0M240, 850517"
FAVORITEN_LISTE = "NVDA, TSLA, ANGI, PLTR, COIN, AMD, RHM.DE, TUI1.DE, LHA.DE, 865985"

WKN_MAP = {
    # DAX
    "716460": "SAP.DE", "SAP": "SAP.DE", "723610": "SIE.DE", "SIEMENS": "SIE.DE", "840400": "ALV.DE", "ALLIANZ": "ALV.DE",
    "710000": "MBG.DE", "MERCEDES": "MBG.DE", "766403": "VOW3.DE", "VW": "VOW3.DE", "555750": "DTE.DE", "TELEKOM": "DTE.DE",
    "BASF11": "BAS.DE", "BASF": "BAS.DE", "BAY001": "BAYN.DE", "BAYER": "BAYN.DE", "519000": "BMW.DE", "BMW": "BMW.DE",
    "543900": "CON.DE", "CONTINENTAL": "CON.DE", "CBK100": "CBK.DE", "COMMERZBANK": "CBK.DE", "514000": "DBK.DE", "DEUTSCHE BANK": "DBK.DE",
    "581005": "DB1.DE", "DEUTSCHE BOERSE": "DB1.DE", "DTR0CK": "DTG.DE", "DAIMLER TRUCK": "DTG.DE", "ENAG99": "EOAN.DE", "EON": "EOAN.DE",
    "A1EWWW": "ADS.DE", "ADIDAS": "ADS.DE", "604843": "HEN3.DE", "HENKEL": "HEN3.DE", "623100": "IFX.DE", "INFINEON": "IFX.DE",
    "843002": "MUV2.DE", "MUENCHENER RUECK": "MUV2.DE", "PAG911": "P911.DE", "PORSCHE": "P911.DE", "703712": "RWE.DE", "RWE": "RWE.DE",
    "SHL100": "SHL.DE", "SIEMENS HEALTH": "SHL.DE", "A1ML7J": "VNA.DE", "VONOVIA": "VNA.DE", "938914": "AIR.DE", "AIRBUS": "AIR.DE",
    "703000": "RHM.DE", "RHEINMETALL": "RHM.DE", "TUAG50": "TUI1.DE", "TUI": "TUI1.DE", "823212": "LHA.DE", "LUFTHANSA": "LHA.DE",
    # US & International
    "865985": "AAPL", "APPLE": "AAPL", "870747": "MSFT", "MICROSOFT": "MSFT", "906866": "AMZN", "AMAZON": "AMZN",
    "A1CX3T": "TSLA", "TESLA": "TSLA", "918422": "NVDA", "NVIDIA": "NVDA", "A14Y6F": "GOOGL", "ALPHABET": "GOOGL",
    "A1JWVX": "META", "META": "META", "552484": "NFLX", "NETFLIX": "NFLX", "A14R7U": "PYPL", "PAYPAL": "PYPL",
    "A1J5X3": "ANGI", "ANGI": "ANGI", "A2QP7J": "GME", "GAMESTOP": "GME", "A0F5UF": "PLTR", "PALANTIR": "PLTR",
    "A2QP7J": "COIN", "COINBASE": "COIN", "863186": "AMD", "AMD": "AMD", "850663": "KO", "COCA COLA": "KO",
    "856958": "MCD", "MCDONALDS": "MCD", "A0M240": "V", "VISA": "V", "851399": "IBM", "IBM": "IBM",
    "860853": "DIS", "DISNEY": "DIS", "850517": "JPM", "JP MORGAN": "JPM", "A0YJQ2": "BRK-B", "BERKSHIRE": "BRK-B"
}

# --- HELPER: NEWS FETCH ---
def get_google_news(query_term):
    """Holt Nachrichten via Google News RSS"""
    try:
        search_query = urllib.parse.quote(f"{query_term} Aktie")
        rss_url = f"https://news.google.com/rss/search?q={search_query}&hl=de&gl=DE&ceid=DE:de"
        feed = feedparser.parse(rss_url)
        news_items = []
        for entry in feed.entries[:3]: 
            pub_date = entry.published if hasattr(entry, 'published') else ""
            if len(pub_date) > 16: pub_date = pub_date[:16]
            news_items.append({'title': entry.title, 'link': entry.link, 'publisher': entry.source.title, 'published': pub_date})
        return news_items
    except: return []

def get_rss_feed(rss_url):
    """Holt Nachrichten von Substack/Blogs via RSS"""
    try:
        feed = feedparser.parse(rss_url)
        news_items = []
        for entry in feed.entries[:5]:
            pub_date = entry.published[:16] if hasattr(entry, 'published') else ""
            news_items.append({'title': entry.title, 'link': entry.link, 'published': pub_date})
        return news_items
    except: return []

# --- 2. SEITENLEISTE MIT LOGIK ---
st.sidebar.header("1. Listen laden")
if 'ticker_text' not in st.session_state:
    st.session_state['ticker_text'] = FAVORITEN_LISTE

if 'scan_results' not in st.session_state: st.session_state['scan_results'] = None
if 'scan_news' not in st.session_state: st.session_state['scan_news'] = {}
if 'last_update' not in st.session_state: st.session_state['last_update'] = None

col1, col2 = st.sidebar.columns(2)
with col1:
    if st.button("🇩🇪 DAX Liste"): st.session_state['ticker_text'] = DAX_LISTE
with col2:
    if st.button("🇺🇸 US Tech"): st.session_state['ticker_text'] = US_TECH_LISTE

col3, col4 = st.sidebar.columns(2)
with col3:
    if st.button("🌍 Global Top"): st.session_state['ticker_text'] = GLOBAL_TOP_LISTE
with col4:
    if st.button("⭐ Favoriten"): st.session_state['ticker_text'] = FAVORITEN_LISTE

st.sidebar.header("2. Manuelle Eingabe")
ticker_input = st.sidebar.text_area("Aktien-Liste (WKN, Name oder Kürzel)", value=st.session_state['ticker_text'], height=150)

st.sidebar.header("3. Steuerung")
rsi_limit = st.sidebar.slider("Max. RSI (14 Tage)", 10, 100, 87)
auto_refresh = st.sidebar.toggle("⏱️ Live-Modus (60s Auto-Update)", value=False)

# EXPERTEN SEKTION
st.sidebar.header("4. Experten-Radar")
show_experts = st.sidebar.checkbox("🧠 Experten (Substack & Wiki)", value=True)

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
    else:
        st.toast("Lade Live-Daten...", icon="🔄")
    
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
                bid = stock.info.get('bid')
                ask = stock.info.get('ask')
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
                
                dist_200 = ((current_price - sma_200) / sma_200) * 100
                dist_50 = ((current_price - sma_50) / sma_50) * 100
                
                info = stock.info
                name = info.get('shortName') or info.get('longName') or ticker
                currency = info.get('currency', '?')
                clean_name = name.replace(" Inc.", "").replace(" Corporation", "").replace(" SE", "").replace(" AG", "").split(" ")[0]
                
                target = info.get('targetMeanPrice', 0)
                upside = ((target - current_price) / current_price) * 100 if target and current_price else 0
                rev_growth = info.get('revenueGrowth', 0) 
                earn_growth = info.get('earningsGrowth', 0)
                peg_ratio = info.get('pegRatio') or info.get('trailingPegRatio')
                status = "Unterbewertet" if (upside > 15 and rsi_val < 45) else "Neutral"
                if upside < 0: status = "Überbewertet"

                if rsi_val <= rsi_limit:
                    peg_display = round(peg_ratio, 2) if peg_ratio else "N/A"
                    if peg_ratio is None and info.get('forwardPE', -1) < 0: peg_display = "Verlust"
                    growth_display = f"{round(rev_growth * 100, 1)}%" if rev_growth else "N/A"
                    earn_growth_display = f"{round(earn_growth * 100, 1)}%" if earn_growth else "N/A"
                    target_display = f"{round(target, 2)} {currency}" if target else "N/A"
                    trend_sign = "+" if change_pct > 0 else ""
                    d50_sign = "+" if dist_50 > 0 else ""
                    d200_sign = "+" if dist_200 > 0 else ""
                    bid_display = f"{round(bid, 2)}" if bid else "-"
                    ask_display = f"{round(ask, 2)}" if ask else "-"

                    temp_results.append({
                        "Name": name, "Kürzel": ticker, "Kurs": f"{round(live_price, 2)} {currency}",
                        "Analysten-Ziel": target_display, "Potenzial %": round(upside, 1),
                        "Tages-Trend": f"{trend_sign}{round(change_pct, 2)}%",
                        "RSI (14)": round(float(rsi_val), 1), "Trend-Signal": trend_signal,
                        "Umsatz-Wachst.": growth_display, "Gewinn-Wachst.": earn_growth_display,
                        "PEG": peg_display, "Bewertung": status,
                        "Abst. SMA50": f"{d50_sign}{round(dist_50, 1)}%",
                        "Abst. SMA200": f"{d200_sign}{round(dist_200, 1)}%",
                        "Bid (VK)": bid_display, "Ask (Kauf)": ask_display
                    })
                    temp_news[ticker] = get_google_news(clean_name)
        except Exception: continue
        
        if not auto_refresh: progress_bar.progress((i + 1) / total_tickers)
            
    if not auto_refresh:
        status_text.empty()
        progress_bar.empty()
    
    st.session_state['scan_results'] = temp_results
    st.session_state['scan_news'] = temp_news
    st.session_state['last_update'] = datetime.now().strftime("%H:%M:%S")

# B) ANZEIGE
if st.session_state['scan_results']:
    results = st.session_state['scan_results']
    news_data = st.session_state['scan_news']
    last_up = st.session_state['last_update']
    
    if auto_refresh: st.markdown(f"🟢 **Live-Modus aktiv** | Zuletzt aktualisiert: **{last_up}**")
    else: st.markdown(f"⚪ Manueller Modus | Stand: **{last_up}**")

    st.subheader(f"🌍 Marktanalyse ({len(results)} Treffer)")
    df_res = pd.DataFrame(results)
    
    def style_percent_color(val):
        if isinstance(val, str) and "%" in val:
            try:
                num = float(val.replace('%', '').replace('+', '').strip())
                return 'color: green' if num > 0 else 'color: red'
            except: return ''
        if isinstance(val, (int, float)): return 'color: green' if val > 0 else 'color: red'
        return ''

    def style_trend(val):
        if "GOLDENES" in str(val): return 'color: #006400; font-weight: bold; background-color: #e6ffe6' 
        if "Todeskreuz" in str(val): return 'color: red; font-weight: bold'
        if "Aufwärtstrend" in str(val): return 'color: green'
        if "Abwärtstrend" in str(val): return 'color: red'
        return ''
    def highlight_valuation(val): return 'background-color: #90EE90; color: black' if val == "Unterbewertet" else ''
    def style_rsi(val):
        try:
            if float(val) < 30: return 'color: green; font-weight: bold'
            elif float(val) > 70: return 'color: red'
        except: pass
        return ''
    def style_peg(val):
        if val == "Verlust": return 'color: red'
        try:
            if float(val) > 1.5: return 'color: red'
            elif float(val) > 0: return 'color: green'
        except: pass
        return ''

    display_cols = ["Name", "Kurs", "Analysten-Ziel", "Potenzial %", "Tages-Trend", "RSI (14)", "Trend-Signal", "Umsatz-Wachst.", "Gewinn-Wachst.", "PEG", "Bewertung"]
    
    st.dataframe(df_res[display_cols].style
                    .applymap(style_trend, subset=['Trend-Signal'])
                    .applymap(highlight_valuation, subset=['Bewertung'])
                    .applymap(style_rsi, subset=['RSI (14)'])
                    .applymap(style_peg, subset=['PEG'])
                    .applymap(style_percent_color, subset=['Tages-Trend', 'Umsatz-Wachst.', 'Gewinn-Wachst.', 'Potenzial %']), 
                    use_container_width=True)
    
    st.divider()
    st.subheader("📉 Profi-Chart")
    ticker_list = [r['Kürzel'] for r in results] if results else []
    selected_ticker = st.selectbox("Aktie auswählen:", ticker_list, key="chart_select") if ticker_list else None
    
    if selected_ticker:
        chart_stock = yf.Ticker(selected_ticker)
        chart_df = chart_stock.history(period="2y")
        if not chart_df.empty:
            chart_df['SMA_20'] = chart_df['Close'].rolling(window=20).mean()
            chart_df['Std_Dev'] = chart_df['Close'].rolling(window=20).std()
            chart_df['Oberes Band'] = chart_df['SMA_20'] + (chart_df['Std_Dev'] * 2)
            chart_df['Unteres Band'] = chart_df['SMA_20'] - (chart_df['Std_Dev'] * 2)
            chart_df['SMA 200'] = chart_df['Close'].rolling(window=200).mean()
            chart_df['SMA 50'] = chart_df['Close'].rolling(window=50).mean()
            plot_df = chart_df.iloc[-250:].copy()
            st.line_chart(plot_df[['Close', 'Oberes Band', 'Unteres Band', 'SMA 200', 'SMA 50']])
            
            delta = chart_df['Close'].diff()
            gain = delta.where(delta > 0, 0)
            loss = -delta.where(delta < 0, 0)
            avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
            avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
            rsi_plot = chart_df.iloc[-250:].copy()
            rsi_plot['RSI'] = 100 - (100 / (1 + (avg_gain / avg_loss)))
            rsi_plot['70'] = 70
            rsi_plot['30'] = 30
            st.line_chart(rsi_plot[['RSI', '70', '30']], color=["#0000FF", "#FF0000", "#00FF00"])

    # --- EXPERTEN SECTION (SUBSTACK & WIKI) ---
    if show_experts:
        st.divider()
        st.subheader("🧠 Experten-Briefing (Substack & Wikifolio)")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.info("📊 **Stefan Waldhauser (HGI)**")
            st.markdown("High-Growth-Investing Strategie")
            
            # Buttons für Direktzugriff
            c1, c2 = st.columns(2)
            with c1:
                st.link_button("📈 Zum Wikifolio", "https://www.wikifolio.com/de/de/w/wf00000hgi")
            with c2:
                st.link_button("📝 Zum Blog/Substack", "https://high-tech-investing.de")

            st.write("**Neueste Artikel (RSS):**")
            # Feed von High-Tech-Investing
            wh_news = get_rss_feed("https://high-tech-investing.de/feed/")
            if wh_news:
                for item in wh_news:
                    st.markdown(f"• [{item['title']}]({item['link']})")
            else:
                st.caption("Keine neuen Artikel geladen.")

        with col2:
            st.info("🐻 **Mateusz Szewczyk (Szew)**")
            st.markdown("Data-Driven Tech Investing")
            
            # Buttons
            c3, c4 = st.columns(2)
            with c3:
                # Link zum Haupt-Wikifolio "Data Driven Tech"
                st.link_button("📈 Zum Wikifolio", "https://www.wikifolio.com/de/de/w/wf000szew1")
            with c4:
                st.link_button("📝 Zum Substack", "https://szew.substack.com")

            st.write("**Neueste Substack-Artikel:**")
            # Feed von Szew Substack
            sz_news = get_rss_feed("https://szew.substack.com/feed")
            if sz_news:
                for item in sz_news:
                    st.markdown(f"• [{item['title']}]({item['link']})")
            else:
                st.caption("Keine Artikel geladen.")

    # --- AKTIEN NEWS ---
    st.divider()
    st.subheader("📰 News zur ausgewählten Aktie")
    if news_data and selected_ticker:
        articles = news_data.get(selected_ticker, [])
        if articles:
            for item in articles:
                pub_date = item.get('published', '')
                st.markdown(f"• **[{item['title']}]({item['link']})**")
                st.caption(f"{item['publisher']} | {pub_date}")
        else:
            st.info(f"Keine Google News gefunden. [Suche starten](https://www.google.com/search?q={selected_ticker}+Aktie&tbm=nws)")

if auto_refresh:
    time.sleep(60)
    st.rerun()
