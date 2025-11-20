import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# --- KONFIGURACIJA STRANICE ---
st.set_page_config(page_title="Rule #1 Pro Dashboard", layout="wide")

# --- CSS STILOVI ---
st.markdown("""
<style>
    .metric-box {
        background-color: #1E1E1E;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #333;
        margin-bottom: 10px;
        font-size: 0.95rem;
        color: #eee;
        line-height: 1.6;
    }
    .metric-title {
        font-size: 1.1rem;
        font-weight: bold;
        color: #fff;
        border-bottom: 1px solid #444;
        padding-bottom: 8px;
        margin-bottom: 10px;
    }
    .l-green { color: #69F0AE; font-weight: bold; } 
    .d-green { color: #00C853; font-weight: bold; } 
    .yellow { color: #FFD740; font-weight: bold; }  
    .red { color: #FF5252; font-weight: bold; }     
    .white { color: #FFFFFF; font-weight: bold; }
    
    .big-ticker { font-size: 1.4rem; color: #aaa; font-weight: 600; }
    .big-price { font-size: 3.5rem; font-weight: 800; line-height: 1; margin: 0; }
    
    /* Stil za Magic Formula Box */
    .magic-box {
        border: 2px solid #4CAF50; /* Zeleni rub */
        padding: 25px;
        border-radius: 12px;
        background-color: #1a1a1a;
        margin-top: 20px;
    }
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
    if rule_type == "liquidity": 
        if value > 1.2: return "l-green"
        elif value >= 0.9: return "yellow"
        else: return "red"
    elif rule_type == "debt": 
        if value < 1: return "l-green"
        elif value <= 2: return "yellow"
        else: return "red"
    elif rule_type == "returns": 
        if value >= 12: return "d-green"
        elif value >= 9: return "l-green"
        elif value >= 6: return "yellow"
        else: return "red"
    elif rule_type == "int_cov": 
        if value >= 1.5: return "l-green"
        elif value >= 1.15: return "yellow"
        else: return "red"
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
    st.header("⚙️ Postavke")
    ticker = st.text_input("Simbol:", "CRM").upper()
    graph_period = st.radio("Prikaz Grafova:", ["Godišnje (Annual)", "Kvartalno (Quarterly)"])
    btn = st.button("Skeniraj", type="primary")

# --- GLAVNI DIO ---
if btn or ticker:
    with st.spinner(f'Dohvaćam podatke za {ticker}...'):
        fin_y, bal_y, cf_y, fin_q, bal_q, cf_q, info = get_data(ticker)
        
        if not fin_y.empty:
            if "Quarterly" in graph_period:
                fin_ch, bal_ch, cf_ch = fin_q, bal_q, cf_q
                chart_title = "Kvartalni Prikaz"
            else:
                fin_ch, bal_ch, cf_ch = fin_y, bal_y, cf_y
                chart_title = "Godišnji Prikaz"
            
            fin, bal, cf = fin_y, bal_y, cf_y 
            
            # --- HEADER INFO ---
            curr_price = info.get('currentPrice', 0)
            prev_close = info.get('previousClose', curr_price)
            price_color = "#4CAF50" if curr_price >= prev_close else "#FF5252"
            
            # Metrike
            pm = info.get('profitMargins', 0) * 100 if info.get('profitMargins') else 0
            om = info.get('operatingMargins', 0) * 100 if info.get('operatingMargins') else 0
            gm = info.get('grossMargins', 0) * 100 if info.get('grossMargins') else 0
            
            total_cash = info.get('totalCash', 0)
            ltd_row = 'Long Term Debt' if 'Long Term Debt' in bal.index else 'Long Term Debt And Capital Lease Obligation'
            lt_debt = bal.loc[ltd_row].iloc[0] if ltd_row in bal.index else 0
            net_cash = total_cash - lt_debt
            
            raw_div = info.get('dividendYield')
            div_yield = raw_div * 100 if raw_div is not None else None
            raw_payout = info.get('payoutRatio')
            payout = raw_payout * 100 if raw_payout is not None else None
            
            qr = info.get('quickRatio', 0)
            cr = info.get('currentRatio', 0)
            de = info.get('debtToEquity', 0) / 100 if info.get('debtToEquity') else 0
            roa = info.get('returnOnAssets', 0) * 100 if info.get('returnOnAssets') else 0
            roe = info.get('returnOnEquity', 0) * 100 if info.get('returnOnEquity') else 0
            
            try:
                ebit = fin.loc['EBIT'].iloc[0] if 'EBIT' in fin.index else fin.loc['Pretax Income'].iloc[0]
                int_exp = abs(fin.loc['Interest Expense'].iloc[0]) if 'Interest Expense' in fin.index else 0
                int_cov = ebit / int_exp if int_exp > 0 else 0
            except: int_cov = 0
            
            try:
                roic_sum = 0
                years_cnt = min(5, len(fin.columns))
                for i in range(years_cnt):
                    e = fin.loc['EBIT'].iloc[i] if 'EBIT' in fin.index else fin.loc['Pretax Income'].iloc[i]
                    ic = bal.loc['Stockholders Equity'].iloc[i] + lt_debt
                    roic_sum += (e/ic)
                avg_roic = (roic_sum/years_cnt)*100
            except: avg_roic = 0

            mkt_cap = info.get('marketCap', 0)
            eps_ttm = info.get('trailingEps', 0)
            pe_ttm = info.get('trailingPE', 0)
            pe_fwd = info.get('forwardPE', 0)
            ps = info.get('priceToSalesTrailing12Months', 0)
            pb = info.get('priceToBook', 0)
            bvps = info.get('bookValue', 0)

            # --- PRIKAZ HEADER ---
            col_big1, col_big2 = st.columns([2, 1])
            with col_big1:
                st.markdown(f"""
                    <div>
                        <span class="big-ticker">{ticker} / USD</span><br>
                        <span class="big-price" style="color:{price_color}">${curr_price}</span>
                    </div>
                """, unsafe_allow_html=True)
            
            st.markdown("---")
            
            c1, c2, c3 = st.columns(3)
            
            with c1:
                dy_str = f"{div_yield:.2f}%" if div_yield is not None else "-"
                po_str = f"{payout:.2f}%" if payout is not None else "-"
                st.markdown(f"""
                <div class="metric-box">
                    <div class="metric-title">💵 Cash & Margine</div>
                    Gross Margin: <b>{gm:.2f}%</b><br>
                    Op. Margin: <b>{om:.2f}%</b><br>
                    Net Margin: <b>{pm:.2f}%</b><br>
                    <hr style="border-color:#444; margin:5px 0;">
                    Total Cash: <b>{format_num(total_cash)}</b><br>
                    L.T. Debt: <b>{format_num(lt_debt)}</b><br>
                    Net Cash: <span class="{'l-green' if net_cash>0 else 'red'}">{format_num(net_cash)}</span><br>
                    <hr style="border-color:#444; margin:5px 0;">
                    Div Yield: <b>{dy_str}</b><br>
                    Payout Ratio: <b>{po_str}</b>
                </div>
                """, unsafe_allow_html=True)
            
            with c2:
                st.markdown(f"""
                <div class="metric-box">
                    <div class="metric-title">🛡️ Financijsko Zdravlje</div>
                    Quick Ratio: <span class="{get_color_class(qr, 'liquidity')}">{qr:.2f}</span><br>
                    Current Ratio: <span class="{get_color_class(cr, 'liquidity')}">{cr:.2f}</span><br>
                    Debt / Equity: <span class="{get_color_class(de, 'debt')}">{de:.2f}</span><br>
                    Interest Cov: <span class="{get_color_class(int_cov, 'int_cov')}">{int_cov:.2f}</span><br>
                    <hr style="border-color:#444; margin:5px 0;">
                    ROA: <span class="{get_color_class(roa, 'returns')}">{roa:.2f}%</span><br>
                    ROE: <span class="{get_color_class(roe, 'returns')}">{roe:.2f}%</span><br>
                    ROIC (Avg): <span class="{get_color_class(avg_roic, 'returns')}">{avg_roic:.2f}%</span>
                </div>
                """, unsafe_allow_html=True)
            
            with c3:
                st.markdown(f"""
                <div class="metric-box">
                    <div class="metric-title">🏷️ Osnovna Valuacija</div>
                    Market Cap: <b>{format_num(mkt_cap)}</b><br>
                    Current EPS: <b>${eps_ttm}</b><br>
                    <hr style="border-color:#444; margin:5px 0;">
                    P/E (TTM): <b>{pe_ttm if pe_ttm else '-'}</b><br>
                    P/E (NTM): <b>{pe_fwd if pe_fwd else '-'}</b><br>
                    Price/Sales: <b>{ps if ps else '-'}</b><br>
                    Price/Book: <b>{pb if pb else '-'}</b><br>
                    Book Val/Share: <b>${bvps}</b>
                </div>
                """, unsafe_allow_html=True)
            
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
            try: pillars['Repay Debt (Cash > LT Debt)'] = (total_cash >= lt_debt, f"Cash: {format_num(total_cash)}")
            except: pillars['Repay Debt (Cash > LT Debt)'] = (False, "")
            try:
                l_row = 'Total Non Current Liabilities Net Minority Interest' if 'Total Non Current Liabilities Net Minority Interest' in bal.index else 'Total Non Current Liabilities'
                avg_liab = bal.loc[l_row].iloc[:5].mean() if l_row in bal.index else 0
                pillars['Repay Liab (Cash > Avg Liab)'] = (total_cash >= avg_liab, "")
            except: pillars['Repay Liab (Cash > Avg Liab)'] = (False, "")
            pillars['PE < 22.5'] = (0 < pe_ttm < 22.5, f"{pe_ttm:.2f}")
            pillars['ROIC > 9%'] = (avg_roic > 9, f"{avg_roic:.2f}%")
            try:
                sh_now = info.get('sharesOutstanding', 0)
                sh_old = bal.loc['Ordinary Shares Number'].iloc[-1] if 'Ordinary Shares Number' in bal.index else sh_now
                pillars['Share Buyback'] = (sh_now <= sh_old, "Reduced")
            except: pillars['Share Buyback'] = (False, "")
            try:
                if 'Free Cash Flow' in cf.index: fcf_avg = cf.loc['Free Cash Flow'].iloc[:5].mean()
                else: fcf_avg = (cf.loc['Operating Cash Flow'] + cf.loc['Capital Expenditure']).iloc[:5].mean()
                pillars['FCF x20 > Market Cap'] = ((fcf_avg*20) > mkt_cap, "")
            except: pillars['FCF x20 > Market Cap'] = (False, "")
            try:
                div_paid = abs(cf.loc['Cash Dividends Paid'].iloc[0]) if 'Cash Dividends Paid' in cf.index else 0
                if div_paid == 0: pillars['Dividend Safety'] = (True, "No Div")
                else: pillars['Dividend Safety'] = (total_cash > div_paid, "Cash > Div Paid")
            except: pillars['Dividend Safety'] = (True, "Safe")

            cp1, cp2 = st.columns(2)
            def show_pillar(col, k, v):
                passed, txt = v
                if passed: col.success(f"✅ {k} {txt}")
                else: col.error(f"❌ {k} {txt}")
            
            with cp1:
                for k in ['Revenue Growth', 'Net Inc Growth', 'Cash Growth', 'ROIC > 9%', 'PE < 22.5']: show_pillar(st, k, pillars[k])
            with cp2:
                for k in ['Repay Debt (Cash > LT Debt)', 'Repay Liab (Cash > Avg Liab)', 'Share Buyback', 'Dividend Safety', 'FCF x20 > Market Cap']: show_pillar(st, k, pillars[k])

            st.markdown("---")

            # --- GRAFOVI ---
            st.subheader(f"📈 Financijski Grafovi ({chart_title})")
            dates = fin_ch.columns[::-1]
            d_str = [str(d).split(' ')[0] for d in dates]

            def plot_bar_chart(title, y1, name1, color1, y2=None, name2=None, color2=None):
                fig = go.Figure()
                fig.add_trace(go.Bar(x=d_str, y=y1, name=name1, marker_color=color1))
                if y2 is not None:
                    fig.add_trace(go.Bar(x=d_str, y=y2, name=name2, marker_color=color2))
                fig.update_layout(title=title, template="plotly_white", barmode='group', height=350, margin=dict(l=10, r=10, t=40, b=10))
                st.plotly_chart(fig, use_container_width=True)

            col_g1, col_g2 = st.columns(2)
            with col_g1: plot_bar_chart("Prihodi & Dobit", fin_ch.loc['Total Revenue'][dates], "Revenue", "#2196F3", fin_ch.loc['Net Income'][dates], "Net Income", "#4CAF50")
            with col_g2:
                try:
                    c_row_ch = 'Cash And Cash Equivalents' if 'Cash And Cash Equivalents' in bal_ch.index else 'Cash Cash Equivalents And Short Term Investments'
                    cd = bal_ch.loc[c_row_ch][dates]
                    ltd_chart = bal_ch.loc[ltd_row][dates] if ltd_row in bal_ch.index else [0]*len(dates)
                    plot_bar_chart("Cash vs Long Term Debt", cd, "Total Cash", "#4CAF50", ltd_chart, "L.T. Debt", "#FF5252")
                except: st.info("Nema podataka za Cash/Debt graf.")
            
            col_g3, col_g4 = st.columns(2)
            with col_g3:
                try:
                    if 'Free Cash Flow' in cf_ch.index: fcf_c = cf_ch.loc['Free Cash Flow'][dates]
                    else: fcf_c = cf_ch.loc['Operating Cash Flow'][dates] + cf_ch.loc['Capital Expenditure'][dates]
                    plot_bar_chart("Free Cash Flow", fcf_c, "FCF", "#009688")
                except: pass
            with col_g4:
                try:
                    sh_row = 'Ordinary Shares Number' if 'Ordinary Shares Number' in bal_ch.index else 'Share Issued'
                    if sh_row in bal_ch.index: plot_bar_chart("Broj Dionica", bal_ch.loc[sh_row][dates], "Shares", "#FF9800")
                except: pass
            
            # --- DCF (AUTOMATSKI) ---
            st.markdown("---")
            st.subheader("🧮 DCF Valuacija (Auto)")
            
            dc1, dc2 = st.columns(2)
            with dc1:
                g_rate = st.number_input("Rast (Growth %):", value=15.0, step=1.0)
                d_rate = st.number_input("Diskontna stopa (%):", value=10.0, step=0.5)
            with dc2:
                t_pe = st.number_input("Terminalni P/E:", value=15.0, step=1.0)
                eps_start = info.get('trailingEps', 0)
            
            v_eps = calculate_dcf(eps_start, g_rate, d_rate, t_pe)
            v_lynch = eps_start * g_rate
            if eps_start > 0 and bvps > 0:
                v_graham = np.sqrt(22.5 * eps_start * bvps)
            else:
                v_graham = 0
            
            c_r1, c_r2, c_r3 = st.columns(3)
            c_r1.metric("DCF Vrijednost", f"${v_eps:.2f}")
            c_r2.metric("Peter Lynch Value", f"${v_lynch:.2f}")
            c_r3.metric("Graham Number", f"${v_graham:.2f}")
            
            fig_m = go.Figure()
            names = ["DCF", "Lynch", "Graham"]
            vals = [v_eps, v_lynch, v_graham]
            cols = ['#2196F3', '#9C27B0', '#FF9800']
            fig_m.add_trace(go.Bar(x=names, y=vals, marker_color=cols, text=[f"${v:.2f}" for v in vals], textposition='auto'))
            fig_m.add_hline(y=curr_price, line_dash="dash", line_color="black", annotation_text=f"Cijena: ${curr_price}")
            fig_m.update_layout(title="Fer Vrijednost vs Cijena", height=400, template="plotly_white")
            st.plotly_chart(fig_m, use_container_width=True)

        else:
            st.error("Nema podataka za ovaj simbol.")
            
    # --- MAGIC FORMULA (MANUAL CALCULATION) ---
    st.markdown("---")
    st.markdown("""<div class="magic-box">""", unsafe_allow_html=True)
    st.subheader("✨ Magic Formula Calculation (Ručni Unos)")
    
    mf1, mf2, mf3 = st.columns(3)
    with mf1:
        m_eps = st.number_input("Trenutni EPS:", value=5.85, step=0.01, key="m_eps")
    with mf2:
        m_growth = st.number_input("Očekivani Rast (%):", value=15.0, step=0.1, key="m_growth")
    with mf3:
        m_pe = st.number_input("Očekivani P/E:", value=30.0, step=0.1, key="m_pe")
    
    # Rule #1 Logic
    # 1. Future EPS = EPS * (1+g)^10
    fut_eps = m_eps * ((1 + m_growth/100)**10)
    # 2. Future Price = Fut EPS * PE
    fut_price = fut_eps * m_pe
    # 3. Sticker Price = Future Price / 4 (approx 15% discount over 10y)
    sticker = fut_price / 4
    # 4. MOS = Sticker / 2
    mos = sticker / 2
    
    st.markdown("<br>", unsafe_allow_html=True)
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Budući EPS (10g)", f"${fut_eps:.2f}")
    r2.metric("Buduća Cijena", f"${fut_price:.2f}")
    r3.metric("Fer Vrijednost (Sticker)", f"${sticker:.2f}")
    r4.metric("MOS Cijena (Kupuj)", f"${mos:.2f}", delta_color="normal")
    
    st.markdown("</div>", unsafe_allow_html=True)
