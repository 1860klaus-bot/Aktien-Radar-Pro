import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="Aktien-Radar Pro", page_icon="💎", layout="wide")
st.title("💎 Aktien-Radar Pro")

# Seitenleiste
st.sidebar.header("Filter-Einstellungen")
ticker_input = st.sidebar.text_area("Aktien-Liste (Kürzel mit Komma)", "NVDA,TSLA,AMD,AAPL,ANGI,MSFT,AMZN,GOOGL")
rsi_limit = st.sidebar.slider("Max. RSI (14 Tage)", 10, 100, 60)

if st.sidebar.button("🚀 Profi-Analyse starten"):
    tickers = [t.strip().upper() for t in ticker_input.split(",") if t.strip()]
    results = []
    status_text = st.empty()
    
    for ticker in tickers:
        status_text.text(f"Analysiere Fundamentaldaten: {ticker}...")
        try:
            stock = yf.Ticker(ticker)
            # 1. Präziser RSI (300 Tage Historie)
            df = stock.history(period="300d")
            if len(df) > 14:
                delta = df['Close'].diff()
                gain = delta.where(delta > 0, 0)
                loss = -delta.where(delta < 0, 0)
                avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
                avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
                rs = avg_gain / avg_loss
                rsi_val = 100 - (100 / (1 + rs)).iloc[-1]
                
                # 2. Fundamentaldaten & Analysten
                info = stock.info
                current_price = df['Close'].iloc[-1]
                rev_growth = info.get('revenueGrowth', 0) * 100 if info.get('revenueGrowth') else 0
                fwd_pe = info.get('forwardPE', 0)
                target_price = info.get('targetMeanPrice', 0) # Erwartetes Kursziel
                
                # Potenzial berechnen
                upside = 0
                if target_price and target_price > 0:
                    upside = ((target_price - current_price) / current_price) * 100
                
                # Bewertung-Logik (Einfach)
                status = "Neutral"
                if upside > 15 and rsi_val < 40:
                    status = "Unterbewertet (Kaufchance)"
                elif upside < 0 or (fwd_pe > 50 and rsi_val > 70):
                    status = "Überbewertet (Vorsicht)"
                elif upside > 0:
                    status = "Fair bewertet / Potenzial"

                if rsi_val <= rsi_limit:
                    results.append({
                        "Ticker": ticker,
                        "Kurs ($)": round(current_price, 2),
                        "RSI (14)": round(float(rsi_val), 1),
                        "Umsatz-Wachst.": f"{round(rev_growth, 1)}%",
                        "KGV (fwd)": round(fwd_pe, 1) if fwd_pe > 0 else "N/A",
                        "Analysten-Ziel ($)": round(target_price, 2) if target_price > 0 else "N/A",
                        "Erw. Gewinn (%)": f"{round(upside, 1)}%",
                        "Bewertung": status
                    })
        except:
            continue
            
    status_text.empty()
    if results:
        df_res = pd.DataFrame(results)
        # Tabelle anzeigen mit farblicher Hervorhebung (optional)
        st.table(df_res)
    else:
        st.warning("Keine Treffer unter dem eingestellten RSI-Limit.")
