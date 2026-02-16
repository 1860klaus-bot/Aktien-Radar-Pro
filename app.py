import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="Aktien-Radar Pro+", page_icon="💎", layout="wide")
st.title("💎 Aktien-Radar Pro+ mit News")

# Seitenleiste
st.sidebar.header("Filter-Einstellungen")
ticker_input = st.sidebar.text_area("Aktien-Liste (Kürzel mit Komma)", "NVDA,TSLA,AMD,AAPL,ANGI,MSFT,AMZN,GOOGL")
rsi_limit = st.sidebar.slider("Max. RSI (14 Tage)", 10, 100, 60)

if st.sidebar.button("🚀 Voll-Analyse starten"):
    tickers = [t.strip().upper() for t in ticker_input.split(",") if t.strip()]
    results = []
    news_data = {} # Speicher für Schlagzeilen
    status_text = st.empty()
    
    for ticker in tickers:
        status_text.text(f"Analysiere Technik, Finanzen & News: {ticker}...")
        try:
            stock = yf.Ticker(ticker)
            # 1. Präziser RSI
            df_hist = stock.history(period="300d")
            if len(df_hist) > 14:
                delta = df_hist['Close'].diff()
                gain = delta.where(delta > 0, 0)
                loss = -delta.where(delta < 0, 0)
                avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
                avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
                rs = avg_gain / avg_loss
                rsi_val = 100 - (100 / (1 + rs)).iloc[-1]
                
                # 2. Fundamentaldaten
                info = stock.info
                current_price = df_hist['Close'].iloc[-1]
                rev_growth = info.get('revenueGrowth', 0) * 100 if info.get('revenueGrowth') else 0
                fwd_pe = info.get('forwardPE', 0)
                target_price = info.get('targetMeanPrice', 0)
                
                # 3. Quartalsgewinn
                try:
                    q_financials = stock.quarterly_financials
                    last_q_profit = q_financials.loc['Net Income'].iloc[0] / 1_000_000
                except:
                    last_q_profit = 0

                # Potenzial & Bewertung
                upside = ((target_price - current_price) / current_price) * 100 if target_price > 0 else 0
                status = "Unterbewertet" if (upside > 15 and rsi_val < 45) else "Neutral"
                if upside < 0: status = "Überbewertet"

                if rsi_val <= rsi_limit:
                    results.append({
                        "Ticker": ticker,
                        "RSI (14)": round(float(rsi_val), 1),
                        "Erw. Gewinn (%)": round(upside, 1),
                        "Bewertung": status,
                        "Letzter Q-Gewinn (Mio $)": round(last_q_profit, 2),
                        "KGV (fwd)": round(fwd_pe, 1) if fwd_pe > 0 else "N/A"
                    })
                    # 4. News speichern
                    news_data[ticker] = stock.news[:3]
        except:
            continue
            
    status_text.empty()
    if results:
        df_res = pd.DataFrame(results)
        
        # Styling & Tabelle
        def highlight_valuation(val):
            return 'background-color: #90EE90; color: black' if val == "Unterbewertet" else ''
        
        st.subheader("📊 Marktanalyse")
        st.dataframe(df_res.style.applymap(highlight_valuation, subset=['Bewertung']), use_container_width=True)
        
        # News-Sektion unter der Tabelle
        st.divider()
        st.subheader("📰 Aktuelle Nachrichten")
        for ticker, news_items in news_data.items():
            with st.expander(f"Nachrichten für {ticker}", expanded=(ticker == "ANGI")):
                if news_items:
                    for item in news_items:
                        st.markdown(f"**[{item['title']}]({item['link']})**")
                        st.caption(f"Quelle: {item.get('publisher', 'Unbekannt')}")
                else:
                    st.write("Keine aktuellen Meldungen gefunden.")
    else:
        st.warning("Keine Treffer unter dem Limit.")
