import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="Aktien-Radar Pro+", page_icon="💎", layout="wide")
st.title("💎 Aktien-Radar Pro+ mit News")

st.sidebar.header("Filter-Einstellungen")
ticker_input = st.sidebar.text_area("Aktien-Liste (Kürzel mit Komma)", "NVDA,TSLA,AMD,AAPL,ANGI,MSFT,AMZN,GOOGL,IAC")
rsi_limit = st.sidebar.slider("Max. RSI (14 Tage)", 10, 100, 87)

if st.sidebar.button("🚀 Voll-Analyse starten"):
    tickers = [t.strip().upper() for t in ticker_input.split(",") if t.strip()]
    results = []
    news_data = {}
    status_text = st.empty()
    
    for ticker in tickers:
        status_text.text(f"Analysiere: {ticker}...")
        try:
            stock = yf.Ticker(ticker)
            df_hist = stock.history(period="300d")
            if len(df_hist) > 14:
                # Exakter RSI
                delta = df_hist['Close'].diff()
                gain = delta.where(delta > 0, 0)
                loss = -delta.where(delta < 0, 0)
                avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
                avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
                rsi_val = 100 - (100 / (1 + (avg_gain / avg_loss))).iloc[-1]
                
                # Finanzen
                info = stock.info
                price = df_hist['Close'].iloc[-1]
                target = info.get('targetMeanPrice', 0)
                upside = ((target - price) / price) * 100 if target > 0 else 0
                
                try:
                    last_q_profit = stock.quarterly_financials.loc['Net Income'].iloc[0] / 1_000_000
                except:
                    last_q_profit = None

                status = "Unterbewertet" if (upside > 15 and rsi_val < 45) else "Neutral"
                if upside < 0: status = "Überbewertet"

                if rsi_val <= rsi_limit:
                    results.append({
                        "Ticker": ticker, "RSI (14)": round(float(rsi_val), 1),
                        "Erw. Gewinn (%)": round(upside, 1), "Bewertung": status,
                        "Letzter Q-Gewinn (Mio $)": round(last_q_profit, 2) if last_q_profit is not None else "N/A",
                        "KGV (fwd)": round(info.get('forwardPE', 0), 1) if info.get('forwardPE', 0) else "N/A"
                    })
                    # Sicherer News-Abruf
                    raw_news = stock.news[:3]
                    news_data[ticker] = raw_news
        except:
            continue
            
    status_text.empty()
    if results:
        st.subheader("📊 Marktanalyse")
        df_res = pd.DataFrame(results)
        st.dataframe(df_res.style.applymap(lambda x: 'background-color: #90EE90; color: black' if x == "Unterbewertet" else '', subset=['Bewertung']), use_container_width=True)
        
        st.divider()
        st.subheader("📰 Aktuelle Nachrichten")
        for ticker, items in news_data.items():
            with st.expander(f"Nachrichten für {ticker}"):
                if items:
                    for item in items:
                        # Hier nutzen wir .get(), damit es nicht mehr zum KeyError kommt
                        title = item.get('title', 'Kein Titel verfügbar')
                        link = item.get('link', '#')
                        st.markdown(f"**[{title}]({link})**")
                else:
                    st.write("Keine News gefunden.")
