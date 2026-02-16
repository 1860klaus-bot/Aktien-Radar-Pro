import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="Aktien-Radar Realtime", page_icon="💎", layout="wide")
st.title("💎 Aktien-Radar: Realtime & Analyse")

# Seitenleiste
st.sidebar.header("Filter-Einstellungen")
ticker_input = st.sidebar.text_area("Aktien-Liste (Kürzel mit Komma)", "NVDA,TSLA,AMD,AAPL,ANGI,MSFT,AMZN,GOOGL,IAC")
rsi_limit = st.sidebar.slider("Max. RSI (14 Tage)", 10, 100, 87)

# Button zum Aktualisieren
if st.sidebar.button("🔄 Kurse & Wachstum prüfen"):
    tickers = [t.strip().upper() for t in ticker_input.split(",") if t.strip()]
    results = []
    news_data = {}
    status_text = st.empty()
    
    for ticker in tickers:
        status_text.text(f"Live-Abfrage: {ticker}...")
        try:
            stock = yf.Ticker(ticker)
            
            # 1. Historie für RSI laden
            df_hist = stock.history(period="300d")
            
            if not df_hist.empty and len(df_hist) > 14:
                # RSI Berechnung (Wilder's Smoothing)
                delta = df_hist['Close'].diff()
                gain = delta.where(delta > 0, 0)
                loss = -delta.where(delta < 0, 0)
                avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
                avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
                rsi_val = 100 - (100 / (1 + (avg_gain / avg_loss))).iloc[-1]
                
                # 2. LIVE-Daten & Fundamentales
                info = stock.info
                
                # Preise
                current_price = info.get('currentPrice') or info.get('regularMarketPrice') or df_hist['Close'].iloc[-1]
                previous_close = info.get('previousClose') or df_hist['Close'].iloc[-2]
                change_pct = ((current_price - previous_close) / previous_close) * 100 if current_price and previous_close else 0
                
                # Kursziele & Potenzial
                target = info.get('targetMeanPrice', 0)
                upside = ((target - current_price) / current_price) * 100 if target and current_price else 0
                
                # Umsatz & Wachstum (Zukunft)
                rev_growth = info.get('revenueGrowth', 0) # Aktuelles Wachstum (YOY)
                peg_ratio = info.get('pegRatio', None)    # Bewertung relativ zum zukünftigen Wachstum
                
                # Gewinn (letztes Quartal)
                try:
                    last_q_profit = stock.quarterly_financials.loc['Net Income'].iloc[0] / 1_000_000
                except:
                    last_q_profit = None

                # Bewertung-Status
                status = "Unterbewertet" if (upside > 15 and rsi_val < 45) else "Neutral"
                if upside < 0: status = "Überbewertet"

                # Daten aufbereiten
                if rsi_val <= rsi_limit:
                    peg_display = round(peg_ratio, 2) if peg_ratio else "N/A"
                    growth_display = f"{round(rev_growth * 100, 2)}%" if rev_growth else "N/A"
                    
                    results.append({
                        "Ticker": ticker, 
                        "Kurs ($)": round(current_price, 2),
                        "Trend": f"{round(change_pct, 2)}%",
                        "RSI (14)": round(float(rsi_val), 1),
                        "Umsatz-Wachstum": growth_display,  # NEU
                        "PEG Ratio (Zukunft)": peg_display, # NEU
                        "Erw. Gewinn (%)": round(upside, 1), 
                        "Bewertung": status,
                        "Q-Gewinn (Mio $)": round(last_q_profit, 2) if last_q_profit is not None else "N/A",
                    })
                    
                    # News-Abruf
                    try:
                        ticker_news = stock.news
                        if ticker_news:
                            news_data[ticker] = ticker_news[:3]
                        else:
                            news_data[ticker] = []
                    except:
                        news_data[ticker] = []
        except Exception as e:
            continue
            
    status_text.empty()
    
    if results:
        st.subheader("📊 Live-Marktübersicht")
        df_res = pd.DataFrame(results)
        
        # Styling
        def style_change(val):
            if isinstance(val, str) and "%" in val:
                num = float(val.strip('%'))
                return 'color: green' if num > 0 else 'color: red'
            return ''
            
        def highlight_valuation(val):
            return 'background-color: #90EE90; color: black' if val == "Unterbewertet" else ''

        st.dataframe(df_res.style
                     .applymap(style_change, subset=['Trend'])
                     .applymap(highlight_valuation, subset=['Bewertung']), 
                     use_container_width=True)
        
        st.divider()
        st.subheader("📰 Aktuelle Nachrichten")
        for ticker in news_data:
            with st.expander(f"Nachrichten für {ticker}"):
                articles = news_data[ticker]
                if articles:
                    for item in articles:
                        t = item.get('title') or item.get('headline') or "News"
                        l = item.get('link') or item.get('url') or f"https://finance.yahoo.com/quote/{ticker}"
                        pub = item.get('publisher') or "Yahoo"
                        st.markdown(f"**[{t}]({l})**")
                        st.caption(f"Quelle: {pub}")
                else:
                    st.info(f"Keine News. [Zu Yahoo Finance](https://finance.yahoo.com/quote/{ticker})")
    else:
        st.warning("Keine Treffer unter dem Limit.")
