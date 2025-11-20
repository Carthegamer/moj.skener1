import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# --- POSTAVKE ---
st.set_page_config(page_title="Rule #1 Dashboard", layout="wide")

# --- CSS DIZAJN ---
st.markdown("""
<style>
    .metric-box { background-color: #1E1E1E; padding: 15px; border-radius: 8px; border: 1px solid #333; margin-bottom: 10px; font-size: 0.95rem; color: #eee; }
    .big-price { font-size: 3.5rem; font-weight: 800; margin: 0; line-height: 1; }
    .big-ticker { font-size: 1.4rem; color: #aaa; font-weight: 600; }
    .l-green { color: #69F0AE; font-weight: bold; } 
    .d-green { color: #00C853; font-weight: bold; } 
    .yellow { color: #FFD740; font-weight: bold; }  
    .red { color: #FF5252; font-weight: bold; }     
    .magic-box { border: 2px solid #4CAF50; padding: 25px; border-radius: 12px; background-color: #1a1a1a; margin-top: 20px; }
</style>
""", unsafe_allow_html=True)

# --- FUNKCIJE ---
def format_num(num):
    if num is None: return "-"
    if abs(num) >= 1_000_000_000_000: return f"{num / 1_000_000_000_000:.2f}T"
    if abs(num) >= 1_000_000_000: return f"{num / 1_000_000_000:.2f}B"
    elif abs(num) >= 1_000_000: return f"{num / 1_000_000:.2f}M"
    else: return f"{num:.2f}"

def get_color_class(value, rule_type):
    if value is None: return "white"
    if rule_type == "liquidity": return "l-green" if value > 1.2 else "yellow" if value >= 0.9 else "red"
    elif rule_type == "debt": return "l-green" if value < 1 else "yellow" if value <= 2 else "red"
    elif rule_type == "returns": return "d-green" if value >= 12 else "l-green" if value >= 9 else "yellow" if value >= 6 else "red"
    elif rule_type == "int_cov": return "l-green" if value >= 1.5 else "yellow" if value >= 1.15 else "red"
    return "white"

def calculate_dcf(start_val, growth_rate, discount_rate, terminal_multiple, years=10):
    current = start_val
    discounted_sum = 0
    for i in range(1, years + 1):
        current = current * (1 + growth_rate/100)
        discounted = current / ((1 + discount_rate/100) ** i)
        discounted_sum += discounted
    terminal_val = current * terminal_multiple
    terminal_discounted = terminal_val / ((1 + discount_rate/100) ** years)
    return discounted_sum + terminal_discounted

@st.cache_data
def get_data(ticker):
    stock = yf.Ticker(ticker)
    return stock.financials, stock.balance_sheet, stock.cashflow, stock.quarterly_financials, stock.quarterly_balance_sheet, stock.quarterly_cashflow, stock.info

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Dashboard Postavke")
    ticker = st.text_input("Simbol:", "CRM").upper()
    graph_period = st.radio("Grafovi:", ["Godišnje", "Kvartalno"])
    btn = st.button("Skeniraj", type="primary")

# --- GLAVNI DIO ---
if btn or ticker:
    with st.spinner(f'Analiziram {ticker}...'):
        fin_y, bal_y, cf_y, fin_q, bal_q, cf_q, info = get_data(ticker)
        
        if not fin_y.empty:
            if graph_period == "Kvartalno": fin_ch, bal_ch, cf_ch = fin_q, bal_q, cf_q
            else: fin_ch, bal_ch, cf_ch = fin_y, bal_y, cf_y
            
            fin, bal, cf = fin_y, bal_y, cf_y
            curr_price = info.get('currentPrice', 0)
            price_color = "#4CAF50" if curr_price >= info.get('previousClose', 0) else "#FF5252"

            # HEADER
            c_head1, c_head2 = st.columns([2, 1])
            with c_head1:
                st.markdown(f"""<div><span class="big-ticker">{ticker} / USD</span><br><span class="big-price" style="color:{price_color}">${curr_price}</span></div>""", unsafe_allow_html=True)
            
            st.markdown("---")

            # METRIKE (3 Stupca)
            c1, c2, c3 = st.columns(3)
            
            # Podaci za metrike
            pm = info.get('profitMargins', 0)*100 if info.get('profitMargins') else 0
            om = info.get('operatingMargins', 0)*100 if info.get('operatingMargins') else 0
            gm = info.get('grossMargins', 0)*100 if info.get('grossMargins') else 0
            
            total_cash = info.get('totalCash', 0)
            ltd_row = 'Long Term Debt' if 'Long Term Debt' in bal.index else 'Long Term Debt And Capital Lease Obligation'
            lt_debt = bal.loc[ltd_row].iloc[0] if ltd_row in bal.index else 0
            net_cash = total_cash - lt_debt
            dy = info.get('dividendYield', 0)*100 if info.get('dividendYield') else None
            
            with c1:
                st.markdown(f"""<div class="metric-box"><b>Net Margin:</b> {pm:.2f}% | <b>Op:</b> {om:.2f}%<br><b>Total Cash:</b> {format_num(total_cash)}<br><b>L.T. Debt:</b> {format_num(lt_debt)}<br><b>Net Cash:</b> <span style="color:{'#4CAF50' if net_cash>0 else '#FF5252'}">{format_num(net_cash)}</span></div>""", unsafe_allow_html=True)

            qr = info.get('quickRatio', 0)
            cr = info.get('currentRatio', 0)
            de = info.get('debtToEquity', 0)/100 if info.get('debtToEquity') else 0
            roa = info.get('returnOnAssets', 0)*100 if info.get('returnOnAssets') else 0
            roe = info.get('returnOnEquity', 0)*100 if info.get('returnOnEquity') else 0
            
            with c2:
                st.markdown(f"""<div class="metric-box">Quick: <span class="{get_color_class(qr,'liquidity')}">{qr:.2f}</span> | Curr: <span class="{get_color_class(cr,'liquidity')}">{cr:.2f}</span><br>Debt/Eq: <span class="{get_color_class(de,'debt')}">{de:.2f}</span><br>ROA: <span class="{get_color_class(roa,'returns')}">{roa:.1f}%</span> | ROE: <span class="{get_color_class(roe,'returns')}">{roe:.1f}%</span></div>""", unsafe_allow_html=True)

            mkt_cap = info.get('marketCap', 0)
            eps = info.get('trailingEps', 0)
            pe = info.get('trailingPE', 0)
            pe_formatted = f"{pe:.2f}" if pe else "-"
            
            with c3:
                st.markdown(f"""<div class="metric-box"><b>Mkt Cap:</b> {format_num(mkt_cap)}<br><b>EPS:</b> ${eps}<br><b>P/E:</b> {pe_formatted}</div>""", unsafe_allow_html=True)

            # 10 PILLARS
            st.subheader("🏛️ 10 Pillars Analiza")
            pillars = {}
            
            # Logika izračuna
            try: pillars['Revenue Growth'] = (((fin.iloc[0,0]-fin.iloc[0,-1])/fin.iloc[0,-1]) > 0, "")
            except: pillars['Revenue Growth'] = (False, "")
            try: pillars['Net Inc Growth'] = (((fin.loc['Net Income'].iloc[0]-fin.loc['Net Income'].iloc[-1])/abs(fin.loc['Net Income'].iloc[-1])) > 0, "")
            except: pillars['Net Inc Growth'] = (False, "")
            try: 
                c_row = 'Cash And Cash Equivalents' if 'Cash And Cash Equivalents' in bal.index else 'Cash Cash Equivalents And Short Term Investments'
                pillars['Cash Growth'] = (((bal.loc[c_row].iloc[0]-bal.loc[c_row].iloc[-1])/abs(bal.loc[c_row].iloc[-1])) > 0, "")
            except: pillars['Cash Growth'] = (False, "")
            try: pillars['Repay Debt'] = (total_cash >= lt_debt, f"Cash > LTD")
            except: pillars['Repay Debt'] = (False, "")
            try:
                l_row = 'Total Non Current Liabilities Net Minority Interest' if 'Total Non Current Liabilities Net Minority Interest' in bal.index else 'Total Non Current Liabilities'
                avg_liab = bal.loc[l_row].iloc[:5].mean() if l_row in bal.index else 0
                pillars['Repay Liab'] = (total_cash >= avg_liab, "")
            except: pillars['Repay Liab'] = (False, "")
            
            if pe is None: pe = 0
            pillars['PE < 22.5'] = (0 < pe < 22.5, f"{pe:.2f}")
            
            try:
                roic_sum = 0
                cnt = min(5, len(fin.columns))
                for i in range(cnt):
                    e = fin.loc['EBIT'].iloc[i] if 'EBIT' in fin.index else fin.loc['Pretax Income'].iloc[i]
                    ic = bal.loc['Stockholders Equity'].iloc[i] + lt_debt
                    roic_sum += (e/ic)
                avg_roic = (roic_sum/cnt)*100
                pillars['ROIC > 9%'] = (avg_roic > 9, f"{avg_roic:.1f}%")
            except: pillars['ROIC > 9%'] = (False, "")
            try:
                sh_now = info.get('sharesOutstanding', 0)
                sh_old = bal.loc['Ordinary Shares Number'].iloc[-1] if 'Ordinary Shares Number' in bal.index else sh_now
                pillars['Share Buyback'] = (sh_now <= sh_old, "")
            except: pillars['Share Buyback'] = (False, "")
            try:
                if 'Free Cash Flow' in cf.index: fcf_avg = cf.loc['Free Cash Flow'].iloc[:5].mean()
                else: fcf_avg = (cf.loc['Operating Cash Flow'] + cf.loc['Capital Expenditure']).iloc[:5].mean()
                pillars['FCF x20 > MktCap'] = ((fcf_avg*20) > mkt_cap, "")
            except: pillars['FCF x20 > MktCap'] = (False, "")
            pillars['Div Safety'] = (True, "Safe")

            # --- PRIKAZ PILLARA (POPRAVLJENO) ---
            # Sada koristimo običan if/else da izbjegnemo ispisivanje koda na ekran
            cp1, cp2 = st.columns(2)
            
            def show_p(col, k, v):
                passed, txt = v
                if passed:
                    col.success(f"✅ {k} {txt}")
                else:
                    col.error(f"❌ {k} {txt}")

            with cp1: 
                for k in ['Revenue Growth', 'Net Inc Growth', 'Cash Growth', 'ROIC > 9%', 'PE < 22.5']:
                    show_p(st, k, pillars[k])
            with cp2: 
                for k in ['Repay Debt', 'Repay Liab', 'Share Buyback', 'Div Safety', 'FCF x20 > MktCap']:
                    show_p(st, k, pillars[k])

            st.markdown("---")

            # GRAFOVI
            st.subheader("📈 Financijski Grafovi")
            dates = fin_ch.columns[::-1]
            d_str = [str(d).split(' ')[0] for d in dates]
            
            cg1, cg2 = st.columns(2)
            with cg1:
                fig = go.Figure()
                fig.add_trace(go.Bar(x=d_str, y=fin_ch.loc['Total Revenue'][dates], name="Rev", marker_color='#2196F3'))
                fig.add_trace(go.Bar(x=d_str, y=fin_ch.loc['Net Income'][dates], name="Net Inc", marker_color='#4CAF50'))
                fig.update_layout(title="Prihodi i Dobit", template="plotly_white", barmode='group', height=350)
                st.plotly_chart(fig, use_container_width=True)
            
            # MAGIC FORMULA
            st.markdown("---")
            st.markdown("""<div class="magic-box">""", unsafe_allow_html=True)
            st.subheader("✨ Magic Formula (Ručni Kalkulator)")
            m1, m2, m3 = st.columns(3)
            with m1: eps_m = st.number_input("EPS", value=info.get('trailingEps', 5.0))
            with m2: gr_m = st.number_input("Rast %", value=15.0)
            with m3: pe_m = st.number_input("PE", value=30.0)
            
            res = calculate_dcf(eps_m, gr_m, 15, pe_m) 
            st.metric("Sticker Price (Fair Value)", f"${res/4:.2f}", f"MOS: ${res/8:.2f}")
            st.markdown("</div>", unsafe_allow_html=True)

        else: st.error("Nema podataka.")
