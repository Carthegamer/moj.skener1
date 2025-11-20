import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="Tehnička Analiza", layout="wide")

st.title("📉 Tehnička Analiza & Tajming")

# --- INPUT ---
c1, c2 = st.columns([3, 1])
with c1:
    ticker = st.text_input("Simbol:", "CRM").upper()
with c2:
    period = st.selectbox("Period:", ["1y", "2y", "5y"], index=1)

if ticker:
    # Dohvat podataka
    stock = yf.Ticker(ticker)
    hist = stock.history(period=period)
    
    if not hist.empty:
        # --- IZRAČUN INDIKATORA ---
        # SMA (Simple Moving Average)
        hist['SMA_50'] = hist['Close'].rolling(window=50).mean()
        hist['SMA_200'] = hist['Close'].rolling(window=200).mean()
        
        # RSI (Relative Strength Index)
        delta = hist['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        hist['RSI'] = 100 - (100 / (1 + rs))

        # Trenutna cijena
        curr_price = hist['Close'].iloc[-1]
        
        # --- GRAF (PLOTLY) ---
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                            vertical_spacing=0.05, row_heights=[0.7, 0.3])

        # 1. Candlestick
        fig.add_trace(go.Candlestick(x=hist.index,
                        open=hist['Open'], high=hist['High'],
                        low=hist['Low'], close=hist['Close'], name='Cijena'), row=1, col=1)
        
        # SMA Linije
        fig.add_trace(go.Scatter(x=hist.index, y=hist['SMA_50'], line=dict(color='blue', width=1), name='SMA 50'), row=1, col=1)
        fig.add_trace(go.Scatter(x=hist.index, y=hist['SMA_200'], line=dict(color='red', width=2), name='SMA 200'), row=1, col=1)

        # 2. RSI
        fig.add_trace(go.Scatter(x=hist.index, y=hist['RSI'], line=dict(color='purple', width=1), name='RSI'), row=2, col=1)
        
        # RSI Granice
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)

        fig.update_layout(
            title=f"Analiza trenda: {ticker} (${curr_price:.2f})",
            xaxis_rangeslider_visible=False,
            height=700,
            template="plotly_dark"
        )
        
        st.plotly_chart(fig, use_container_width=True)

        # --- SIGNAL BOX ---
        rsi_now = hist['RSI'].iloc[-1]
        sma_200_now = hist['SMA_200'].iloc[-1]
        
        col1, col2 = st.columns(2)
        with col1:
            st.info(f"**RSI (14): {rsi_now:.2f}**\n\n"
                    "• < 30: Preprodano (Moguća kupnja)\n"
                    "• > 70: Prekupljeno (Moguća prodaja)")
        with col2:
            trend = "UZLAZNI (Bullish)" if curr_price > sma_200_now else "SILAZNI (Bearish)"
            st.warning(f"**Trend (SMA 200): {trend}**\n\n"
                       f"Cijena je {'IZNAD' if curr_price > sma_200_now else 'ISPOD'} linije dugoročnog trenda.")

    else:
        st.error("Nema podataka.")
