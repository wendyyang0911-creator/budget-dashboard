import os
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import scipy.stats as stats
import streamlit as st

# ==========================================
# 0. 頁面配置與 CSS 視覺美化
# ==========================================
st.set_page_config(
    page_title='AI 預算預測與差異分析高階戰情室',
    page_icon='📊',
    layout='wide',
    initial_sidebar_state='expanded',
)

# 自訂 CSS 提升質感
st.markdown(
    """
    <style>
    .metric-card {
        background-color: #f8f9fa;
        border-left: 5px solid #1f77b4;
        padding: 15px;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .badge-red { background-color: #ff4b4b; color: white; padding: 3px 8px; border-radius: 12px; font-weight: bold; }
    .badge-yellow { background-color: #ffa100; color: white; padding: 3px 8px; border-radius: 12px; font-weight: bold; }
    .badge-green { background-color: #21c354; color: white; padding: 3px 8px; border-radius: 12px; font-weight: bold; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #f1f3f6;
        border-radius: 8px 8px 0px 0px;
        padding-top: 10px;
        padding-bottom: 10px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #1f77b4 !important;
        color: white !important;
    }
    </style>
""",
    unsafe_allow_html=True,
)


# ==========================================
# 1. 歷史資料庫自動載入與正規化
# ==========================================
@st.cache_data
def load_real_history():
  possible_files = [
      '5年5部門月度預算與支出詳細數據表.xlsx',
      '5年5部門月度預算與支出範例表_分部門分頁.xlsx',
  ]
  filepath = None
  for f in possible_files:
    if os.path.exists(f):
      filepath = f
      break

  if not filepath:
    st.error(
        '❌ 找不到 Excel 數據檔，請確認 Excel 檔案與程式碼在同一目錄中。'
    )
    return pd.DataFrame()

  dept_sheets = ['業務部', '行銷部', '研發部', '行政管理部', '資訊維運部']
  df_list = []
  xls = pd.ExcelFile(filepath)

  for sheet in dept_sheets:
    if sheet in xls.sheet_names:
      tmp_df = pd.read_excel(filepath, sheet_name=sheet)
      df_list.append(tmp_df)

  if not df_list:
    st.error('❌ Excel 檔案中缺乏預期部門分頁！')
    return pd.DataFrame()

  df_hist = pd.concat(df_list, ignore_index=True)
  df_hist = df_hist.dropna(subset=['年份', '月份', '當月分配預算', '當月實際支出'])
  df_hist['年份'] = df_hist['年份'].astype(int)
  df_hist['月份'] = df_hist['月份'].astype(int)
  df_hist['當月分配預算'] = df_hist['當月分配預算'].astype(float)
  df_hist['當月實際支出'] = df_hist['當月實際支出'].astype(float)
  df_hist['單月執行率'] = df_hist['當月實際支出'] / df_hist['當月分配預算']

  return df_hist


df_hist = load_real_history()
if df_hist.empty:
  st.stop()

departments = sorted(df_hist['部門'].unique())
target_year = 115  # 當前目標監控年份 (2026年 / 115年)

# ==========================================
# 2. 初始化 115 年全年度預算與動態帳本 (Session State)
# ==========================================
if 'budget_115' not in st.session_state:
  budget_records = []
  df_114 = df_hist[df_hist['年份'] == 114]
  for d in departments:
    for m in range(1, 13):
      val = df_114[(df_114['部門'] == d) & (df_114['月份'] == m)][
          '當月分配預算'
      ].mean()
      budget_records.append({
          '部門': d,
          '月份': m,
          '分配預算': int(val) if not np.isnan(val) else 500000,
      })
  st.session_state.budget_115 = pd.DataFrame(budget_records)

if 'actual_115' not in st.session_state:
  actual_records = []
  for d in departments:
    for m in range(1, 13):
      base_b = st.session_state.budget_115[
          (st.session_state.budget_115['部門'] == d)
          & (st.session_state.budget_115['月份'] == m)
      ]['分配預算'].values[0]

      # 模擬前幾個月的真實花費 (1~2月正常，3月行銷/業務部超支)
      if m == 1:
        act = int(base_b * 0.98)
      elif m == 2:
        act = int(base_b * 1.02)
      elif m == 3:
        act = (
            int(base_b * 1.18)
            if d in ['行銷部', '業務部']
            else int(base_b * 0.95)
        )
      else:
        act = 0

      actual_records.append({'部門': d, '月份': m, '實際支出': act})
  st.session_state.actual_115 = pd.DataFrame(actual_records)

# ==========================================
# 3. 側邊欄：全域控制控制台
# ==========================================
st.sidebar.image(
    'https://img.icons8.com/color/96/000000/dashboard--v1.png', width=70
)
st.sidebar.title('⚡ 控制台面板')
st.sidebar.markdown('---')

selected_month = st.sidebar.slider(
    '📅 選擇當前結算月份 (YTD 截止)', 1, 12, 3
)
st.sidebar.info(
    f'📌 歷史對照庫：110 ~ 114 年 (5年基底)\n\n'
    f'🎯 當前決算區間：**115 年 1 ~ {selected_month} 月**'
)

st.sidebar.markdown('---')
st.sidebar.subheader('⚙️ 風險敏感度調整')
risk_tolerance = st.sidebar.select_slider(
    '預算差異容許區間 (預警寬鬆度)',
    options=['嚴格 (1.0 σ)', '標準 (1.5 σ)', '寬鬆 (2.0 σ)'],
    value='標準 (1.5 σ)',
)
sigma_mult = (
    1.0
    if '嚴格' in risk_tolerance
    else 1.5
    if '標準' in risk_tolerance
    else 2.0
)

# ==========================================
# 4. 主畫面抬頭與 KPI 計算
# ==========================================
st.title('📊 企業級 AI 預算預測與差異分析戰情室')
st.caption('Comprehensive Executive Budget Forecasting & Risk Radar Engine')

# 計算全公司層級 KPI
b_115 = st.session_state.budget_115
a_115 = st.session_state.actual_115

total_company_annual_budget = b_115['分配預算'].sum()
company_ytd_budget = b_115[b_115['月份'] <= selected_month][
    '分配預算'
].sum()
company_ytd_actual = a_115[a_115['月份'] <= selected_month]['實際支出'].sum()
company_ytd_variance = company_ytd_budget - company_ytd_actual
company_ytd_rate = (
    company_ytd_actual / company_ytd_budget if company_ytd_budget > 0 else 0
)

# 年底 Run-Rate 預測
company_projected_year_end = (
    company_ytd_actual / selected_month
) * 12 + b_115[b_115['月份'] > selected_month]['分配預算'].sum() * 0.05
company_year_variance = (
    total_company_annual_budget - company_projected_year_end
)

# KPI 頂部展示卡片
k1, k2, k3, k4 = st.columns(4)
k1.metric('全公司 115 全年總預算', f'${total_company_annual_budget:,.0f}')
k2.metric(
    f'1~{selected_month}月 YTD 累計花費',
    f'${company_ytd_actual:,.0f}',
    f'執行率 {company_ytd_rate*100:.1f}%',
)
k3.metric(
    'YTD 累計預算超/節餘',
    f'${abs(company_ytd_variance):,.0f}',
    '節餘' if company_ytd_variance >= 0 else '超支',
    delta_color='normal' if company_ytd_variance >= 0 else 'inverse',
)
k4.metric(
    '預估全年落點 (Run-Rate)',
    f'${company_projected_year_end:,.0f}',
    f'預估{"節餘" if company_year_variance>=0 else "超支"} ${abs(company_year_variance):,.0f}',
    delta_color='normal' if company_year_variance >= 0 else 'inverse',
)

st.markdown('---')

# ==========================================
# 5. 核心四大頁籤 (4 Major Tabs)
# ==========================================
tab1, tab2, tab3, tab4 = st.tabs([
    '🌐 1. 全公司總覽與風險熱力圖',
    '🔍 2. 部門深入差異與 12個月預測',
    '💰 3. 預算編列與跨部門流用模擬',
    '📄 4. AI 財務決策與高階管理簡報',
])

# ──────────────────────────────────────────
# 【Tab 1】：全公司總覽與風險熱力圖
# ──────────────────────────────────────────
with tab1:
  st.subheader('🔥 全公司各部門預算執行率風險熱力圖 (Heatmap)')
  st.caption('直觀識別全公司 5 大部門在各月份的執行率偏差 (紅燈代表超支風險)')

  # 建構熱力圖矩陣數據
  heatmap_data = []
  for d in departments:
    row = []
    for m in range(1, 13):
      b_val = b_115[(b_115['部門'] == d) & (b_115['月份'] == m)][
          '分配預算'
      ].values[0]
      a_val = a_115[(a_115['部門'] == d) & (a_115['月份'] == m)][
          '實際支出'
      ].values[0]
      if m <= selected_month:
        rate = (a_val / b_val * 100) if b_val > 0 else 0
      else:
        rate = np.nan  # 未來月份無實際值
      row.append(rate)
    heatmap_data.append(row)

  fig_heat = px.imshow(
      heatmap_data,
      labels=dict(x='月份', y='部門', color='執行率 (%)'),
      x=[f'{m}月' for m in range(1, 13)],
      y=departments,
      color_continuous_scale='RdYlGn_r',  # 紅黃綠 (超支為紅)
      range_color=[80, 120],
      text_auto='.1f',
  )
  fig_heat.update_layout(height=320, margin=dict(l=20, r=20, t=30, b=20))
  st.plotly_chart(fig_heat, use_container_width=True)

  # 下方兩張跨部門比較圖表
  col_a, col_b = st.columns(2)
  with col_a:
    st.subheader(f'📊 各部門 1~{selected_month}月 YTD 預算 vs 實際支出比較')
    dept_ytd_b = [
        b_115[(b_115['部門'] == d) & (b_115['月份'] <= selected_month)][
            '分配預算'
        ].sum()
        for d in departments
    ]
    dept_ytd_a = [
        a_115[(a_115['部門'] == d) & (a_115['月份'] <= selected_month)][
            '實際支出'
        ].sum()
        for d in departments
    ]

    fig_bar = go.Figure(
        data=[
            go.Bar(
                name='YTD 累計預算',
                x=departments,
                y=dept_ytd_b,
                marker_color='#2ca02c',
            ),
            go.Bar(
                name='YTD 實際支出',
                x=departments,
                y=dept_ytd_a,
                marker_color='#d62728',
            ),
        ]
    )
    fig_bar.update_layout(
        barmode='group',
        height=350,
        yaxis_title='金額 (元)',
        hovermode='x unified',
    )
    st.plotly_chart(fig_bar, use_container_width=True)

  with col_b:
    st.subheader('🎯 各部門預期年底落點超支風險排行榜')
    dept_projections = []
    for d in departments:
      ytd_a = a_115[(a_115['部門'] == d) & (a_115['月份'] <= selected_month)][
          '實際支出'
      ].sum()
      tot_b = b_115[b_115['部門'] == d]['分配預算'].sum()
      proj_end = (ytd_a / selected_month) * 12
      diff = proj_end - tot_b
      dept_projections.append({'部門': d, '預估偏差': diff, '預估全年花費': proj_end})

    df_proj = pd.DataFrame(dept_projections).sort_values(
        by='預估偏差', ascending=False
    )
    fig_proj = px.bar(
        df_proj,
        x='部門',
        y='預估偏差',
        color='預估偏差',
        color_continuous_scale='Reds',
        labels={'預估偏差': '預估超支金額 (元)'},
        text_auto=',.0f',
    )
    fig_proj.update_layout(
        height=350, showlegend=False, yaxis_title='預估差異 (+超支 / -節餘)'
    )
    st.plotly_chart(fig_proj, use_container_width=True)


# ──────────────────────────────────────────
# 【Tab 2】：部門深入差異與 12 個月預測曲線
# ──────────────────────────────────────────
with tab2:
  st.subheader('🔍 單一部門深入差異診斷與全年度預測引擎')

  col_sel1, col_sel2 = st.columns([1, 2])
  with col_sel1:
    target_dept = st.selectbox('選擇欲深入分析的部門', departments, key='tab2_dept')

    # 部門當月輸入區
    act_m_val = a_115[
        (a_115['部門'] == target_dept) & (a_115['月份'] == selected_month)
    ]['實際支出'].values[0]
    new_act_m = st.number_input(
        f'✏️ 修改/錄入 【{target_dept}】 {selected_month} 月實際支出',
        value=int(act_m_val),
        step=20000,
    )
    # 更新回帳本
    st.session_state.actual_115.loc[
        (st.session_state.actual_115['部門'] == target_dept)
        & (st.session_state.actual_115['月份'] == selected_month),
        '實際支出',
    ] = new_act_m
    a_115 = st.session_state.actual_115  # 重新刷新

  # 計算部門指標
  d_b = b_115[b_115['部門'] == target_dept]
  d_a = a_115[a_115['部門'] == target_dept]

  d_m_b = d_b[d_b['月份'] == selected_month]['分配預算'].values[0]
  d_m_a = d_a[d_a['月份'] == selected_month]['實際支出'].values[0]
  d_m_rate = d_m_a / d_m_b if d_m_b > 0 else 0

  # 歷史同月份對照 (110-114年)
  hist_d_m = df_hist[
      (df_hist['部門'] == target_dept) & (df_hist['月份'] == selected_month)
  ]
  hist_m_mean = hist_d_m['單月執行率'].mean()
  hist_m_std = (
      hist_d_m['單月執行率'].std()
      if not pd.isna(hist_d_m['單月執行率'].std())
      else 0.05
  )

  # 計算信賴區間 Upper / Lower
  m_upper = hist_m_mean + sigma_mult * hist_m_std
  m_lower = hist_m_mean - sigma_mult * hist_m_std

  with col_sel2:
    st.markdown(f'### 📊 【{target_dept}】{selected_month} 月份診斷快照')
    c1, c2, c3 = st.columns(3)
    c1.metric(
        '當月實際花費',
        f'${d_m_a:,.0f}',
        f'預算 ${d_m_b:,.0f}',
    )
    c2.metric(
        '當月執行率',
        f'{d_m_rate*100:.1f}%',
        f'歷史同月均值 {hist_m_mean*100:.1f}%',
        delta_color='inverse',
    )

    if d_m_rate > m_upper:
      status_badge = '<span class="badge-red">🔴 嚴重超支警戒</span>'
      status_desc = f'執行率高於歷史上限 ({m_upper*100:.1f}%)，具極高超支風險！'
    elif d_m_rate < m_lower:
      status_badge = '<span class="badge-yellow">🟡 執行落後警戒</span>'
      status_desc = f'執行率低於歷史下限 ({m_lower*100:.1f}%)，可能存在專案報銷延宕。'
    else:
      status_badge = '<span class="badge-green">🟢 控制健康</span>'
      status_desc = '落於歷史正常合理預測區間內。'

    c3.markdown(f'**預警狀態**：{status_badge}', unsafe_allow_html=True)
    c3.caption(status_desc)

  st.markdown('---')

  # 12 個月滾動預測圖 (融合歷史季節權重 + 95% 信賴帶)
  st.subheader(f'📈 【{target_dept}】1~12 個月全年度滾動預測曲線')

  months = list(range(1, 13))
  actual_curve = []
  forecast_curve = []
  upper_band = []
  lower_band = []

  # 計算歷史 1~12 月的平均執行率與波動強度
  hist_d_all = df_hist[df_hist['部門'] == target_dept]

  for m in months:
    b_m = d_b[d_b['月份'] == m]['分配預算'].values[0]
    m_hist_rates = hist_d_all[hist_d_all['月份'] == m]['單月執行率']
    mean_rate = m_hist_rates.mean()
    std_rate = (
        m_hist_rates.std() if not pd.isna(m_hist_rates.std()) else 0.05
    )

    if m <= selected_month:
      a_m = d_a[d_a['月份'] == m]['實際支出'].values[0]
      actual_curve.append(a_m)
      forecast_curve.append(a_m)
      upper_band.append(a_m)
      lower_band.append(a_m)
    else:
      actual_curve.append(None)
      # 結合當前 YTD 的 run-rate 趨勢微調未來的預估
      run_rate_factor = (
          (
              sum(actual_curve[:selected_month])
              / d_b[d_b['月份'] <= selected_month]['分配預算'].sum()
          )
          if selected_month > 0
          else 1.0
      )
      pred_val = b_m * mean_rate * run_rate_factor
      forecast_curve.append(pred_val)
      upper_band.append(b_m * (mean_rate + sigma_mult * std_rate))
      lower_band.append(b_m * max(0.1, mean_rate - sigma_mult * std_rate))

  fig_forecast = go.Figure()

  # 信賴區間陰影帶
  fig_forecast.add_trace(
      go.Scatter(
          x=[f'{m}月' for m in months] + [f'{m}月' for m in months][::-1],
          y=upper_band + lower_band[::-1],
          fill='toself',
          fillcolor='rgba(31, 119, 180, 0.15)',
          line=dict(color='rgba(255,255,255,0)'),
          hoverinfo='skip',
          name='歷史 95% 合理安全帶',
      )
  )

  # 預算分配線
  fig_forecast.add_trace(
      go.Scatter(
          x=[f'{m}月' for m in months],
          y=d_b['分配預算'],
          mode='lines+markers',
          name='規劃預算基線',
          line=dict(color='gray', dash='dash'),
      )
  )

  # 實際花費線
  fig_forecast.add_trace(
      go.Scatter(
          x=[f'{m}月' for m in months[:selected_month]],
          y=actual_curve[:selected_month],
          mode='lines+markers',
          name='實際花費 (已發生)',
          line=dict(color='firebrick', width=3),
          marker=dict(size=8),
      )
  )

  # 未來預測線
  fig_forecast.add_trace(
      go.Scatter(
          x=[f'{m}月' for m in months[selected_month - 1 :]],
          y=forecast_curve[selected_month - 1 :],
          mode='lines+markers',
          name='AI 未來滾動預測',
          line=dict(color='royalblue', width=3, dash='dot'),
          marker=dict(size=8),
      )
  )

  fig_forecast.update_layout(
      xaxis_title='月份',
      yaxis_title='金額 (元)',
      hovermode='x unified',
      height=400,
  )
  st.plotly_chart(fig_forecast, use_container_width=True)


# ──────────────────────────────────────────
# 【Tab 3】：預算動態調整與跨部門流用模擬器
# ──────────────────────────────────────────
with tab3:
  st.subheader('💰 全年預算動態調整與跨部門流用模擬器 (Scenario Reallocation)')
  st.write('本模組提供企業管理者進行**「預算二次微調」**與**「跨部門額度支援」**試算。')

  sub_tab1, sub_tab2 = st.tabs(
      ['📝 各部門年度預算直接修改', '🔄 跨部門預算流用 (Transfer) 模擬']
  )

  with sub_tab1:
    edit_d = st.selectbox('選擇調整預算部門', departments, key='tab3_dept')
    d_b_df = b_115[b_115['部門'] == edit_d].copy()

    edited_b = st.data_editor(
        d_b_df[['月份', '分配預算']],
        num_rows='fixed',
        use_container_width=True,
        key=f'editor_{edit_d}',
    )

    # 更新 Session State
    for idx, row in edited_b.iterrows():
      m = row['月份']
      st.session_state.budget_115.loc[
          (st.session_state.budget_115['部門'] == edit_d)
          & (st.session_state.budget_115['月份'] == m),
          '分配預算',
      ] = row['分配預算']

    st.success(
        f'✅ 【{edit_d}】最新總預算為：${st.session_state.budget_115[st.session_state.budget_115["部門"]==edit_d]["分配預算"].sum():,.0f} 元'
    )

  with sub_tab2:
    st.markdown('#### 🔄 跨部門預算額度流用試算')
    st.caption(
        '若某些部門 (如業務部/行銷部) 預計超支，可從有剩餘預算的部門 (如行政部) 調撥額度。'
    )

    c_donor, c_receiver, c_amount = st.columns(3)
    with c_donor:
      donor_dept = st.selectbox('轉出預算部門 (提供者)', departments, index=3)
    with c_receiver:
      receiver_dept = st.selectbox(
          '轉入預算部門 (接受者)', departments, index=0
      )
    with c_amount:
      transfer_amount = st.number_input(
          '流用金額 (元)', value=300000, step=50000
      )

    if st.button('🚀 執行流用試算模擬'):
      if donor_dept == receiver_dept:
        st.error('轉出與轉入部門不可相同！')
      else:
        st.balloons()
        st.success(
            f'🎉 成功模擬：將 【{donor_dept}】 的 ${transfer_amount:,.0f} 元預算轉移給 【{receiver_dept}】！'
        )

        d_orig_b = b_115[b_115['部門'] == donor_dept]['分配預算'].sum()
        r_orig_b = b_115[b_115['部門'] == receiver_dept]['分配預算'].sum()

        r1, r2 = st.columns(2)
        r1.info(
            f'**【{donor_dept}】** 調整後總預算：'
            f' ~${d_orig_b:,.0f}~ ➔ **${d_orig_b - transfer_amount:,.0f}**'
        )
        r2.success(
            f'**【{receiver_dept}】** 調整後總預算：'
            f' ~${r_orig_b:,.0f}~ ➔ **${r_orig_b + transfer_amount:,.0f}**'
        )


# ──────────────────────────────────────────
# 【Tab 4】：AI 財務決策與高階管理簡報
# ──────────────────────────────────────────
with tab4:
  st.subheader('📄 AI 財務決策與高階管理簡報報告')
  st.caption('自動彙整 110-114 年歷史基底與 115 年當前動態數據，生成標準高階決策備忘錄 (Executive Memo)')

  # 自動判斷警示部門
  alert_depts = []
  for d in departments:
    ytd_a = a_115[(a_115['部門'] == d) & (a_115['月份'] <= selected_month)][
        '實際支出'
    ].sum()
    ytd_b = b_115[(b_115['部門'] == d) & (b_115['月份'] <= selected_month)][
        '分配預算'
    ].sum()
    rate = ytd_a / ytd_b if ytd_b > 0 else 0
    if rate > 1.05:
      alert_depts.append((d, rate))

  alert_str = (
      '、'.join([f'**{d[0]}** (YTD 執行率 {d[1]*100:.1f}%)' for d in alert_depts])
      if alert_depts
      else '無（各部門控制良好）'
  )

  report_md = f"""
### 📋 115 年度截至 {selected_month} 月份預算執行與風險評估高階報告

#### 📌 一、 執行總覽與關鍵摘要 (Executive Summary)
1. **全公司整體執行率**：115 年 1~{selected_month} 月全公司累計預算支出金額為 **${company_ytd_actual:,.0f}** 元，總體 YTD 執行率為 **{company_ytd_rate*100:.2f}%**。
2. **年底預測落點**：按當前 Run-Rate 趨勢推算，預估 115 全年總花費將達到 **${company_projected_year_end:,.0f}** 元，相較年度總預算預估偏差為 **{"超支" if company_year_variance<0 else "節餘"} ${abs(company_year_variance):,.0f} 元**。
3. **高風險警戒部門**：{alert_str}。

---

#### 🔍 二、 根因分析與歷史對照 (Past Root-Cause Analysis)
* **季節性趨勢比對**：對照 110-114 年歷史 5 年數據，第 {selected_month} 季度通常屬於費用報銷與業務衝刺高峰。
* **差異主因剖析**：部分部門（特別是行銷與業務單位）因集中於當月支付推廣活動款項，導致單月執行率衝高，屬於「短期集中流出」現象。

---

#### 🚨 三、 當前管理處置措施 (Present Action Plan)
* **二級簽核審核機制**：建議針對偏高部門，即日起針對單筆大於 **$100,000** 元之非經常性支出啟動二次審核。
* **費用性與資本性分流**：請財務部盤點當前累計支出中，屬於一次性專案費用與經常性管銷費用的比例。

---

#### 🔮 四、 資源優化配置建議 (Future Strategic Roadmap)
1. **跨部門預算動態流用**：建議調配目前執行率低於 **85%** 之行政或資維部門閒置額度 **3%~5%**，注入行銷與業務部門作為年末衝刺緩衝金。
2. **滾動式 12 個月預測 (Rolling Forecast)**：每月底固定更新未來 12 個月的預測值，將歷史信賴區間做為動態風控門檻。
"""

  st.markdown(report_md)

  st.markdown('---')
  st.subheader('📌 建議行動方案清單 (Action Items Matrix)')

  action_df = pd.DataFrame([
      {
          '優先級': '🔴 高 (High)',
          '行動項目': '行銷與業務部專案開支簽核複查',
          '負責單位': '財務部 / 權責部門主管',
          '預期效益': '遏制年底 5%~8% 的潛在超支',
      },
      {
          '優先級': '🟡 中 (Medium)',
          '跨部門預算流用試算與申請',
          '負責單位': '營運管理處',
          '預期效益': '均衡整體資金池，提升預算利用率',
      },
      {
          '優先級': '🟢 低 (Low)',
          '歷史資料庫季節參數每季校正',
          '負責單位': 'IT / 數據分析組',
          '預期效益': '維持預測模型 95% 信賴區間精準度',
      },
  ])
  st.table(action_df)
