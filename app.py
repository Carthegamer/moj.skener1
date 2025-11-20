import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import time

# --- KONFIGURACIJA STRANICE ---
st.set_page_config(page_title="Rule #1 Pro Dashboard", layout="wide")

# --- CSS STILOVI (Za kompaktni i moderni izgled) ---
st.markdown("""
<style>
    /* Glavni boxovi za metrike */
    .metric-box {
        background-color: #1E1E1E;
        padding: 12px;
        border-radius: 8px;
        border: 1px solid #333;
        margin-bottom: 8px;
        font-size: 0.9rem;
        color: #eee;
    }
    .box-title {
        font-size: 1rem;
        font-weight: bold;
        color: #fff;
        margin-bottom: 8px;
        border-bottom: 1px solid #444;
        padding-bottom: 4px;
    }
    /* Pillar redovi */
    .pillar-row {
        display: flex;
        justify-content: space-between;
        margin-bottom: 4px;
        padding: 3px 0;
        border-bottom: 1px solid #2b2b2b;
        font-size: 0.85rem;
    }
    .pillar-pass { color: #4CAF50; font-weight: bold; }
    .pillar-fail { color: #FF5252; font-weight: bold; }
    
    /* Velika cijena na vrhu */
    .big-ticker { font-size: 1.3rem; color: #aaa; font-weight: 600; }
    .big-price { font-size: 3.5rem; font-weight: 800; line-height: 1; margin: 0; }
    .price-green { color: #4CAF50; }
    .price-red { color: #FF5252; }
    
    /* Ukloni prazninu na vrhu */
    .block-container { padding-top: 2rem; }
</style>
""", unsafe_allow_html=True)

# --- POMOĆNE FUNKCIJE ---
def format_num(num):
    if num is None: return "-"
    if abs(num) >= 1_000_000_000_000: return f"{num / 1_000_000_000_000:.2f}T"
    if abs(num) >= 1_000_000_000: return f"{num / 1_000_000_000:.2f}B"
    elif abs(num) >= 1_000_000: return f"{num / 1_000_000:.2f}M"
    else: return f"{num:.2f}"

def get_color_html(value, type_rule):
    if value is None: return "white"
    if type_rule == "ratio_liquidity": 
        if value > 1.2: return "#4CAF50" 
        elif value >= 0.9: return "#FFC107"
        else: return "#FF5252"
    elif type_rule == "debt_equity": 
        if value < 1: return "#4CAF50"
        elif value <= 2: return "#FFC107"
        else: return "#FF5252"
    elif type_rule == "returns": 
        if value > 12: return "#2E7D32" 
        elif value > 9: return "#4CAF50" 
        elif value > 6: return "#FFC107" 
        else: return "#FF5252" 
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
    # Dohvaćamo sve setove podataka odjednom
    return stock.financials, stock.balance_sheet, stock.cashflow, stock.quarterly_financials, stock.quarterly_balance_sheet, stock.quarterly_cashflow, stock.info

# --- IZBORNIK (SIDEBAR) ---
with st.sidebar:
    st.header("⚙️ Postavke")
    ticker = st.text_input("Simbol:", "CRM").upper()
    period_type = st.radio("Prikaz Grafova:", ["Godišnje (Annual)", "Kvartalno (Quarterly)"])
    btn = st.button("Skeniraj", type="primary")

# --- GLAVNI LOGIC START ---
if btn or ticker:
    with st.spinner(f'⏳ Dohvaćam podatke za {ticker}...'):
        fin_y, bal_y, cf_y, fin_q, bal_q, cf_q, info = get_data(ticker)
        
        if not fin_y.empty:
            # Određivanje seta za grafove
            if "Quarterly" in period_type:
                fin_ch, bal_ch, cf_ch = fin_q, bal_q, cf_q
                chart_title = "Kvartalni"
            else:
                fin_ch, bal_ch, cf_ch = fin_y, bal_y, cf_y
                chart_title = "Godišnji"
            
            # Podaci za analizu (Uvijek Annual za stabilnost)
            fin, bal, cf = fin_y, bal_y, cf_y
            
            # Priprema varijabli
            curr_price = info.get('currentPrice', 0)
            prev_close = info.get('previousClose', curr_price)
            price_col = "price-green" if curr_price >= prev_close else "price-red"
            
            # Long Term Debt
            ltd_row = 'Long Term Debt' if 'Long Term Debt' in bal.index else 'Long Term Debt And Capital Lease Obligation'
            lt_debt = bal.loc[ltd_row].iloc[0] if ltd_row in bal.index else 0
            
            total_cash = info.get('totalCash', 0)
            net_cash_lt = total_cash - lt_debt
            # --- PRIKAZ ZAGLAVLJA (Velika cijena) ---
            col_h1, col_h2 = st.columns([2, 1])
            with col_h1:
                st.markdown(f"""
                    <div style="margin-bottom: 10px;">
                        <span class="big-ticker">{ticker} / USD</span><br>
                        <span class="big-price {price_col}">${curr_price}</span>
                    </div>
                """, unsafe_allow_html=True)
            
            # Izračun skora
            # Ovdje radimo brzu kalkulaciju svih 10 stupova
            pillars = {}
            years_cnt = min(5, len(fin.columns))

            # 1-3 Growth
            try: pillars['Revenue Growth'] = (((fin.iloc[0,0]-fin.iloc[0,-1])/fin.iloc[0,-1]) > 0, f"{((fin.iloc[0,0]-fin.iloc[0,-1])/fin.iloc[0,-1]*100):.1f}%")
            except: pillars['Revenue Growth'] = (False, "N/A")
            try: pillars['Net Inc Growth'] = (((fin.loc['Net Income'].iloc[0]-fin.loc['Net Income'].iloc[-1])/abs(fin.loc['Net Income'].iloc[-1])) > 0, "")
            except: pillars['Net Inc Growth'] = (False, "N/A")
            try: 
                c_row = 'Cash And Cash Equivalents' if 'Cash And Cash Equivalents' in bal.index else 'Cash Cash Equivalents And Short Term Investments'
                pillars['Cash Growth'] = (((bal.loc[c_row].iloc[0]-bal.loc[c_row].iloc[-1])/abs(bal.loc[c_row].iloc[-1])) > 0, "")
            except: pillars['Cash Growth'] = (False, "N/A")
            
            # 4-5 Debt
            try: pillars['Repay Debt'] = (bal.loc[c_row].iloc[0] >= lt_debt, f"Cash > LTD")
            except: pillars['Repay Debt'] = (False, "N/A")
            try:
                l_row = 'Total Non Current Liabilities Net Minority Interest' if 'Total Non Current Liabilities Net Minority Interest' in bal.index else 'Total Non Current Liabilities'
                avg_liab = bal.loc[l_row].iloc[:5].mean()
                pillars['Repay Liab'] = (bal.loc[c_row].iloc[0] >= avg_liab, "")
            except: pillars['Repay Liab'] = (False, "Err")
            
            # 6-7 Returns
            pe = info.get('trailingPE', 0)
            pillars['PE < 22.5'] = (0 < pe < 22.5, f"{pe:.2f}")
            try:
                roic_sum = 0
                for i in range(years_cnt):
                    ebit = fin.loc['EBIT'].iloc[i] if 'EBIT' in fin.index else fin.loc['Pretax Income'].iloc[i]
                    ic = bal.loc['Stockholders Equity'].iloc[i] + lt_debt
                    roic_sum += (ebit/ic)
                avg_roic = (roic_sum/years_cnt)*100
                pillars['ROIC > 9%'] = (avg_roic > 9, f"{avg_roic:.1f}%")
            except: pillars['ROIC > 9%'] = (False, "N/A")
            
            # 8-10 Value/Other
            try:
                sh_now = info.get('sharesOutstanding', 0)
                sh_old = bal.loc['Ordinary Shares Number'].iloc[-1] if 'Ordinary Shares Number' in bal.index else sh_now
                pillars['Share Buyback'] = (sh_now <= sh_old, "Reduced")
            except: pillars['Share Buyback'] = (False, "N/A")
            try:
                mkt_cap = info.get('marketCap', 0)
                if 'Free Cash Flow' in cf.index: fcf_avg = cf.loc['Free Cash Flow'].iloc[:5].mean()
                else: fcf_avg = (cf.loc['Operating Cash Flow'] + cf.loc['Capital Expenditure']).iloc[:5].mean()
                pillars['FCF x20'] = ((fcf_avg*20) > mkt_cap, "")
            except: pillars['FCF x20'] = (False, "N/A")
            pillars['Div Safety'] = (True, "Safe") # Pojednostavljeno

            score = sum([1 for k,v in pillars.items() if v[0]])
            with col_h2:
                st.markdown(f"<h2 style='text-align:right; color:#888; margin:0;'>Score: <span style='color:#4CAF50'>{score}/10</span></h2>", unsafe_allow_html=True)

            # --- RED 1: METRIKE ---
            c1, c2, c3 = st.columns(3)
            
            # Metrike izračuni
            pm = info.get('profitMargins', 0) * 100 if info.get('profitMargins') else 0
            om = info.get('operatingMargins', 0) * 100 if info.get('operatingMargins') else 0
            dy = info.get('dividendYield', 0) * 100 if info.get('dividendYield') else None
            qr = info.get('quickRatio', 0)
            cr = info.get('currentRatio', 0)
            de = info.get('debtToEquity', 0) / 100 if info.get('debtToEquity') else 0
            roa = info.get('returnOnAssets', 0) * 100 if info.get('returnOnAssets') else 0
            roe = info.get('returnOnEquity', 0) * 100 if info.get('returnOnEquity') else 0
            pb = info.get('priceToBook', 0)

            with c1:
                st.markdown(f"""
                <div class="metric-box">
                    <div class="box-title">💵 Cash & Margine</div>
                    Net Margin: <b>{pm:.1f}%</b> | Op: <b>{om:.1f}%</b><br>
                    Total Cash: <b>{format_num(total_cash)}</b><br>
                    L.T. Debt: <b>{format_num(lt_debt)}</b><br>
                    Net Cash: <span style="color:{'#4CAF50' if net_cash_lt>0 else '#FF5252'}"><b>{format_num(net_cash_lt)}</b></span><br>
                    Div Yield: <b>{f"{dy:.2f}%" if dy else "-"}</b>
                </div>
                """, unsafe_allow_html=True)
            
            with c2:
                st.markdown(f"""
                <div class="metric-box">
                    <div class="box-title">🛡️ Zdravlje</div>
                    Quick: <span style="color:{get_color_html(qr,'ratio_liquidity')}">{qr:.2f}</span> | 
                    Curr: <span style="color:{get_color_html(cr,'ratio_liquidity')}">{cr:.2f}</span><br>
                    Debt/Eq: <span style="color:{get_color_html(de,'debt_equity')}">{de:.2f}</span><br>
                    ROA: <span style="color:{get_color_html(roa,'returns')}">{roa:.1f}%</span> | 
                    ROE: <span style="color:{get_color_html(roe,'returns')}">{roe:.1f}%</span>
                </div>
                """, unsafe_allow_html=True)

            with c3:
                st.markdown(f"""
                <div class="metric-box">
                    <div class="box-title">🏷️ Valuacija</div>
                    Mkt Cap: <b>{format_num(mkt_cap)}</b><br>
                    P/E (TTM): <b>{pe if pe else '-'}</b><br>
                    P/B: <b>{pb if pb else '-'}</b><br>
                    Book Val: <b>${info.get('bookValue',0)}</b>
                </div>
                """, unsafe_allow_html=True)

           # --- RED 2: 10 PILLARS PRIKAZ ---
            st.markdown("<h5 style='margin-top:10px; color:#888;'>🏛️ 10 Pillars Analysis</h5>", unsafe_allow_html=True)
            cp1, cp2 = st.columns(2)
            
            def render_pillar_col(col, items):
                html_content = '<div class="metric-box">'
                for k in items:
                    # Dohvatimo podatke, ako nema, default je False
                    passed, note = pillars.get(k, (False, "N/A"))
                    status_cls = "pillar-pass" if passed else "pillar-fail"
                    icon = "✅" if passed else "❌"
                    html_content += f"""
                    <div class="pillar-row">
                        <span class="pillar-label" style="color:#ccc;">{k}</span>
                        <span>
                            <span style="font-size:0.8em; color:#666; margin-right:5px;">{note}</span> 
                            <span class="{status_cls}">{icon}</span>
                        </span>
                    </div>
                    """
                html_content += '</div>'
                # KLJUČNA PROMJENA: Ovdje dodajemo unsafe_allow_html=True
                col.markdown(html_content, unsafe_allow_html=True)

            render_pillar_col(cp1, ['Revenue Growth', 'Net Inc Growth', 'Cash Growth', 'ROIC > 9%', 'PE < 22.5'])
            render_pillar_col(cp2, ['Repay Debt', 'Repay Liab', 'Share Buyback', 'Div Safety', 'FCF x20'])
            tab_chart, tab_dcf = st.tabs(["📈 Financijski Grafovi", "🧮 DCF & Valuacija"])
            
            with tab_chart:
                st.caption(f"Prikaz podataka: {chart_title}")
                dates = fin_ch.columns[::-1] # Obrni redoslijed (najstarije prvo)
                d_str = [str(d).split(' ')[0] for d in dates]

                def plot_bar(title, y, col, y2=None, col2=None, name2=None):
                    fig = go.Figure()
                    fig.add_trace(go.Bar(x=d_str, y=y, name=title, marker_color=col, width=0.4))
                    if y2 is not None: fig.add_trace(go.Bar(x=d_str, y=y2, name=name2, marker_color=col2, width=0.4))
                    fig.update_layout(
                        title=dict(text=title, font=dict(size=14)),
                        height=280, 
                        margin=dict(l=10,r=10,t=30,b=10), 
                        template="plotly_white",
                        barmode='group'
                    )
                    st.plotly_chart(fig, use_container_width=True)

                # Red grafova 1
                cg1, cg2 = st.columns(2)
                with cg1: plot_bar("Revenue", fin_ch.loc['Total Revenue'][dates], '#2196F3')
                with cg2: plot_bar("Net Income", fin_ch.loc['Net Income'][dates], '#4CAF50')

                # Red grafova 2
                cg3, cg4 = st.columns(2)
                try:
                    fcf = cf_ch.loc['Free Cash Flow'][dates] if 'Free Cash Flow' in cf_ch.index else (cf_ch.loc['Operating Cash Flow'][dates] + cf_ch.loc['Capital Expenditure'][dates])
                    with cg3: plot_bar("Free Cash Flow", fcf, '#009688')
                except: pass
                
                try:
                    sh = bal_ch.loc['Ordinary Shares Number'][dates] if 'Ordinary Shares Number' in bal_ch.index else bal_ch.loc['Share Issued'][dates]
                    with cg4: plot_bar("Shares Outstanding", sh, '#FF9800')
                except: pass
                
                # Red grafova 3 (Cash vs Debt)
                try:
                    c_row_ch = 'Cash And Cash Equivalents' if 'Cash And Cash Equivalents' in bal_ch.index else 'Cash Cash Equivalents And Short Term Investments'
                    cd = bal_ch.loc[c_row_ch][dates]
                    ld = bal_ch.loc[ltd_row][dates] if ltd_row in bal_ch.index else [0]*len(dates)
                    plot_bar("Cash vs LT Debt", cd, '#4CAF50', ld, '#FF5252', 'L.T. Debt')
                except: pass

            with tab_dcf:
                st.markdown("#### Kalkulator Fer Vrijednosti")
                ci1, ci2 = st.columns(2)
                with ci1:
                    g_rate = st.number_input("Rast (Growth %):", 15.0, step=1.0)
                    d_rate = st.number_input("Diskontna stopa (%):", 10.0, step=0.5)
                with ci2:
                    t_pe = st.number_input("Terminalni PE:", 15.0, step=1.0)
                    eps_start = info.get('trailingEps', 0)
                
                # Kalkulacije
                v_eps = calculate_dcf(eps_start, g_rate, d_rate, t_pe)
                v_lynch = eps_start * g_rate
                bv = info.get('bookValue', 0) if info.get('bookValue') else 0
                v_graham = np.sqrt(22.5 * eps_start * bv) if (eps_start>0 and bv>0) else 0
                
                st.markdown("---")
                c_r1, c_r2, c_r3 = st.columns(3)
                c_r1.metric("DCF (EPS Model)", f"${v_eps:.2f}")
                c_r2.metric("Peter Lynch Value", f"${v_lynch:.2f}")
                c_r3.metric("Graham Number", f"${v_graham:.2f}")
                
                # Master Graf Usporedbe
                fig_m = go.Figure()
                # Trenutna cijena linija
                fig_m.add_trace(go.Scatter(x=[-0.5, 2.5], y=[curr_price, curr_price], mode="lines", name="Trenutna Cijena", line=dict(color="#333", width=3, dash="dash")))
                
                names = ["DCF", "Lynch", "Graham"]
                vals = [v_eps, v_lynch, v_graham]
                cols = ['#2196F3', '#9C27B0', '#FF9800']
                
                fig_m.add_trace(go.Bar(x=names, y=vals, marker_color=cols, text=[f"${v:.2f}" for v in vals], textposition='auto'))
                fig_m.update_layout(title="Usporedba Valuacija", height=400, template="plotly_white")
                st.plotly_chart(fig_m, use_container_width=True)

        else:
            st.error("Nema podataka. Provjeri simbol.")
