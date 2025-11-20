import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- KONFIGURACIJA STRANICE ---
st.set_page_config(page_title="Rule #1 Skener 2.0", layout="wide")

# --- FUNKCIJE ---
def format_num(num):
    if abs(num) >= 1_000_000_000: return f"{num / 1_000_000_000:.2f}B"
    elif abs(num) >= 1_000_000: return f"{num / 1_000_000:.2f}M"
    else: return f"{num:.2f}"

@st.cache_data
def get_data(ticker):
    stock = yf.Ticker(ticker)
    return stock.financials, stock.balance_sheet, stock.cashflow, stock.info

def analyze_stock(ticker):
    fin, bal, cf, info = get_data(ticker)
    
    if fin.empty: return None

    results = {}
    score = 0 # Ovdje brojimo bodove (0 do 10)
    
    years_count = min(5, len(fin.columns))
    current_idx = 0
    old_idx = years_count - 1

    # 1. REVENUE GROWTH
    try:
        rev_now = fin.iloc[0, current_idx]
        rev_old = fin.iloc[0, old_idx]
        growth = ((rev_now - rev_old) / rev_old) * 100
        passed = growth > 0
        results['Revenue Growth'] = (passed, f"{growth:.1f}%")
        if passed: score += 1
    except: results['Revenue Growth'] = (False, "N/A")

    # 2. NET INCOME GROWTH
    try:
        ni_now = fin.loc['Net Income'].iloc[current_idx]
        ni_old = fin.loc['Net Income'].iloc[old_idx]
        growth = ((ni_now - ni_old) / abs(ni_old)) * 100
        passed = growth > 0
        results['Net Income Growth'] = (passed, f"{growth:.1f}%")
        if passed: score += 1
    except: results['Net Income Growth'] = (False, "N/A")

    # 3. CASH GROWTH
    try:
        cash_row = 'Cash And Cash Equivalents' if 'Cash And Cash Equivalents' in bal.index else 'Cash Cash Equivalents And Short Term Investments'
        cash_now = bal.loc[cash_row].iloc[current_idx]
        cash_old = bal.loc[cash_row].iloc[old_idx]
        growth = ((cash_now - cash_old) / abs(cash_old)) * 100
        passed = growth > 0
        results['Cash Growth'] = (passed, f"{growth:.1f}%")
        if passed: score += 1
    except: results['Cash Growth'] = (False, "N/A")

    # 4. REPAY DEBT
    try:
        debt = bal.loc['Total Debt'].iloc[current_idx] if 'Total Debt' in bal.index else 0
        cash = bal.loc[cash_row].iloc[current_idx]
        passed = cash >= debt
        results['Repay Debt'] = (passed, f"Cash: {format_num(cash)} vs Debt: {format_num(debt)}")
        if passed: score += 1
    except: results['Repay Debt'] = (False, "N/A")
    
    # 5. REPAY LIABILITIES (Avg Non-Current)
    try:
        liab_row = 'Total Non Current Liabilities Net Minority Interest' if 'Total Non Current Liabilities Net Minority Interest' in bal.index else 'Total Non Current Liabilities'
        if liab_row in bal.index:
            avg_liab = bal.loc[liab_row].iloc[:years_count].mean()
            cash = bal.loc[cash_row].iloc[current_idx]
            passed = cash >= avg_liab
            results['Repay Liabilities'] = (passed, f"Cash > Avg Liab ({format_num(avg_liab)})")
            if passed: score += 1
        else: results['Repay Liabilities'] = (False, "N/A")
    except: results['Repay Liabilities'] = (False, "Err")

    # 6. PE < 22.5
    try:
        pe = info.get('trailingPE', 0)
        if pe is None: pe = 0
        passed = 0 < pe < 22.5
        results['PE Ratio'] = (passed, f"{pe:.2f}")
        if passed: score += 1
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
        passed = avg_roic > 9
        results['ROIC > 9%'] = (passed, f"{avg_roic:.1f}%")
        if passed: score += 1
    except: results['ROIC > 9%'] = (False, "N/A")
    
    # 8. SHARE BUYBACK
    try:
        shares_now = info.get('sharesOutstanding', 0)
        # Fallback na balancu ako info fali
        if shares_now == 0 and 'Ordinary Shares Number' in bal.index:
            shares_now = bal.loc['Ordinary Shares Number'].iloc[current_idx]
            
        shares_old = shares_now # default
        if 'Ordinary Shares Number' in bal.index:
            shares_old = bal.loc['Ordinary Shares Number'].iloc[old_idx]
            
        passed = shares_now <= shares_old
        results['Share Buyback'] = (passed, f"{format_num(shares_old)} -> {format_num(shares_now)}")
        if passed: score += 1
    except: results['Share Buyback'] = (False, "N/A")

    # 9. VALUATION (FCF * 20)
    try:
        fcf_avg = 0
        if 'Free Cash Flow' in cf.index:
             fcf_avg = cf.loc['Free Cash Flow'].iloc[:years_count].mean()
        elif 'Operating Cash Flow' in cf.index and 'Capital Expenditure' in cf.index:
             op_cash = cf.loc['Operating Cash Flow'].iloc[:years_count].mean()
             capex = cf.loc['Capital Expenditure'].iloc[:years_count].mean()
             fcf_avg = op_cash + capex
        
        fair_val = fcf_avg * 20
        mkt_cap = info.get('marketCap', 0)
        passed = fair_val > mkt_cap
        results['Undervalued (FCFx20)'] = (passed, f"Fair: {format_num(fair_val)}")
        if passed: score += 1
    except: results['Undervalued (FCFx20)'] = (False, "N/A")
    
    # 10. DIVIDEND SAFETY
    try:
        div_paid = abs(cf.loc['Cash Dividends Paid'].iloc[current_idx]) if 'Cash Dividends Paid' in cf.index else 0
        cash = bal.loc[cash_row].iloc[current_idx]
        if div_paid == 0:
            passed = True # Nema dividende = sigurno (neutralno)
            msg = "Nema dividende"
        else:
            passed = cash > div_paid
            msg = f"Cash > Div ({format_num(div_paid)})"
        
        results['Dividend Safety'] = (passed, msg)
        if passed: score += 1
    except: results['Dividend Safety'] = (False, "N/A")

    return results, score, fin, bal, info

# --- HEADER ---
st.title("🚀 Rule #1 Skener 2.0")
st.markdown("Napredna analiza dionica s automatskim bodovanjem")

# --- SIDEBAR INPUT ---
with st.sidebar:
    st.header("Pretraga")
    ticker = st.text_input("Simbol:", "CRM").upper()
    btn = st.button("Skeniraj Dionicu", type="primary")
    st.markdown("---")
    st.markdown("💡 **Savjet:** Upiši US simbole (CRM, AAPL, TSLA, GOOGL).")

# --- GLAVNI DIO ---
if btn or ticker:
    with st.spinner(f'Analiziram {ticker}...'):
        data = analyze_stock(ticker)
        
        if data:
            results, score, fin, bal, info = data
            
            # SCORE CARD
            curr_price = info.get('currentPrice', 'N/A')
            
            col_score1, col_score2, col_score3 = st.columns([1,2,1])
            with col_score2:
                st.markdown(f"<h1 style='text-align: center; color: #4CAF50;'>SCORE: {score}/10</h1>", unsafe_allow_html=True)
                st.markdown(f"<h3 style='text-align: center;'>Cijena: ${curr_price}</h3>", unsafe_allow_html=True)

            # TABS
            tab1, tab2, tab3 = st.tabs(["📊 10 Pillars Analiza", "📈 Interaktivni Grafovi", "📄 Izvještaji"])

            # TAB 1: PILLARS
            with tab1:
                c1, c2 = st.columns(2)
                
                # Helper za prikaz
                def show_res(container, key, label):
                    passed, val = results[key]
                    icon = "✅" if passed else "❌"
                    container.markdown(f"**{icon} {label}**")
                    container.caption(val)
                    container.markdown("---")

                with c1:
                    st.subheader("Rast & Profitabilnost")
                    show_res(st, 'Revenue Growth', '1. Revenue Growth (5y)')
                    show_res(st, 'Net Income Growth', '2. Net Income Growth (5y)')
                    show_res(st, 'Cash Growth', '3. Cash Growth (5y)')
                    show_res(st, 'ROIC > 9%', '7. ROIC > 9% (Avg)')
                    show_res(st, 'PE Ratio', '6. PE Ratio (< 22.5)')

                with c2:
                    st.subheader("Bilanca & Vrednovanje")
                    show_res(st, 'Repay Debt', '4. Can Repay Net Debt')
                    show_res(st, 'Repay Liabilities', '5. Can Repay Liabilities')
                    show_res(st, 'Share Buyback', '8. Share Buyback')
                    show_res(st, 'Dividend Safety', '10. Dividend Safety')
                    show_res(st, 'Undervalued (FCFx20)', '9. Valuation (FCF * 20)')

            # TAB 2: GRAFOVI (PLOTLY)
            with tab2:
                years = fin.columns[::-1] # Od najstarije
                
                # GRAF 1: Revenue vs Net Income
                fig1 = make_subplots(specs=[[{"secondary_y": True}]])
                fig1.add_trace(go.Bar(x=years, y=fin.loc['Total Revenue'][years], name="Revenue", marker_color='blue'), secondary_y=False)
                fig1.add_trace(go.Scatter(x=years, y=fin.loc['Net Income'][years], name="Net Income", line=dict(color='green', width=3)), secondary_y=True)
                fig1.update_layout(title_text="Rast Prihoda (Stupci) i Dobiti (Linija)")
                st.plotly_chart(fig1, use_container_width=True)

                # GRAF 2: Cash vs Debt
                if 'Total Debt' in bal.index:
                    cash_row = 'Cash And Cash Equivalents' if 'Cash And Cash Equivalents' in bal.index else 'Cash Cash Equivalents And Short Term Investments'
                    fig2 = go.Figure()
                    fig2.add_trace(go.Bar(x=years, y=bal.loc[cash_row][years], name='Cash', marker_color='green'))
                    fig2.add_trace(go.Bar(x=years, y=bal.loc['Total Debt'][years], name='Debt', marker_color='red'))
                    fig2.update_layout(title_text="Financijska Snaga: Keš vs Dug", barmode='group')
                    st.plotly_chart(fig2, use_container_width=True)

                # GRAF 3: VALUATION GAUGE
                # Pojednostavljena vizualizacija trenutnog PE
                pe = info.get('trailingPE', 0)
                fig3 = go.Figure(go.Indicator(
                    mode = "gauge+number",
                    value = pe,
                    title = {'text': "P/E Ratio (Manje je bolje)"},
                    gauge = {
                        'axis': {'range': [0, 50]},
                        'bar': {'color': "black"},
                        'steps': [
                            {'range': [0, 15], 'color': "lightgreen"},
                            {'range': [15, 25], 'color': "yellow"},
                            {'range': [25, 50], 'color': "red"}],
                        'threshold': {
                            'line': {'color': "blue", 'width': 4},
                            'thickness': 0.75,
                            'value': 22.5}}))
                st.plotly_chart(fig3, use_container_width=True)

            # TAB 3: IZVJEŠTAJI
            with tab3:
                st.write("Ovdje su sirovi podaci ako želiš dublje kopati:")
                with st.expander("Prikaži Income Statement"):
                    st.dataframe(fin)
                with st.expander("Prikaži Balance Sheet"):
                    st.dataframe(bal)

        else:
            st.error("Podaci nisu pronađeni. Provjeri simbol ili pokušaj kasnije.")
