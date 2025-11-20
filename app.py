import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- KONFIGURACIJA STRANICE ---
st.set_page_config(page_title="Rule #1 Dashboard", layout="wide")

# --- CSS STILOVI (Za boje u tablicama) ---
st.markdown("""
<style>
    .metric-card {
        background-color: #1E1E1E;
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 10px;
    }
    .val-dark-green { color: #006400; font-weight: bold; }
    .val-green { color: #4CAF50; font-weight: bold; }
    .val-yellow { color: #FFC107; font-weight: bold; }
    .val-red { color: #FF5252; font-weight: bold; }
    .metric-label { font-size: 0.8rem; color: #aaa; }
    .metric-value { font-size: 1.1rem; font-weight: bold; color: #fff; }
</style>
""", unsafe_allow_html=True)

# --- FUNKCIJE ---
def format_num(num):
    if num is None: return "-"
    if abs(num) >= 1_000_000_000_000: return f"{num / 1_000_000_000_000:.2f}T"
    if abs(num) >= 1_000_000_000: return f"{num / 1_000_000_000:.2f}B"
    elif abs(num) >= 1_000_000: return f"{num / 1_000_000:.2f}M"
    else: return f"{num:.2f}"

def get_color_html(value, type_rule):
    """Funkcija koja određuje boju na temelju tvojih pravila"""
    if value is None: return "white"
    
    if type_rule == "ratio_liquidity": # Quick/Current Ratio (>1.2 G, 0.9-1.2 Y, <0.9 R)
        if value > 1.2: return "#4CAF50" # Green
        elif value >= 0.9: return "#FFC107" # Yellow
        else: return "#FF5252" # Red
        
    elif type_rule == "debt_equity": # Debt/Eq (<1 G, 1-2 Y, >2 R)
        if value < 1: return "#4CAF50"
        elif value <= 2: return "#FFC107"
        else: return "#FF5252"
        
    elif type_rule == "returns": # ROA, ROE, ROIC (>12 DG, 9-12 G, 6-9 Y, <6 R)
        if value > 12: return "#2E7D32" # Dark Green
        elif value > 9: return "#4CAF50" # Light Green
        elif value > 6: return "#FFC107" # Yellow
        else: return "#FF5252" # Red
        
    elif type_rule == "interest_cov": # >1.5 G, 1.15-1.5 Y, <1.15 R
        if value > 1.5: return "#4CAF50"
        elif value >= 1.15: return "#FFC107"
        else: return "#FF5252"
    
    return "white"

@st.cache_data
def get_data(ticker):
    stock = yf.Ticker(ticker)
    return stock.financials, stock.balance_sheet, stock.cashflow, stock.info

def analyze_stock(ticker):
    fin, bal, cf, info = get_data(ticker)
    
    if fin.empty: return None

    results = {}
    score = 0 
    
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
    
    # 5. REPAY LIABILITIES
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
        if shares_now == 0 and 'Ordinary Shares Number' in bal.index:
            shares_now = bal.loc['Ordinary Shares Number'].iloc[current_idx]
        shares_old = shares_now 
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
            passed = True 
            msg = "Nema dividende"
        else:
            passed = cash > div_paid
            msg = f"Cash > Div ({format_num(div_paid)})"
        results['Dividend Safety'] = (passed, msg)
        if passed: score += 1
    except: results['Dividend Safety'] = (False, "N/A")

    return results, score, fin, bal, info, avg_roic

# --- HEADER ---
st.title("🚀 Rule #1 Dashboard")
st.markdown("Profesionalni alat za analizu dionica")

# --- SIDEBAR ---
with st.sidebar:
    st.header("Pretraga")
    ticker = st.text_input("Simbol:", "CRM").upper()
    btn = st.button("Skeniraj Dionicu", type="primary")

# --- GLAVNI DIO ---
if btn or ticker:
    with st.spinner(f'Dohvaćam podatke za {ticker}...'):
        data = analyze_stock(ticker)
        
        if data:
            results, score, fin, bal, info, avg_roic = data
            
            # --- DATA PREPARATION FOR HEADER ---
            # Col 1: Margins & Cash
            p_margin = info.get('profitMargins', 0) * 100 if info.get('profitMargins') else 0
            o_margin = info.get('operatingMargins', 0) * 100 if info.get('operatingMargins') else 0
            g_margin = info.get('grossMargins', 0) * 100 if info.get('grossMargins') else 0
            total_cash = info.get('totalCash', 0)
            total_debt = info.get('totalDebt', 0)
            net_cash = total_cash - total_debt
            div_yield = info.get('dividendYield', 0) * 100 if info.get('dividendYield') else None
            payout = info.get('payoutRatio', 0) * 100 if info.get('payoutRatio') else None

            # Col 2: Ratios (Colors)
            quick_r = info.get('quickRatio', 0)
            curr_r = info.get('currentRatio', 0)
            debt_eq = info.get('debtToEquity', 0) / 100 if info.get('debtToEquity') else 0 # YF gives % often
            roa = info.get('returnOnAssets', 0) * 100 if info.get('returnOnAssets') else 0
            roe = info.get('returnOnEquity', 0) * 100 if info.get('returnOnEquity') else 0
            # Interest Cov calc
            try:
                ebit = fin.loc['EBIT'].iloc[0] if 'EBIT' in fin.index else fin.loc['Pretax Income'].iloc[0]
                int_exp = abs(fin.loc['Interest Expense'].iloc[0]) if 'Interest Expense' in fin.index else 1
                int_cov = ebit / int_exp if int_exp > 0 else 0
            except: int_cov = 0

            # Col 3: Valuation
            mkt_cap = info.get('marketCap', 0)
            eps = info.get('trailingEps', 0)
            pe_ttm = info.get('trailingPE', 0)
            pe_fwd = info.get('forwardPE', 0)
            ps = info.get('priceToSalesTrailing12Months', 0)
            pb = info.get('priceToBook', 0)
            bvps = info.get('bookValue', 0)

            # --- RENDER HEADER COLUMNS ---
            st.markdown("---")
            col_left, col_mid, col_right = st.columns(3)

            # 1. COLUMN (Lijevo - Margine, Cash, Dividende)
            with col_left:
                st.subheader("💵 Margine & Cash")
                st.markdown(f"""
                <div style="line-height: 1.8;">
                    <b>Gross Margin:</b> {g_margin:.2f}%<br>
                    <b>Operating Margin:</b> {o_margin:.2f}%<br>
                    <b>Net Margin:</b> {p_margin:.2f}%<br>
                    <hr style="margin: 5px 0;">
                    <b>Total Cash:</b> {format_num(total_cash)}<br>
                    <b>Total Debt:</b> {format_num(total_debt)}<br>
                    <b>Net Cash:</b> <span style="color: {'#4CAF50' if net_cash>0 else '#FF5252'}">{format_num(net_cash)}</span><br>
                    <hr style="margin: 5px 0;">
                    <b>Dividend Yield:</b> {f"{div_yield:.2f}%" if div_yield else "-"}<br>
                    <b>Payout Ratio:</b> {f"{payout:.2f}%" if payout else "-"}
                </div>
                """, unsafe_allow_html=True)

            # 2. COLUMN (Sredina - Ratios sa BOJAMA)
            with col_mid:
                st.subheader("🛡️ Financijsko Zdravlje")
                st.markdown(f"""
                <div style="line-height: 1.8; font-weight: 500;">
                    Quick Ratio: <span style="color:{get_color_html(quick_r, 'ratio_liquidity')}">{quick_r:.2f}</span><br>
                    Current Ratio: <span style="color:{get_color_html(curr_r, 'ratio_liquidity')}">{curr_r:.2f}</span><br>
                    Debt / Equity: <span style="color:{get_color_html(debt_eq, 'debt_equity')}">{debt_eq:.2f}</span><br>
                    <hr style="margin: 5px 0;">
                    ROA: <span style="color:{get_color_html(roa, 'returns')}">{roa:.2f}%</span><br>
                    ROE: <span style="color:{get_color_html(roe, 'returns')}">{roe:.2f}%</span><br>
                    ROIC (Avg 5y): <span style="color:{get_color_html(avg_roic, 'returns')}">{avg_roic:.2f}%</span><br>
                    Interest Cov: <span style="color:{get_color_html(int_cov, 'interest_cov')}">{int_cov:.2f}</span>
                </div>
                """, unsafe_allow_html=True)

            # 3. COLUMN (Desno - Osnovne Valuacije)
            with col_right:
                st.subheader("🏷️ Valuacija")
                st.markdown(f"""
                <div style="line-height: 1.8;">
                    <b>Market Cap:</b> {format_num(mkt_cap)}<br>
                    <b>Current EPS:</b> ${eps}<br>
                    <hr style="margin: 5px 0;">
                    <b>P/E (TTM):</b> {pe_ttm if pe_ttm else '-'}<br>
                    <b>P/E (Fwd):</b> {pe_fwd if pe_fwd else '-'}<br>
                    <b>Price / Sales:</b> {ps if ps else '-'}<br>
                    <b>Price / Book:</b> {pb if pb else '-'}<br>
                    <b>Book Val/Share:</b> ${bvps}
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown("---")

            # SCORE CARD
            curr_price = info.get('currentPrice', 'N/A')
            c1, c2, c3 = st.columns([1,2,1])
            with c2:
                st.markdown(f"<h1 style='text-align: center; color: #4CAF50; margin-bottom:0;'>SCORE: {score}/10</h1>", unsafe_allow_html=True)
                st.markdown(f"<h3 style='text-align: center; margin-top:0;'>Cijena: ${curr_price}</h3>", unsafe_allow_html=True)

            # TABS
            tab1, tab2, tab3 = st.tabs(["📊 10 Pillars Detaljno", "📈 Grafovi", "📄 Izvještaji"])

            # TAB 1: PILLARS
            with tab1:
                c_left, c_right = st.columns(2)
                def show_res(container, key, label):
                    passed, val = results[key]
                    icon = "✅" if passed else "❌"
                    container.markdown(f"**{icon} {label}**")
                    container.caption(val)
                    container.markdown("---")

                with c_left:
                    st.subheader("Rast & Profitabilnost")
                    show_res(st, 'Revenue Growth', '1. Revenue Growth (5y)')
                    show_res(st, 'Net Income Growth', '2. Net Income Growth (5y)')
                    show_res(st, 'Cash Growth', '3. Cash Growth (5y)')
                    show_res(st, 'ROIC > 9%', '7. ROIC > 9% (Avg)')
                    show_res(st, 'PE Ratio', '6. PE Ratio (< 22.5)')

                with c_right:
                    st.subheader("Bilanca & Vrednovanje")
                    show_res(st, 'Repay Debt', '4. Can Repay Net Debt')
                    show_res(st, 'Repay Liabilities', '5. Can Repay Liabilities')
                    show_res(st, 'Share Buyback', '8. Share Buyback')
                    show_res(st, 'Dividend Safety', '10. Dividend Safety')
                    show_res(st, 'Undervalued (FCFx20)', '9. Valuation (FCF * 20)')

            # TAB 2: GRAFOVI
            with tab2:
                years = fin.columns[::-1]
                
                # GRAF 1
                fig1 = make_subplots(specs=[[{"secondary_y": True}]])
                fig1.add_trace(go.Bar(x=years, y=fin.loc['Total Revenue'][years], name="Revenue", marker_color='#3f51b5'), secondary_y=False)
                fig1.add_trace(go.Scatter(x=years, y=fin.loc['Net Income'][years], name="Net Income", line=dict(color='#4CAF50', width=3)), secondary_y=True)
                fig1.update_layout(title_text="Rast Prihoda i Dobiti", template="plotly_dark")
                st.plotly_chart(fig1, use_container_width=True)

                # GRAF 2
                if 'Total Debt' in bal.index:
                    cash_row = 'Cash And Cash Equivalents' if 'Cash And Cash Equivalents' in bal.index else 'Cash Cash Equivalents And Short Term Investments'
                    fig2 = go.Figure()
                    fig2.add_trace(go.Bar(x=years, y=bal.loc[cash_row][years], name='Cash', marker_color='#4CAF50'))
                    fig2.add_trace(go.Bar(x=years, y=bal.loc['Total Debt'][years], name='Debt', marker_color='#FF5252'))
                    fig2.update_layout(title_text="Keš vs Dug", barmode='group', template="plotly_dark")
                    st.plotly_chart(fig2, use_container_width=True)

            # TAB 3: IZVJEŠTAJI
            with tab3:
                st.write("Izvorni podaci:")
                with st.expander("Income Statement"): st.dataframe(fin)
                with st.expander("Balance Sheet"): st.dataframe(bal)

        else:
            st.error("Nema podataka. Provjeri simbol.")
