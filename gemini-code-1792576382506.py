import os
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import scipy.stats as stats
import streamlit as st

# ==========================================
# 0. 網頁基本設定
# ==========================================
st.set_page_config(
    page_title='預算預測與差異分析助手',
    layout='wide',
    initial_sidebar_state='expanded',
)

st.title('🤖 預算預測與差異分析戰情室')
st.caption('基於 110-114 年歷史數據庫之 115 年 (2026) 動態預算監控系統')

# ==========================================
# 1. 載入 110~114 年歷史資料庫
# ==========================================
@st.cache_data
def load_real_history():
    filepath = '5年5部門月度預算與支出詳細數據表.xlsx'
    if not os.path.exists(filepath):
        st.error(f"找不到檔案：{filepath}，請確認檔案與 app.py 在同一資料夾。")
        return pd.DataFrame()
    
    # 讀取 5 個部門的分頁並合併
    dept_sheets = ['業務部', '行銷部', '研發部', '行政管理部', '資訊維運部']
    df_list = []
    for sheet in dept_sheets:
        tmp_df = pd.read_excel(filepath, sheet_name=sheet)
        df_list.append(tmp_df)
        
    df_hist = pd.concat(df_list, ignore_index=True)
    # 清理空值
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

# 取得歷史年份清單與部門清單
hist_years = sorted(df_hist['年份'].unique())
departments = sorted(df_hist['部門'].unique())
target_year = 115 # 設定監控目標年為 115 年 (2026)

# ==========================================
# 2. 初始化 115 年 (2026) 預算與實際支出帳本 (Session State)
# ==========================================
if 'budget_115' not in st.session_state:
    # 預設抓取 114 年的當月分配預算當作 115 年的基準
    budget_records = []
    df_114 = df_hist[df_hist['年份'] == 114]
    for d in departments:
        for m in range(1, 13):
            val = df_114[(df_114['部門'] == d) & (df_114['月份'] == m)]['當月分配預算'].mean()
            budget_records.append({
                '部門': d,
                '月份': m,
                '年度規劃預算': int(val) if not np.isnan(val) else 0
            })
    st.session_state.budget_115 = pd.DataFrame(budget_records)

if 'actual_115' not in st.session_state:
    # 初始化 115 年實際支出，預設 1~2 月有稍微超支的假資料，供展示用
    actual_records = []
    for d in departments:
        for m in range(1, 13):
            base_budget = st.session_state.budget_115[
                (st.session_state.budget_115['部門']==d) & 
                (st.session_state.budget_115['月份']==m)
            ]['年度規劃預算'].values[0]
            
            if m == 1: val = int(base_budget * 0.98)
            elif m == 2: val = int(base_budget * 1.05)
            elif m == 3: val = int(base_budget * 1.10) # 預設3月偏高，展示預警
            else: val = 0
            
            actual_records.append({'部門': d, '月份': m, '當月實際支出': val})
    st.session_state.actual_115 = pd.DataFrame(actual_records)

# ==========================================
# 3. 頂部兩大功能切換按鈕 (Tabs)
# ==========================================
tab1, tab2 = st.tabs([
    '💰 步驟一：115年度(2026) 全年預算編列與修改', 
    '📝 步驟二：預算差異分析與年底預測預警'
])

# ──────────────────────────────────────────
# 【功能一】：修改全年度預算
# ──────────────────────────────────────────
with tab1:
    st.header('💰 115 年度各部門預算配置表')
    st.write('系統已自動預載 114 年度預算作為基準，您可在此直接點擊表格修改 115 年度的規劃預算：')

    edit_dept = st.selectbox('選擇要編列預算的部門', departments, key='tab1_dept')

    dept_budget_mask = st.session_state.budget_115['部門'] == edit_dept
    dept_budget_df = st.session_state.budget_115[dept_budget_mask].copy()

    # 可直接編輯的表格
    edited_df = st.data_editor(
        dept_budget_df[['月份', '年度規劃預算']],
        num_rows='fixed',
        use_container_width=True,
        key=f'editor_{edit_dept}'
    )

    # 存回 Session State
    for idx, row in edited_df.iterrows():
        m = row['月份']
        st.session_state.budget_115.loc[
            (st.session_state.budget_115['部門'] == edit_dept) & 
            (st.session_state.budget_115['月份'] == m), 
            '年度規劃預算'
        ] = row['年度規劃預算']

    total_b = st.session_state.budget_115[dept_budget_mask]['年度規劃預算'].sum()
    st.success(f'✅ 【{edit_dept}】115 年全年度總規劃預算為：${total_b:,.0f} 元')


# ──────────────────────────────────────────
# 【功能二】：輸入支出、差異分析與年底預測
# ──────────────────────────────────────────
with tab2:
    st.header('📝 當前支出錄入與預測預警分析')

    col_left, col_right = st.columns([1, 2])

    with col_left:
        st.subheader('📥 支出錄入面板')
        selected_dept = st.selectbox('選擇監控部門', departments, key='tab2_dept')
        selected_month = st.slider('選擇目前月份 (截至幾月)', 1, 12, 3)

        act_mask = (st.session_state.actual_115['部門'] == selected_dept) & \
                   (st.session_state.actual_115['月份'] == selected_month)
        current_val = st.session_state.actual_115[act_mask]['當月實際支出'].iloc[0]

        new_input = st.number_input(
            f'輸入 {selected_dept} {selected_month} 月份實際支出 (元)',
            value=int(current_val),
            step=10000
        )
        st.session_state.actual_115.loc[act_mask, '當月實際支出'] = new_input
        st.caption(f'💡 系統已記錄 1 ~ {selected_month} 月的歷史輸入數字，做為預測基準。')

    # 計算 115 年截至選定月份的數字
    b_115 = st.session_state.budget_115
    a_115 = st.session_state.actual_115

    # 抓取單月與 YTD 數據
    cur_m_b = b_115[(b_115['部門']==selected_dept) & (b_115['月份']==selected_month)]['年度規劃預算'].iloc[0]
    cur_m_a = a_115[(a_115['部門']==selected_dept) & (a_115['月份']==selected_month)]['當月實際支出'].iloc[0]
    cur_ytd_b = b_115[(b_115['部門']==selected_dept) & (b_115['月份']<=selected_month)]['年度規劃預算'].sum()
    cur_ytd_a = a_115[(a_115['部門']==selected_dept) & (a_115['月份']<=selected_month)]['當月實際支出'].sum()
    total_year_b = b_115[b_115['部門']==selected_dept]['年度規劃預算'].sum()

    cur_m_rate = cur_m_a / cur_m_b if cur_m_b > 0 else 0
    cur_ytd_rate = cur_ytd_a / cur_ytd_b if cur_ytd_b > 0 else 0

    # 歷史對比運算 (110~114年同月份特徵)
    df_h_dept = df_hist[df_hist['部門'] == selected_dept]
    hist_m = df_h_dept[df_h_dept['月份'] == selected_month]
    
    m_mean = hist_m['單月執行率'].mean()
    m_std = hist_m['單月執行率'].std() if not pd.isna(hist_m['單月執行率'].std()) else 0.05
    n = len(hist_m)
    t_val = stats.t.ppf(0.975, df=n-1) if n > 1 else 2.776
    m_margin = t_val * m_std * np.sqrt(1 + 1/n)
    m_lower, m_upper = m_mean - m_margin, m_mean + m_margin

    # 年底預測邏輯 (Run Rate 預測法)
    predicted_year_end_actual = cur_ytd_a / selected_month * 12
    projected_variance = total_year_b - predicted_year_end_actual

    # 燈號判定
    if cur_m_rate > m_upper:
        status, color, msg = '🔴 紅燈（嚴重超支）', 'red', '突破歷史 5 年合理上限，具高度超支風險！'
    elif cur_m_rate > m_mean + m_std:
        status, color, msg = '🟡 黃燈（偏高警戒）', 'orange', '高於歷史平均 1 個標準差，需嚴控下月預算。'
    elif cur_m_rate < m_lower:
        status, color, msg = '🟡 黃燈（進度落後）', 'orange', '低於歷史合理下限，可能有專案延宕情形。'
    else:
        status, color, msg = '🟢 綠燈（控制健康）', 'green', '落於歷史正常安全區間內，預算執行優良。'

    with col_right:
        st.subheader(f'📊 分析診斷報告：115年 {selected_month}月 - 【{selected_dept}】')
        
        c1, c2, c3 = st.columns(3)
        c1.metric('當月執行率', f'{cur_m_rate*100:.1f}%', f'預算 ${cur_m_b:,.0f}', delta_color="inverse")
        c2.metric('YTD 累計執行率', f'{cur_ytd_rate*100:.1f}%', f'累計花費 ${cur_ytd_a:,.0f}', delta_color="inverse")
        
        # 顯示年底預測
        proj_str = f"超支 ${abs(projected_variance):,.0f}" if projected_variance < 0 else f"節餘 ${projected_variance:,.0f}"
        c3.metric('年底預估落點差異', proj_str, f'全年預估花費 ${predicted_year_end_actual:,.0f}', delta_color="normal" if projected_variance >= 0 else "inverse")

        st.markdown(f'### 當月預警：{status}')
        st.caption(f'• 說明：{msg}\n• 110-114年歷史安全區間：{m_lower*100:.1f}% ~ {m_upper*100:.1f}%')

    st.markdown('---')

    # 歷史折線圖
    st.subheader(f'📈 歷年 {selected_month} 月預算執行率走勢對比')
    
    years_label = [f'{int(y)}年' for y in hist_m['年份']] + ['115年 (當前)']
    hist_rates = list(hist_m['單月執行率'] * 100) + [cur_m_rate * 100]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=years_label, y=hist_rates, 
        mode='lines+markers', name='單月執行率 (%)', 
        line=dict(color='royalblue', width=3),
        marker=dict(size=[8]*len(hist_m) + [12], color=['royalblue']*len(hist_m) + ['red'])
    ))
    fig.add_hrect(
        y0=m_lower*100, y1=m_upper*100, 
        fillcolor='green', opacity=0.15, line_width=0,
        annotation_text='歷史 95% 合理安全區間'
    )
    fig.update_layout(xaxis_title='年份', yaxis_title='執行率 (%)', hovermode='x unified')
    st.plotly_chart(fig, use_container_width=True)

    # AI 分析摘要
    st.subheader('💡 系統洞察與資源配置建議')
    adv_action = "需立即凍結非必要支出，並啟動二級簽核機制。" if projected_variance < 0 else "目前執行穩健，可維持常態簽核機制。"
    st.markdown(f"""
    * **現況剖析**：本月【{selected_dept}】執行率達 **{cur_m_rate*100:.1f}%**，歷史同月平均為 **{m_mean*100:.1f}%**。
    * **年底預測**：若維持前 {selected_month} 個月的花費速度，預估年底將會 **{proj_str}**。
    * **行動建議**：{adv_action} 若年底確定出現超支趨勢，建議於下個月的經營會議提出「跨部門預算流用（轉移）」申請，調度其他產生節餘的部門預算。
    """)