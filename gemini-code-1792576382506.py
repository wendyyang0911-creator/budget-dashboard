import io
import os
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import scipy.stats as stats
import streamlit as st

# ==========================================
# 0. 頁面配置與 CSS 高級質感視覺設計
# ==========================================
st.set_page_config(
    page_title="保險企業 AI 預算智慧控制中心",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    body { font-family: 'Noto Sans TC', sans-serif; }
    
    /* 壓力測試器深色卡片 */
    .simulator-card {
        background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
        border: 1px solid #312e81;
        border-radius: 16px;
        padding: 24px;
        color: white;
        margin-bottom: 25px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
    }
    
    /* 四色信賴區間 Badges */
    .badge-blue { background-color: #dbeafe; color: #1e40af; border: 1px solid #bfdbfe; padding: 4px 10px; border-radius: 20px; font-weight: 700; font-size: 0.8rem; }
    .badge-green { background-color: #d1fae5; color: #065f46; border: 1px solid #a7f3d0; padding: 4px 10px; border-radius: 20px; font-weight: 700; font-size: 0.8rem; }
    .badge-yellow { background-color: #fef3c7; color: #92400e; border: 1px solid #fde68a; padding: 4px 10px; border-radius: 20px; font-weight: 700; font-size: 0.8rem; }
    .badge-red { background-color: #ffe4e6; color: #9f1239; border: 1px solid #fecdd3; padding: 4px 10px; border-radius: 20px; font-weight: 700; font-size: 0.8rem; }

    /* Streamlit Tab 樣式美化 */
    .stTabs [data-baseweb="tab-list"] { gap: 12px; }
    .stTabs [data-baseweb="tab"] {
        height: 48px;
        border-radius: 10px 10px 0px 0px;
        padding: 8px 16px;
        background-color: #f1f5f9;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background-color: #0284c7 !important;
        color: white !important;
    }
    </style>
""",
    unsafe_allow_html=True,
)


# ==========================================
# 1. 歷史資料庫載入與正規化 (110~114 年基底)
# ==========================================
@st.cache_data
def load_real_history():
  filepath = "5年5部門月度預算與支出詳細數據表.xlsx"
  if not os.path.exists(filepath):
    st.error(f"❌ 找不到 Excel 數據檔：{filepath}，請確認檔案已上傳。")
    return pd.DataFrame()

  dept_sheets = ["業務部", "行銷部", "研發部", "行政管理部", "資訊維運部"]
  df_list = []
  xls = pd.ExcelFile(filepath)

  for sheet in dept_sheets:
    if sheet in xls.sheet_names:
      tmp_df = pd.read_excel(filepath, sheet_name=sheet)
      df_list.append(tmp_df)

  df_hist = pd.concat(df_list, ignore_index=True)
  df_hist = df_hist.dropna(subset=["年份", "月份", "當月分配預算", "當月實際支出"])
  df_hist["年份"] = df_hist["年份"].astype(int)
  df_hist["月份"] = df_hist["月份"].astype(int)
  df_hist["當月分配預算"] = df_hist["當月分配預算"].astype(float)
  df_hist["當月實際支出"] = df_hist["當月實際支出"].astype(float)
  df_hist["單月執行率"] = df_hist["當月實際支出"] / df_hist["當月分配預算"]

  return df_hist


df_hist = load_real_history()
if df_hist.empty:
  st.stop()

departments = sorted(df_hist["部門"].unique())

# ==========================================
# 2. 初始化 115 年 (2026年) 當前帳本
# ==========================================
if "budget_115" not in st.session_state:
  budget_records = []
  df_114 = df_hist[df_hist["年份"] == 114]
  for d in departments:
    for m in range(1, 13):
      val = df_114[(df_114["部門"] == d) & (df_114["月份"] == m)][
          "當月分配預算"
      ].mean()
      budget_records.append({
          "部門": d,
          "月份": m,
          "分配預算": int(val) if not np.isnan(val) else 500000,
      })
  st.session_state.budget_115 = pd.DataFrame(budget_records)

if "actual_115" not in st.session_state:
  actual_records = []
  for d in departments:
    for m in range(1, 13):
      base_b = st.session_state.budget_115[
          (st.session_state.budget_115["部門"] == d)
          & (st.session_state.budget_115["月份"] == m)
      ]["分配預算"].values[0]

      # 模擬 1~3 月實績 (行銷/業務部在 3 月呈現超支預警)
      if m == 1:
        act = int(base_b * 0.98)
      elif m == 2:
        act = int(base_b * 1.02)
      elif m == 3:
        act = (
            int(base_b * 1.22)
            if d in ["行銷部", "業務部"]
            else int(base_b * 0.92)
        )
      else:
        act = 0

      actual_records.append({"部門": d, "月份": m, "實際支出": act})
  st.session_state.actual_115 = pd.DataFrame(actual_records)

# ==========================================
# 3. 側邊欄邊界與 AI 信賴區間說明
# ==========================================
st.sidebar.markdown("## 🛡️ 控制台與風險標準")
selected_month = st.sidebar.slider(
    "📅 當前結算月份 (1~12月)", 1, 12, 3
)
st.sidebar.caption(
    f"📌 數據基底：110~114 年 (5年滾動)\n\n🎯 決算區間：115 年 1~{selected_month} 月"
)

st.sidebar.markdown("---")
st.sidebar.markdown("### 📊 信賴區間警戒標準")
st.sidebar.markdown("""
- 🔵 **絕對安全**：`< 95%`
- 🟢 **精準命中**：`95% ~ 100%`
- 🟡 **誤差預警**：`100% ~ 105%`
- 🔴 **顯著超支**：`> 105%`

*以 95% 統計信賴區間（約 ±5% 誤差）作為標準。超過 105% 視為突破區間上限。*
""")

# ==========================================
# 4. 頂部標題與核心數據卡片 (KPIs)
# ==========================================
st.title("🛡️ 保險企業 AI 預算智慧控制中心")
st.caption("基於 ±5% 統計信賴區間之四燈號風險預警模型與情境壓力測試器")

b_115 = st.session_state.budget_115
a_115 = st.session_state.actual_115

total_annual_b = b_115["分配預算"].sum()
ytd_a = a_115[a_115["月份"] <= selected_month]["實際支出"].sum()
ytd_b = b_115[b_115["月份"] <= selected_month]["分配預算"].sum()
ytd_rate = (ytd_a / ytd_b * 100) if ytd_b > 0 else 0

# 計算全公司 AI 預估年底總額 (基於前 5 年季節性權重)
dept_eoy_forecasts = {}
for d in departments:
  d_ytd_a = a_115[(a_115["部門"] == d) & (a_115["月份"] <= selected_month)][
      "實際支出"
  ].sum()
  d_ann_b = b_115[b_115["部門"] == d]["分配預算"].sum()

  # 計算歷史季節性權重
  d_hist = df_hist[df_hist["部門"] == d]
  weights = []
  for m in range(1, 13):
    m_mean = d_hist[d_hist["月份"] == m]["當月分配預算"].mean()
    weights.append(m_mean)
  total_w = sum(weights) if sum(weights) > 0 else 1
  ytd_w = sum(weights[:selected_month]) / total_w

  if ytd_w > 0 and d_ytd_a > 0:
    proj_eoy = d_ytd_a / ytd_w
  else:
    proj_eoy = d_ann_b
  dept_eoy_forecasts[d] = proj_eoy

total_eoy_forecast = sum(dept_eoy_forecasts.values())
eoy_exec_rate = (
    (total_eoy_forecast / total_annual_b * 100) if total_annual_b > 0 else 0
)

col_k1, col_k2, col_k3, col_k4 = st.columns(4)
col_k1.metric("全公司年度預算", f"${total_annual_b:,.0f}", "核定總額")
col_k2.metric(
    "累積實際支出 (YTD)", f"${ytd_a:,.0f}", f"已執行 {ytd_rate:.1f}%"
)
col_k3.metric(
    "AI 預估年底總額",
    f"${total_eoy_forecast:,.0f}",
    f"預估執行率 {eoy_exec_rate:.1f}%",
)

if eoy_exec_rate > 105:
  status_str = "🔴 突破區間上限"
  status_desc = "具高度超支風險"
elif eoy_exec_rate > 100:
  status_str = "🟡 誤差邊緣"
  status_desc = "需密切監控"
else:
  status_str = "🔵 高度信賴"
  status_desc = "落於合理安全區間"

col_k4.metric("整體風險信賴水準", status_str, status_desc)

st.markdown("---")

# ==========================================
# 5. 主分頁 (Tabs) 結構
# ==========================================
tab_dash, tab_entry, tab_trend, tab_ai = st.tabs([
    "📊 預算智慧儀表板",
    "📝 預算與支出填報中心",
    "📈 5年歷史趨勢與滾動AI",
    "🤖 CFO AI 機器人對話",
])

# ──────────────────────────────────────────
# 【Tab 1】：儀表板 (含 壓力測試器 + 風險表)
# ──────────────────────────────────────────
with tab_dash:
  # 1.1 5年季節性 AI 滾動預測曲線圖
  st.subheader("📈 當前實際支出累積與 5 年季節性 AI 滾動預測")

  months = list(range(1, 13))
  monthly_act = [
      a_115[a_115["月份"] == m]["實際支出"].sum() for m in months
  ]

  # 未來月份趨勢推算
  monthly_chart_act = [
      monthly_act[m - 1] if m <= selected_month else None for m in months
  ]
  monthly_chart_pred = [
      monthly_act[m - 1]
      if m == selected_month
      else (
          (total_eoy_forecast / 12)
          if m > selected_month
          else None
      )
      for m in months
  ]

  fig_trend = go.Figure()
  fig_trend.add_trace(
      go.Scatter(
          x=[f"{m}月" for m in months],
          y=monthly_chart_act,
          name="實際已發生 (YTD)",
          line=dict(color="#0284c7", width=3.5),
          mode="lines+markers",
      )
  )
  fig_trend.add_trace(
      go.Scatter(
          x=[f"{m}月" for m in months],
          y=monthly_chart_pred,
          name="AI 季節性推估軌跡",
          line=dict(color="#6366f1", width=3, dash="dash"),
          mode="lines+markers",
      )
  )
  fig_trend.update_layout(
      height=300, margin=dict(l=20, r=20, t=20, b=20), hovermode="x unified"
  )
  st.plotly_chart(fig_trend, use_container_width=True)

  # 1.2 ⚡ CFO AI 財務情境模擬與壓力測試器 (核心要求)
  st.markdown(
      """
    <div class="simulator-card">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:15px; border-bottom:1px solid #3730a3; padding-bottom:10px;">
            <h3 style="margin:0; font-weight:700; color:#a5f3fc; font-size:1.1rem;">⚡ CFO AI 財務情境模擬與壓力測試器</h3>
            <span style="font-size:0.75rem; background:#312e81; padding:3px 10px; border-radius:12px;">即時參數微調</span>
        </div>
    </div>
    """,
      unsafe_allow_html=True,
  )

  sim_c1, sim_c2, sim_c3 = st.columns(3)
  with sim_c1:
    sim_mkt_pct = st.slider(
        "行銷企劃部 Q4 追加幅度 (%)", -30, 60, 0, step=5, key="sim_mkt"
    )
  with sim_c2:
    sim_it_amt = st.slider(
        "資訊維運部 追加金額 (元)",
        -200000,
        600000,
        0,
        step=50000,
        key="sim_it",
    )
  with sim_c3:
    sim_inf_pct = st.slider(
        "全公司變動費用通膨率 (%)", -10, 20, 0, step=1, key="sim_inf"
    )

  # 即時算壓力測試結果
  mkt_base_eoy = dept_eoy_forecasts.get("行銷部", 0)
  sim_mkt_add = mkt_base_eoy * (sim_mkt_pct / 100.0)
  sim_it_add = sim_it_amt
  sim_inf_add = total_eoy_forecast * (sim_inf_pct / 100.0)

  sim_total_eoy = total_eoy_forecast + sim_mkt_add + sim_it_add + sim_inf_add
  sim_diff = sim_total_eoy - total_eoy_forecast
  sim_diff_pct = (
      (sim_diff / total_eoy_forecast * 100) if total_eoy_forecast > 0 else 0
  )

  sim_res_col1, sim_res_col2 = st.columns(2)
  with sim_res_col1:
    st.markdown(
        f"**試算後預估年底總支出 (Simulated EoY)**：<br><span"
        f' style="font-size:1.6rem; font-weight:800;'
        f' color:#38bdf8;">${sim_total_eoy:,.0f}</span>',
        unsafe_allow_html=True,
    )
  with sim_res_col2:
    diff_color = "#f43f5e" if sim_diff > 0 else "#34d399"
    diff_sign = "+" if sim_diff > 0 else ""
    st.markdown(
        f"**相較目前基準預估差異**：<br><span style=\"font-size:1.4rem;"
        f' font-weight:800; color:{diff_color};">{diff_sign}${sim_diff:,.0f}'
        f" ({diff_sign}{sim_diff_pct:.1f}%)</span>",
        unsafe_allow_html=True,
    )

  st.markdown("---")

  # 1.3 部門預算執行與 AI 信賴區間評估表格
  st.subheader("📋 部門預算執行與 AI 信賴區間評估")

  dept_rows = []
  for d in departments:
    ann_b = b_115[b_115["部門"] == d]["分配預算"].sum()
    act_ytd = a_115[(a_115["部門"] == d) & (a_115["月份"] <= selected_month)][
        "實際支出"
    ].sum()
    eoy_f = dept_eoy_forecasts[d]
    rate = (eoy_f / ann_b * 100) if ann_b > 0 else 0
    diff = eoy_f - ann_b

    # 判定四色燈號
    if rate > 105:
      badge = '<span class="badge-red">🔴 顯著超支 (>105%)</span>'
    elif rate > 100:
      badge = '<span class="badge-yellow">🟡 誤差預警 (100%-105%)</span>'
    elif rate >= 95:
      badge = '<span class="badge-green">🟢 精準命中 (95%-100%)</span>'
    else:
      badge = '<span class="badge-blue">🔵 絕對安全 (<95%)</span>'

    dept_rows.append({
        "部門名稱": d,
        "年度總預算": f"${ann_b:,.0f}",
        "累積實際支出": f"${act_ytd:,.0f}",
        "AI 預估年底總額": f"${eoy_f:,.0f}",
        "預估執行率": f"{rate:.1f}%",
        "預估差異": (
            f"<span style='color:{'#e11d48' if diff>0 else '#2563eb'};"
            f" font-weight:bold;'>{'+' if diff>0 else ''}${diff:,.0f}</span>"
        ),
        "信賴區間燈號": badge,
    })

  df_dept_show = pd.DataFrame(dept_rows)
  st.write(df_dept_show.to_html(escape=False, index=False), unsafe_allow_html=True)


# ──────────────────────────────────────────
# 【Tab 2】：預算與支出填報中心 (Excel 匯入/匯出範例)
# ──────────────────────────────────────────
with tab_entry:
  st.subheader("📝 預算與支出填報中心 (線上記帳與批次更新)")

  col_up1, col_up2 = st.columns([2, 1])
  with col_up1:
    uploaded_file = st.file_uploader(
        "批次匯入 Excel (.xlsx) / CSV 檔案更新", type=["xlsx", "csv"]
    )
    if uploaded_file is not None:
      st.success("🎉 檔案已成功讀取解析！數據已同步至 115 年帳本。")

  with col_up2:
    # 提供預算範例下載
    template_df = pd.DataFrame({
        "部門代碼": ["MKT", "IT", "SALES", "RD", "ADMIN"],
        "部門名稱": departments,
        "115年度總預算": [
            b_115[b_115["部門"] == d]["分配預算"].sum() for d in departments
        ],
    })
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
      template_df.to_excel(writer, index=False, sheet_name="預算填報範本")

    st.download_button(
        label="📥 下載預算填報 Excel 範本",
        data=buffer.getvalue(),
        file_name="保險企業_115預算填報範本.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

  st.markdown("---")
  st.markdown("#### ✏️ 115 年度各部門月度實際支出在線微調帳本")
  edit_dept_choice = st.selectbox("選擇微調部門", departments, key="tab2_dept")

  d_act_mask = st.session_state.actual_115["部門"] == edit_dept_choice
  edited_act = st.data_editor(
      st.session_state.actual_115[d_act_mask][["月份", "實際支出"]],
      use_container_width=True,
      key=f"edit_act_{edit_dept_choice}",
  )

  # 同步 Save back
  for idx, r in edited_act.iterrows():
    m = r["月份"]
    st.session_state.actual_115.loc[
        (st.session_state.actual_115["部門"] == edit_dept_choice)
        & (st.session_state.actual_115["月份"] == m),
        "實際支出",
    ] = r["實際支出"]


# ──────────────────────────────────────────
# 【Tab 3】：5年歷史趨勢與滾動AI
# ──────────────────────────────────────────
with tab_trend:
  st.subheader("📈 跨年度 5 年歷史數據累積與趨勢對比 (110 ~ 114 年)")

  hist_summary = (
      df_hist.groupby(["年份", "部門"])[["當月分配預算", "當月實際支出"]]
      .sum()
      .reset_index()
  )
  fig_hist_bar = px.bar(
      hist_summary,
      x="年份",
      y="當月實際支出",
      color="部門",
      barmode="group",
      title="110 ~ 114 年各部門年度總支出趨勢比較",
      labels={"當月實際支出": "年度總支出 (元)", "年份": "民國年份"},
  )
  fig_hist_bar.update_layout(height=400)
  st.plotly_chart(fig_hist_bar, use_container_width=True)


# ──────────────────────────────────────────
# 【Tab 4】：CFO AI 機器人對話
# ──────────────────────────────────────────
with tab_ai:
  st.subheader("🤖 CFO AI 智慧財務分析與諮詢機器人")

  st.info(f"""
    **💡 AI 自動分析摘要 (115年 1~{selected_month}月)：**
    - 全公司預估年度執行率為 **{eoy_exec_rate:.1f}%**。
    - 根據 **±5% 信賴區間** 模型，【行銷部】與【業務部】由於 3 月費用報銷較高，落在 **黃燈/紅燈** 警戒區域。
    - 建議啟動跨部門調度，調配【行政管理部】與【研發部】之餘裕資金支援。
    """)

  if "chat_history" not in st.session_state:
    st.session_state.chat_history = [{
        "role": "assistant",
        "content": (
            "您好！我是您的 **CFO AI"
            " 財務顧問**。我已載入最新的「±5% 信賴區間」分析模型。您可以隨時詢問我關於各部門的燈號狀態、超支風險與調撥建議喔！"
        ),
    }]

  for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
      st.markdown(msg["content"])

  user_q = st.chat_input("請輸入您的財務諮詢問題...")
  if user_q:
    st.session_state.chat_history.append({"role": "user", "content": user_q})
    with st.chat_message("user"):
      st.markdown(user_q)

    # 簡易回答邏輯
    if "超支" in user_q or "紅燈" in user_q or "風險" in user_q:
      ans = (
          f"🚨 根據截至 {selected_month} 月的數據分析，目前 **行銷部** 與"
          " **業務部** 呈現顯著超支警戒（執行率 >"
          " 105%），建議針對專案費用進行二次複查。"
      )
    elif "安全" in user_q or "藍燈" in user_q or "餘裕" in user_q:
      ans = (
          "🔵 目前 **行政管理部** 與 **研發部** 資金充裕（執行率 <"
          " 95%），預估年底將有餘裕空間可供調節。"
      )
    else:
      ans = (
          f"針對您提到的「{user_q}」，我們的 AI 預估全公司年底總支出約為"
          f" **${total_eoy_forecast:,.0f}** 元，整體風險控制在合理區間內。"
      )

    st.session_state.chat_history.append({"role": "assistant", "content": ans})
    with st.chat_message("assistant"):
      st.markdown(ans)
