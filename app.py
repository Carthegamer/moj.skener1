import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- KONFIGURACIJA STRANICE ---
st.set_page_config(page_title="Rule #1 Pro Dashboard", layout="wide")

# --- CSS STILOVI ---
st.markdown("""
<style>
    .metric-box { background-color: #1E1E1E; padding: 15px; border-radius: 8px; border: 1px solid #333; margin-bottom: 10px; font-size: 0.95rem; color: #eee; line-height: 1.6; }
    .metric-title { font-size: 1.1rem; font-weight: bold; color: #fff; border-bottom: 1px solid #444; padding-bottom: 8px; margin-bottom: 10px; }
    .l-green { color: #69F0AE; font-weight: bold; } 
    .d-green { color: #00C853; font-weight: bold; } 
    .yellow { color: #FFD740; font-weight: bold; }  
    .red { color: #FF5252; font-weight: bold; }     
    .white { color: #FFFFFF; font-weight: bold; }
    .big-ticker { font-size: 1.4rem; color: #aaa; font-weight: 600; }
    .big-price { font-size: 3.5rem; font-weight: 800; line-height: 1; margin: 0; }
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

def calculate_rsi(data, window=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

@st.cache_data
def get_data(ticker):
    stock = yf.Ticker(ticker)
    # Dohvaćamo i povijest cijena za tehničku analizu (zadnjih 2 godine)
    history = stock.history(period="2y")
    return stock.financials, stock.balance_sheet, stock.cashflow, stock.quarterly_financials, stock.quarterly_balance_sheet, stock.quarterly_cashflow, stock.info, history

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Dashboard Postavke")
    ticker = st.text_input("Simbol:", "CRM").upper()
    graph_period = st.radio("Grafovi:", ["Godišnje", "Kvartalno"])
    btn = st.button("Skeniraj", type="primary")

# --- GLAVNI DIO ---
if btn or ticker:
    with st.spinner(f'Analiziram {ticker}...'):
        # Dohvaćamo i history sada
        fin_y, bal_y, cf_y, fin_q, bal_q, cf_q, info, history = get_data(ticker)
        
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
            
            pm, om, gm = info.get('profitMargins', 0)*100, info.get('operatingMargins', 0)*100, info.get('grossMargins', 0)*100
            total_cash = info.get('totalCash', 0)
            ltd_row = 'Long Term Debt' if 'Long Term Debt' in bal.index else 'Long Term Debt And Capital Lease Obligation'
            lt_debt = bal.loc[ltd_row].iloc[0] if ltd_row in bal.index else 0
            net_cash = total_cash - lt_debt
            dy = info.get('dividendYield', 0)*100 if info.get('dividendYield') else None
            
            with c1:
                st.markdown(f"""<div class="metric-box"><b>Net Margin:</b> {pm:.2f}% | <b>Op:</b> {om:.2f}%<br><b>Total Cash:</b> {format_num(total_cash)}<br><b>L.T. Debt:</b> {format_num(lt_debt)}<br><b>Net Cash:</b> <span style="color:{'#4CAF50' if net_cash>0 else '#FF5252'}">{format_num(net_cash)}</span></div>""", unsafe_allow_html=True)

            qr, cr, de = info.get('quickRatio', 0), info.get('currentRatio', 0), info.get('debtToEquity', 0)/100
            roa, roe = info.get('returnOnAssets', 0)*100, info.get('returnOnEquity', 0)*100
            
            with c2:
                st.markdown(f"""<div class="metric-box">Quick: <span class="{get_color_class(qr,'liquidity')}">{qr:.2f}</span> | Curr: <span class="{get_color_class(cr,'liquidity')}">{cr:.2f}</span><br>Debt/Eq: <span class="{get_color_class(de,'debt')}">{de:.2f}</span><br>ROA: <span class="{get_color_class(roa,'returns')}">{roa:.1f}%</span> | ROE: <span class="{get_color_class(roe,'returns')}">{roe:.1f}%</span></div>""", unsafe_allow_html=True)

            mkt_cap, eps, pe = info.get('marketCap', 0), info.get('trailingEps', 0), info.get('trailingPE', 0)
            
            with c3:
                st.markdown(f"""<div class="metric-box"><b>Mkt Cap:</b> {format_num(mkt_cap)}<br><b>EPS:</b> ${eps}<br><b>P/E:</b> {pe if pe else '-'}</div>""", unsafe_allow_html=True)

            # --- 10 PILLARS ---
            st.subheader("🏛️ 10 Pillars Analiza")
            pillars = {}
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
            pillars['PE < 22.5'] = (0 < pe < 22.5, f"{pe:.2f}")
            try:
                roic_sum = 0
                for i in range(min(5, len(fin.columns))):
                    e = fin.loc['EBIT'].iloc[i] if 'EBIT' in fin.index else fin.loc['Pretax Income'].iloc[i]
                    ic = bal.loc['Stockholders Equity'].iloc[i] + lt_debt
                    roic_sum += (e/ic)
                avg_roic = (roic_sum/5)*100
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

            cp1, cp2 = st.columns(2)
            def show_p(col, k, v): col.success(f"✅ {k} {v[1]}") if v[0] else col.error(f"❌ {k} {v[1]}")
            with cp1: 
                for k in ['Revenue Growth', 'Net Inc Growth', 'Cash Growth', 'ROIC > 9%', 'PE < 22.5']: show_p(st, k, pillars[k])
            with cp2: 
                for k in ['Repay Debt', 'Repay Liab', 'Share Buyback', 'Div Safety', 'FCF x20 > MktCap']: show_p(st, k, pillars[k])

            st.markdown("---")

            # --- TABS (DODAN NOVI TAB ZA TEHNIČKU ANALIZU) ---
            tab_fund, tab_tech, tab_dcf = st.tabs(["📈 Financijski Grafovi", "📉 Tehnička Analiza", "🧮 DCF & Valuacija"])

            # TAB 1: FUNDAMENTALNI GRAFOVI
            with tab_fund:
                dates = fin_ch.columns[::-1]
                d_str = [str(d).split(' ')[0] for d in dates]
                
                cg1, cg2 = st.columns(2)
                with cg1:
                    fig = go.Figure()
                    fig.add_trace(go.Bar(x=d_str, y=fin_ch.loc['Total Revenue'][dates], name="Rev", marker_color='#2196F3'))
                    fig.add_trace(go.Bar(x=d_str, y=fin_ch.loc['Net Income'][dates], name="Net Inc", marker_color='#4CAF50'))
                    fig.update_layout(title="Prihodi i Dobit", template="plotly_white", barmode='group', height=350)
                    st.plotly_chart(fig, use_container_width=True)
                
                with cg2:
                    # Cash vs LT Debt
                    try:
                        c_row_ch = 'Cash And Cash Equivalents' if 'Cash And Cash Equivalents' in bal_ch.index else 'Cash Cash Equivalents And Short Term Investments'
                        cd = bal_ch.loc[c_row_ch][dates]
                        ld = bal_ch.loc[ltd_row][dates] if ltd_row in bal_ch.index else [0]*len(dates)
                        fig2 = go.Figure()
                        fig2.add_trace(go.Bar(x=d_str, y=cd, name="Cash", marker_color='#4CAF50'))
                        fig2.add_trace(go.Bar(x=d_str, y=ld, name="L.T. Debt", marker_color='#FF5252'))
                        fig2.update_layout(title="Cash vs LT Debt", template="plotly_white", barmode='group', height=350)
                        st.plotly_chart(fig2, use_container_width=True)
                    except: st.info("Nema Cash podataka.")

            # TAB 2: TEHNIČKA ANALIZA (NOVO!)
            with tab_tech:
                st.subheader("Tehnička Analiza (Zadnjih 12 mj)")
                if not history.empty:
                    # Izračun indikatora
                    history['SMA_50'] = history['Close'].rolling(window=50).mean()
                    history['SMA_200'] = history['Close'].rolling(window=200).mean()
                    history['RSI'] = calculate_rsi(history['Close'])
                    
                    # Graf 1: Candlestick + SMA
                    fig_tech = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])
                    
                    # Cijena (Candlestick)
                    fig_tech.add_trace(go.Candlestick(x=history.index,
                                    open=history['Open'], high=history['High'],
                                    low=history['Low'], close=history['Close'], name='Cijena'), row=1, col=1)
                    
                    # SMA Linije
                    fig_tech.add_trace(go.Scatter(x=history.index, y=history['SMA_50'], line=dict(color='blue', width=1.5), name='SMA 50'), row=1, col=1)
                    fig_tech.add_trace(go.Scatter(x=history.index, y=history['SMA_200'], line=dict(color='red', width=1.5), name='SMA 200'), row=1, col=1)
                    
                    # Graf 2: RSI
                    fig_tech.add_trace(go.Scatter(x=history.index, y=history['RSI'], line=dict(color='purple', width=1.5), name='RSI'), row=2, col=1)
                    
                    # RSI Linije (30 i 70)
                    fig_tech.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
                    fig_tech.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)
                    
                    fig_tech.update_layout(xaxis_rangeslider_visible=False, height=500, template="plotly_dark")
                    st.plotly_chart(fig_tech, use_container_width=True)
                    
                    st.info("💡 **Savjet:** Kupuj kada je cijena iznad SMA 200 (Crvena), a RSI padne blizu 30 (Preprodano).")
                else:
                    st.warning("Nema povijesnih podataka o cijeni.")

            # TAB 3: MAGIC FORMULA
            with tab_dcf:
                st.markdown("""<div class="magic-box">""", unsafe_allow_html=True)
                st.subheader("✨ Magic Formula Calculation")
                m1, m2, m3 = st.columns(3)
                with m1: eps_m = st.number_input("EPS", value=info.get('trailingEps', 5.0))
                with m2: gr_m = st.number_input("Rast %", value=15.0)
                with m3: pe_m = st.number_input("PE", value=30.0)
                
                res = calculate_dcf(eps_m, gr_m, 15, pe_m) 
                st.metric("Sticker Price (Fair Value)", f"${res/4:.2f}", f"MOS: ${res/8:.2f}")
                st.markdown("</div>", unsafe_allow_html=True)

        else: st.error("Nema podataka.")
