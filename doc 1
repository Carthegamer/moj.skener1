import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# --- FUNKCIJE ZA ANALIZU ---
def format_num(num):
    if abs(num) >= 1_000_000_000: return f"{num / 1_000_000_000:.2f}B"
    elif abs(num) >= 1_000_000: return f"{num / 1_000_000:.2f}M"
    else: return f"{num:.2f}"

def analyze_stock(ticker):
    stock = yf.Ticker(ticker)
    fin = stock.financials
    bal = stock.balance_sheet
    cf = stock.cashflow
    info = stock.info
    
    if fin.empty: return None, None, None, None

    # Podaci za 10 Pillars
    results = {}
    
    # Uzimamo zadnjih 5 godina (ili manje ako nema)
    years_count = min(5, len(fin.columns))
    current_idx = 0
    old_idx = years_count - 1

    # 1. Revenue Growth
    try:
        rev_now = fin.iloc[0, current_idx]
        rev_old = fin.iloc[0, old_idx]
        growth = ((rev_now - rev_old) / rev_old) * 100
        results['Revenue Growth'] = (growth > 0, f"{growth:.1f}%")
    except: results['Revenue Growth'] = (False, "N/A")

    # 2. Net Income Growth
    try:
        ni_now = fin.loc['Net Income'].iloc[current_idx]
        ni_old = fin.loc['Net Income'].iloc[old_idx]
        growth = ((ni_now - ni_old) / abs(ni_old)) * 100
        results['Net Income Growth'] = (growth > 0, f"{growth:.1f}%")
    except: results['Net Income Growth'] = (False, "N/A")

    # 3. Cash Growth
    try:
        cash_row = 'Cash And Cash Equivalents' if 'Cash And Cash Equivalents' in bal.index else 'Cash Cash Equivalents And Short Term Investments'
        cash_now = bal.loc[cash_row].iloc[current_idx]
        cash_old = bal.loc[cash_row].iloc[old_idx]
        growth = ((cash_now - cash_old) / abs(cash_old)) * 100
        results['Cash Growth'] = (growth > 0, f"{growth:.1f}%")
    except: results['Cash Growth'] = (False, "N/A")

    # 4. Repay Debt (Cash vs Total Debt)
    try:
        debt = bal.loc['Total Debt'].iloc[current_idx] if 'Total Debt' in bal.index else 0
        cash = bal.loc[cash_row].iloc[current_idx]
        results['Repay Debt'] = (cash >= debt, f"Cash: {format_num(cash)} vs Debt: {format_num(debt)}")
    except: results['Repay Debt'] = (False, "N/A")

    # 6. PE < 22.5
    try:
        pe = info.get('trailingPE', 0)
        if pe is None: pe = 0
        results['PE Ratio'] = (0 < pe < 22.5, f"{pe:.2f}")
    except: results['PE Ratio'] = (False, "N/A")

    # 7. ROIC > 9%
    try:
        roic_sum = 0
        count = 0
        for i in range(years_count):
            try:
                ebit = fin.loc['EBIT'].iloc[i] if 'EBIT' in fin.index else fin.loc['Pretax Income'].iloc[i]
                equity = bal.loc['Stockholders Equity'].iloc[i]
                debt = bal.loc['Total Debt'].iloc[i] if 'Total Debt' in bal.index else 0
                roic_sum += (ebit / (equity + debt)) * 100
                count += 1
            except: pass
        avg_roic = roic_sum / count if count > 0 else 0
        results['ROIC > 9%'] = (avg_roic > 9, f"{avg_roic:.1f}%")
    except: results['ROIC > 9%'] = (False, "N/A")

    return results, fin, bal, info

# --- WEB SUČELJE ---
st.set_page_config(page_title="Rule #1 Skener", layout="wide")

st.title("📊 Rule #1 Investicijski Skener")
st.markdown("Analiza dionica u 10 stupova + Vizualizacija")

ticker = st.text_input("Upiši simbol dionice (npr. CRM, AAPL, MSFT):", "").upper()

if st.button("Analiziraj") and ticker:
    with st.spinner(f'Analiziram {ticker}...'):
        results, fin, bal, info = analyze_stock(ticker)
        
        if results:
            st.header(f"Rezultati za {ticker}")
            
            # Prikaz metrika u stupcima
            col1, col2, col3 = st.columns(3)
            
            # Prikazujemo rezultate (Zeleno/Crveno)
            def show_metric(col, label, data):
                passed, val = data
                color = "normal" if passed else "off" # Streamlit delta logic
                col.metric(label=label, value=val, delta="✅ PASS" if passed else "❌ FAIL", delta_color=color)

            show_metric(col1, "Revenue Growth (5y)", results['Revenue Growth'])
            show_metric(col2, "Net Income Growth (5y)", results['Net Income Growth'])
            show_metric(col3, "Cash Growth (5y)", results['Cash Growth'])
            
            col1, col2, col3 = st.columns(3)
            show_metric(col1, "Can Repay Debt", results['Repay Debt'])
            show_metric(col2, "P/E Ratio (< 22.5)", results['PE Ratio'])
            show_metric(col3, "Avg ROIC (> 9%)", results['ROIC > 9%'])

            # --- GRAFOVI ---
            st.markdown("---")
            st.subheader("📈 Vizualna Analiza")
            
            tab1, tab2 = st.tabs(["Rast Prihoda", "Cash vs Debt"])
            
            # Priprema podataka za grafove (obrnuti redoslijed godina)
            years = fin.columns[::-1]
            rev_data = fin.loc['Total Revenue'][years]
            net_inc_data = fin.loc['Net Income'][years]
            
            with tab1:
                fig, ax = plt.subplots(figsize=(10, 4))
                ax.plot(years, rev_data, label='Revenue', marker='o')
                ax.plot(years, net_inc_data, label='Net Income', marker='o')
                ax.set_title("Prihod i Dobit")
                ax.legend()
                st.pyplot(fig)

            with tab2:
                # Pokusaj naci cash/debt redove
                cash_row = 'Cash And Cash Equivalents' if 'Cash And Cash Equivalents' in bal.index else 'Cash Cash Equivalents And Short Term Investments'
                if cash_row in bal.index and 'Total Debt' in bal.index:
                    cash_data = bal.loc[cash_row][years]
                    debt_data = bal.loc['Total Debt'][years]
                    
                    fig, ax = plt.subplots(figsize=(10, 4))
                    width = 0.35
                    x = np.arange(len(years))
                    ax.bar(x - width/2, cash_data, width, label='Cash', color='green')
                    ax.bar(x + width/2, debt_data, width, label='Debt', color='red')
                    ax.set_xticks(x)
                    ax.set_xticklabels([y.year for y in years])
                    ax.legend()
                    st.pyplot(fig)
                else:
                    st.warning("Nema dovoljno podataka za Cash/Debt graf.")
        else:
            st.error("Nema podataka ili krivi simbol.")
