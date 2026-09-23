"""
app.py
全台即時天氣監測 & 一週氣溫趨勢預報系統
整合滿分專案 (huanchen1107/taiwan-weather-map) 特色與煥哥微課程 24 環節功能
- Esri World Dark Gray Base 專業免 Key 純淨暗黑底圖
- 即時天氣特報橫幅 (Active Warning Banner)
- 多圖層切換：氣溫、風向風速、雨量、RainViewer 雷達回波
- 一週氣溫預報 (TemperatureForecasts)：地區下拉選單、MaxT/MinT 雙折線圖、一週資料表、日期地圖切換
"""
import warnings
warnings.filterwarnings("ignore")

import os
import sys
import folium
import altair as alt
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

sys.path.insert(0, os.path.dirname(__file__))

import importlib
import src.cwa_service
import src.db_service
importlib.reload(src.cwa_service)
importlib.reload(src.db_service)

from src.cwa_service import (
    get_clean_weather_data,
    get_clean_forecast_data,
    fetch_weather_warnings,
    get_radar_tile_url,
    REGION_COORDS,
)
from src.db_service import (
    init_db,
    upsert_records,
    upsert_forecast_records,
    get_all_stations,
    get_station_count,
    get_temp_distribution,
    get_forecast_regions,
    get_forecast_dates,
    get_forecast_by_region,
    get_forecast_by_date,
)

# ── 頁面設定 ─────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="🌡 台灣即時天氣監測 & 一週氣溫預報 | Airbox Style",
    page_icon="🌡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 自訂 CSS（滿分專案科技深色風）─────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Outfit', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        background-color: #0D0D1A;
        color: #E0E0E0;
    }

    .main { background-color: #0D0D1A; }

    /* 頂部 Header 安全間距與透明化 */
    header[data-testid="stHeader"] {
        background-color: transparent !important;
        pointer-events: none;
    }
    header[data-testid="stHeader"] * {
        pointer-events: auto;
    }

    .block-container {
        padding-top: 4.5rem !important;
        padding-bottom: 2.5rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
    }

    /* 標題區 */
    .hero-title {
        font-size: 2.6rem;
        font-weight: 700;
        background: linear-gradient(135deg, #E94560, #FF8C00, #4287F5);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        line-height: 1.4;
        padding-top: 0.2rem;
        padding-bottom: 0.2rem;
        margin-bottom: 0.2rem;
    }

    .hero-icon {
        -webkit-text-fill-color: initial;
        background: none;
        display: inline-block;
        margin-right: 0.3rem;
    }

    .hero-sub {
        color: #8E8EA0;
        font-size: 0.95rem;
        margin-top: 0.2rem;
        margin-bottom: 1.2rem;
    }

    /* 滿分專案特色：天氣特報橫幅 (Warning Banner) */
    .warning-banner {
        background: linear-gradient(90deg, rgba(233,69,96,0.15), rgba(255,140,0,0.15));
        border: 1px solid #E94560;
        border-radius: 12px;
        padding: 0.8rem 1.2rem;
        margin-bottom: 1.5rem;
        display: flex;
        align-items: center;
        gap: 12px;
    }

    .warning-banner-clear {
        background: rgba(46, 204, 113, 0.08);
        border: 1px solid rgba(46, 204, 113, 0.3);
        border-radius: 12px;
        padding: 0.6rem 1.2rem;
        margin-bottom: 1.5rem;
        color: #2ECC71;
        font-size: 0.9rem;
    }

    /* 統計卡片 */
    .stat-card {
        background: linear-gradient(145deg, #1A1A2E, #16213E);
        border: 1px solid #2A2A4A;
        border-radius: 16px;
        padding: 1.2rem 1.5rem;
        text-align: center;
        box-shadow: 0 4px 20px rgba(0,0,0,0.4);
        transition: transform 0.2s ease;
    }

    .stat-card:hover { transform: translateY(-3px); }

    .stat-value {
        font-size: 2.2rem;
        font-weight: 700;
        line-height: 1;
    }

    .stat-label {
        font-size: 0.8rem;
        color: #888;
        margin-top: 0.4rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    /* 側邊欄 */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1A1A2E 0%, #16213E 100%);
        border-right: 1px solid #2A2A4A;
    }

    /* 分頁 Tabs 樣式 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 12px;
        background-color: transparent;
    }

    .stTabs [data-baseweb="tab"] {
        height: 48px;
        background-color: #1A1A2E;
        border-radius: 10px 10px 0 0;
        border: 1px solid #2A2A4A;
        padding: 0 20px;
        color: #888;
        font-weight: 600;
        font-size: 1rem;
    }

    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, rgba(233,69,96,0.2), rgba(66,135,245,0.2)) !important;
        border-color: #E94560 !important;
        color: #FFF !important;
    }

    /* 按鈕 */
    .stButton>button {
        background: linear-gradient(135deg, #E94560, #C0392B);
        color: white;
        border: none;
        border-radius: 10px;
        font-weight: 600;
        transition: all 0.2s;
        width: 100%;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(233,69,96,0.4);
    }

    hr { border-color: #2A2A4A; }
</style>
""", unsafe_allow_html=True)


# ── 工具函數 ─────────────────────────────────────────────────────────────────
def temp_to_color(temp: float) -> str:
    """溫度對應顏色階梯（符合煥哥課程標準：<20 藍, 20-25 綠, 25-30 橘, >=30 紅）"""
    if temp >= 30:
        return "#FF4444"
    elif temp >= 25:
        return "#FF8C00"
    elif temp >= 20:
        return "#2ECC71"
    else:
        return "#4287F5"


def temp_to_radius(temp: float) -> int:
    """溫度越高，圓圈半徑越大"""
    if temp >= 30:
        return 10
    elif temp >= 25:
        return 8
    else:
        return 6


@st.cache_data(ttl=300, show_spinner=False)
def load_all_data():
    """載入並快取即時測站與一週預報數據（5 分鐘 TTL）"""
    init_db()
    # 1. 即時測站觀測 (Gate 1 & 2)
    realtime_records = get_clean_weather_data()
    upsert_records(realtime_records)

    # 2. 一週天氣預報 (煥哥課程 4~9 環節)
    forecast_records = get_clean_forecast_data()
    if forecast_records:
        upsert_forecast_records(forecast_records)

    # 3. 天氣特報
    warnings_list = fetch_weather_warnings()

    # 4. 雷達圖磚 URL
    radar_url = get_radar_tile_url()

    return {
        "stations": get_all_stations(),
        "warnings": warnings_list,
        "radar_url": radar_url,
    }


def build_realtime_map(stations: list, layer_mode: str, radar_url: str = None) -> folium.Map:
    """
    建立即時監測地圖（採用滿分專案指定的 Esri World Dark Gray Base 專業免 Key 暗黑底圖）。
    支援多圖層切換：氣溫、風向風速、雨量、RainViewer 雷達回波。
    """
    m = folium.Map(
        location=[23.7, 121.0],
        zoom_start=7,
        tiles=None,
        prefer_canvas=True,
    )

    # 滿分專案特色：使用 Esri World Dark Gray Base 底圖（免 API Key、零浮水印）
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}",
        attr="Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ",
        name="Esri Dark Gray",
        overlay=False,
        control=False,
    ).add_to(m)

    # 雷達回波疊加
    if layer_mode == "📡 即時雷達回波 (RainViewer)" and radar_url:
        folium.TileLayer(
            tiles=radar_url,
            attr="RainViewer Radar",
            name="雷達回波",
            overlay=True,
            opacity=0.75,
        ).add_to(m)

    # 測站標記
    for s in stations:
        temp   = s["air_temperature"]
        name   = s["station_name"]
        color  = temp_to_color(temp)
        r      = temp_to_radius(temp)
        obs    = s["obs_time"][:16].replace("T", " ")
        wind_s = s.get("wind_speed", 0.0)
        wind_d = s.get("wind_direction", 0.0)
        humid  = s.get("relative_humidity", 0.0)
        precip = s.get("precipitation", 0.0)
        desc   = s.get("weather_desc", "")

        popup_html = f"""
        <div style="font-family:Outfit,sans-serif;background:#16213E;
                    color:#E0E0E0;border-radius:10px;padding:12px;
                    width:210px;border:1px solid {color};">
            <div style="font-size:1.1rem;font-weight:700;">{name} {desc}</div>
            <div style="color:{color};font-size:1.8rem;font-weight:700;margin:4px 0;">
                {temp}°C
            </div>
            <div style="color:#AAA;font-size:0.8rem;line-height:1.6;">
                💧 相對濕度：{humid}%<br>
                💨 風速風向：{wind_s} m/s ({wind_d}°)<br>
                🌧 累積雨量：{precip} mm<br>
                📍 座標：{s['latitude']:.3f}°N, {s['longitude']:.3f}°E<br>
                🕐 時間：{obs}
            </div>
        </div>
        """

        if layer_mode == "🧭 風向風速":
            tooltip_text = f"{name}: 風速 {wind_s} m/s ({wind_d}°)"
            # 風速分級顏色
            w_color = "#4287F5" if wind_s < 3 else ("#FF8C00" if wind_s < 8 else "#FF4444")
            folium.CircleMarker(
                location=[s["latitude"], s["longitude"]],
                radius=max(4, min(14, int(wind_s * 2 + 4))),
                color=w_color,
                fill=True,
                fill_color=w_color,
                fill_opacity=0.8,
                weight=1.5,
                tooltip=tooltip_text,
                popup=folium.Popup(popup_html, max_width=240),
            ).add_to(m)

        elif layer_mode == "🌧️ 雨量觀測":
            tooltip_text = f"{name}: 降雨量 {precip} mm"
            p_color = "#4287F5" if precip == 0 else ("#FF8C00" if precip < 10 else "#FF4444")
            folium.CircleMarker(
                location=[s["latitude"], s["longitude"]],
                radius=6 if precip == 0 else 10,
                color=p_color,
                fill=True,
                fill_color=p_color,
                fill_opacity=0.8,
                weight=1.5,
                tooltip=tooltip_text,
                popup=folium.Popup(popup_html, max_width=240),
            ).add_to(m)

        else:
            # 氣溫或雷達模式
            tooltip_text = f"{name}: {temp}°C (濕度 {humid}%)"
            folium.CircleMarker(
                location=[s["latitude"], s["longitude"]],
                radius=r,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.85,
                weight=1.5,
                tooltip=tooltip_text,
                popup=folium.Popup(popup_html, max_width=240),
            ).add_to(m)

    return m


def build_forecast_map(forecast_by_date_list: list, selected_date: str) -> folium.Map:
    """
    建立一週氣溫預報分區地圖（煥哥課程 17 & 18 環節）。
    在地圖上標記全台 6 大主要分區，依照當日平均溫度自動著色，Popup 標示 MinT / MaxT。
    """
    m = folium.Map(
        location=[23.7, 121.0],
        zoom_start=7,
        tiles=None,
        prefer_canvas=True,
    )

    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}",
        attr="Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ",
        name="Esri Dark Gray",
        overlay=False,
    ).add_to(m)

    # 篩選 6 大分區標記在中心點
    for r in forecast_by_date_list:
        reg_name = r["regionName"]
        if reg_name in REGION_COORDS:
            lat, lon = REGION_COORDS[reg_name]
            min_t = r["minT"]
            max_t = r["maxT"]
            avg_t = round((min_t + max_t) / 2, 1)
            color = temp_to_color(avg_t)

            popup_html = f"""
            <div style="font-family:Outfit,sans-serif;background:#16213E;color:#FFF;
                        border-radius:10px;padding:12px;width:180px;border:1px solid {color};">
                <div style="font-size:1.1rem;font-weight:700;">{reg_name}</div>
                <div style="color:#888;font-size:0.8rem;margin-top:2px;">預報日期：{selected_date}</div>
                <hr style="border-color:#2A2A4A;margin:8px 0;">
                <div style="display:flex;justify-content:space-between;">
                    <div>最低溫：<span style="color:#4287F5;font-weight:700;">{min_t}°C</span></div>
                    <div>最高溫：<span style="color:#FF4444;font-weight:700;">{max_t}°C</span></div>
                </div>
                <div style="margin-top:4px;color:{color};font-weight:600;font-size:0.9rem;">
                    平均溫：{avg_t}°C
                </div>
            </div>
            """

            folium.CircleMarker(
                location=[lat, lon],
                radius=18,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.85,
                weight=3,
                tooltip=f"<b>{reg_name}</b>: {min_t}°C ~ {max_t}°C (均溫 {avg_t}°C)",
                popup=folium.Popup(popup_html, max_width=220),
            ).add_to(m)

            # 加上文字標籤
            folium.Marker(
                location=[lat, lon],
                icon=folium.DivIcon(
                    html=f"""
                    <div style="font-family:Outfit,sans-serif;font-weight:700;font-size:11px;
                                color:#FFF;text-shadow:0 0 4px #000;margin-top:-6px;margin-left:-25px;
                                width:50px;text-align:center;">
                        {reg_name[:2]}<br>{avg_t}°
                    </div>
                    """
                )
            ).add_to(m)

    return m


# ── 主流程資料載入 ───────────────────────────────────────────────────────────
with st.spinner("🛰 正在同步中央氣象署最新測站與預報資料..."):
    data = load_all_data()

stations = data["stations"]
warnings_list = data["warnings"]
radar_url = data["radar_url"]

# ── 頂部標題區 ───────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero-title"><span class="hero-icon">🌡</span>台灣即時天氣監測 & 氣象預報系統</div>
<div class="hero-sub">
    類 Windy 風格專業深色地圖 · 中央氣象署 CWA 局屬測站與一週預報 · SQLite 持久化
</div>
""", unsafe_allow_html=True)

# 滿分專案特色：天氣特報橫幅 (Active Warning Banner)
if warnings_list:
    warning_text = " · ".join([f"⚠️ <b>{w['event']}</b>: {w['headline']}" for w in warnings_list])
    st.markdown(f"""
    <div class="warning-banner">
        <span>📢</span>
        <div>{warning_text}</div>
    </div>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
    <div class="warning-banner-clear">
        🟢 目前全台無生效中的天氣特報 (CWA 局屬特報檢測正常)
    </div>
    """, unsafe_allow_html=True)


# ── 側邊欄 ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ 系統控制台")
    st.markdown("---")

    if st.button("🔄 重新整理所有數據", help="清除快取並重新向 CWA API 抓取最新即時與預報資料"):
        st.cache_data.clear()
        st.rerun()

    st.markdown("### 🗺 溫度圖例說明")
    st.markdown("""
    <div style="line-height:2.2;font-size:0.9rem;">
        <span style="display:inline-block;width:12px;height:12px;border-radius:50%;
            background:#FF4444;margin-right:6px;"></span>
        🔴 高溫 ≥ 30°C<br>
        <span style="display:inline-block;width:12px;height:12px;border-radius:50%;
            background:#FF8C00;margin-right:6px;"></span>
        🟠 暖溫 25~29°C<br>
        <span style="display:inline-block;width:12px;height:12px;border-radius:50%;
            background:#2ECC71;margin-right:6px;"></span>
        🟢 舒適 20~24°C<br>
        <span style="display:inline-block;width:12px;height:12px;border-radius:50%;
            background:#4287F5;margin-right:6px;"></span>
        🔵 涼溫 < 20°C
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 📡 資料來源架構")
    st.markdown("""
    <div style="color:#888;font-size:0.8rem;line-height:1.6;">
        <b>即時觀測：</b>CWA <code>O-A0003-001</code><br>
        <b>一週預報：</b>CWA <code>F-D0047-091</code><br>
        <b>天氣特報：</b>CWA <code>W-C0033-001</code><br>
        <b>雷達回波：</b>RainViewer XYZ Tiles<br>
        <b>地圖底圖：</b>Esri World Dark Gray<br>
        <b>資料庫：</b>SQLite <code>data/weather.db</code>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 🤖 LINE Bot 整合")
    st.markdown("""
    <div style="color:#888;font-size:0.8rem;">
        已部署 <code>bot.py</code> 支援 LINE Flex Message 即時查詢測站天氣！
    </div>
    """, unsafe_allow_html=True)


# ── 兩大核心分頁 ─────────────────────────────────────────────────────────────
tab_realtime, tab_forecast = st.tabs([
    "🛰️ 即時氣象監測 (Airbox 347 測站 / 滿分地圖)",
    "📅 一週氣溫趨勢預報 (煥哥課程 24 環節 滿分實作)"
])


# ═════════════════════════════════════════════════════════════════════════════
# 分頁 1: 即時氣象監測 (Airbox 347 測站 / 滿分專案多圖層)
# ═════════════════════════════════════════════════════════════════════════════
with tab_realtime:
    # 頂部控制列：圖層切換與測站搜尋
    ctrl_col1, ctrl_col2 = st.columns([2, 1])
    with ctrl_col1:
        layer_mode = st.radio(
            "地圖圖層模式 (Layer Mode)",
            ["🌡️ 氣溫分佈", "🧭 風向風速", "🌧️ 雨量觀測", "📡 即時雷達回波 (RainViewer)"],
            horizontal=True,
        )
    with ctrl_col2:
        search_query = st.text_input("🔍 搜尋即時測站", placeholder="輸入測站名稱 (例：台北、花蓮...)")

    # 搜尋過濾
    if search_query:
        filtered = [s for s in stations if search_query in s["station_name"]]
        if not filtered:
            st.warning(f"⚠️ 找不到「{search_query}」測站")
            filtered = stations
    else:
        filtered = stations

    # 統計卡片列
    dist = get_temp_distribution()
    total = get_station_count()

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-value" style="color:#4287F5;">{total}</div>
            <div class="stat-label">有效測站數</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-value" style="color:#FF4444;">{dist.get('hot', 0)}</div>
            <div class="stat-label">高溫站 (≥30°C)</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-value" style="color:#FF8C00;">{dist.get('warm', 0)}</div>
            <div class="stat-label">暖溫站 (20~29°C)</div>
        </div>
        """, unsafe_allow_html=True)
    with c4:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-value" style="color:#2ECC71;">{dist.get('cool', 0)}</div>
            <div class="stat-label">涼溫站 (<20°C)</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # 地圖與右側資訊欄
    map_col, info_col = st.columns([3, 1])

    with map_col:
        folium_map = build_realtime_map(filtered, layer_mode, radar_url)
        st_folium(
            folium_map,
            width="100%",
            height=580,
            returned_objects=["last_object_clicked_popup"],
            key=f"realtime_map_{layer_mode}",
        )

    with info_col:
        st.markdown("### 📊 全台氣象概覽")
        st.markdown(f"""
        <div class="stat-card" style="margin-bottom:10px;">
            <div class="stat-value" style="color:#FF4444;">
                {dist.get('max_temp', '--')}°C
            </div>
            <div class="stat-label">全台最高溫</div>
        </div>
        <div class="stat-card" style="margin-bottom:10px;">
            <div class="stat-value" style="color:#4287F5;">
                {dist.get('min_temp', '--')}°C
            </div>
            <div class="stat-label">全台最低溫</div>
        </div>
        <div class="stat-card" style="margin-bottom:10px;">
            <div class="stat-value" style="color:#FF8C00;">
                {dist.get('avg_temp', '--')}°C
            </div>
            <div class="stat-label">全台平均溫</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("### 🏆 高溫熱點 Top 5")
        top_hot = sorted(filtered, key=lambda x: x["air_temperature"], reverse=True)[:5]
        for i, s in enumerate(top_hot, 1):
            c_val = temp_to_color(s["air_temperature"])
            st.markdown(f"""
            <div style="background:#1A1A2E;border-radius:8px;padding:8px 12px;
                        margin-bottom:6px;border-left:3px solid {c_val};">
                <span style="color:#888;font-size:0.75rem;">#{i}</span>
                <b style="margin-left:6px;">{s['station_name']}</b>
                <span style="float:right;color:{c_val};font-weight:700;">
                    {s['air_temperature']}°C
                </span>
            </div>
            """, unsafe_allow_html=True)

    # 測站詳細表格
    with st.expander("📋 展開查看所有 347 個測站即時觀測資料表", expanded=False):
        df_realtime = pd.DataFrame(filtered)
        if not df_realtime.empty:
            cols_map = {
                "station_name": "測站名稱",
                "station_id": "測站代碼",
                "air_temperature": "氣溫(°C)",
                "wind_speed": "風速(m/s)",
                "wind_direction": "風向(°)",
                "relative_humidity": "濕度(%)",
                "precipitation": "降雨量(mm)",
                "latitude": "緯度",
                "longitude": "經度",
                "obs_time": "觀測時間",
            }
            show_cols = [c for c in cols_map.keys() if c in df_realtime.columns]
            df_display = df_realtime[show_cols].rename(columns=cols_map)
            st.dataframe(
                df_display.sort_values("氣溫(°C)", ascending=False),
                use_container_width=True,
                hide_index=True,
            )


# ═════════════════════════════════════════════════════════════════════════════
# 分頁 2: 一週氣溫趨勢預報 (煥哥課程 24 環節 滿分實作)
# ═════════════════════════════════════════════════════════════════════════════
with tab_forecast:
    forecast_regions = get_forecast_regions()
    forecast_dates   = get_forecast_dates()

    if not forecast_regions or not forecast_dates:
        st.info("⚠️ 正在從中央氣象署抓取預報數據，請稍候...")
    else:
        # 環節 13 & 18：控制項（下拉選單選擇地區、選擇日期）
        f_col1, f_col2 = st.columns([1, 1])

        with f_col1:
            selected_region = st.selectbox(
                "📍 選擇地區 (Select Region) [環節 13 & 16]",
                options=forecast_regions,
                index=0,
                help="可選擇 6 大分區（北部、中部、南部、東北部、東部、東南部）或 22 縣市",
            )

        with f_col2:
            selected_date = st.selectbox(
                "🗓 選擇日期顯示地圖 (Select Date) [環節 18]",
                options=forecast_dates,
                index=0,
                help="選擇日期在地圖上即時呈現全台各區氣溫分佈",
            )

        st.markdown("---")

        # 環節 14 & 15：一週折線圖與表格整合
        region_forecasts = get_forecast_by_region(selected_region)
        df_region = pd.DataFrame(region_forecasts)

        if not df_region.empty:
            df_region["溫差"] = (df_region["maxT"] - df_region["minT"]).round(1)
            df_region["日期簡稱"] = df_region["dataDate"].apply(lambda x: x[5:])

            chart_col, table_col = st.columns([3, 2])

            with chart_col:
                st.markdown(f"### 📈 {selected_region} · 一週最高與最低氣溫走勢圖 [環節 14]")

                # 準備 Altair 繪圖資料 (Melt 格式)
                melted = df_region.melt(
                    id_vars=["日期簡稱", "dataDate"],
                    value_vars=["maxT", "minT"],
                    var_name="類型",
                    value_name="氣溫",
                )
                melted["類型名稱"] = melted["類型"].map({"maxT": "最高溫 MaxT", "minT": "最低溫 MinT"})

                line_chart = (
                    alt.Chart(melted)
                    .mark_line(point=alt.OverlayMarkDef(size=60, filled=True), strokeWidth=3)
                    .encode(
                        x=alt.X("日期簡稱:N", title="日期", sort=None),
                        y=alt.Y("氣溫:Q", title="氣溫 (°C)", scale=alt.Scale(zero=False)),
                        color=alt.Color(
                            "類型名稱:N",
                            scale=alt.Scale(
                                domain=["最高溫 MaxT", "最低溫 MinT"],
                                range=["#FF4444", "#4287F5"]
                            ),
                            legend=alt.Legend(title="溫度指標", orient="top"),
                        ),
                        tooltip=[
                            alt.Tooltip("dataDate:N", title="完整日期"),
                            alt.Tooltip("類型名稱:N", title="項目"),
                            alt.Tooltip("氣溫:Q", title="氣溫 (°C)"),
                        ],
                    )
                    .properties(height=320)
                    .configure_view(strokeWidth=0)
                    .configure_axis(
                        gridColor="#2A2A4A",
                        domainColor="#2A2A4A",
                        tickColor="#2A2A4A",
                        labelColor="#AAA",
                        titleColor="#FFF",
                    )
                    .configure_legend(
                        labelColor="#FFF",
                        titleColor="#FFF",
                    )
                )

                st.altair_chart(line_chart, use_container_width=True)

            with table_col:
                st.markdown(f"### 📋 {selected_region} · 一週預報資料表格 [環節 15]")
                display_df = df_region[["dataDate", "minT", "maxT", "溫差"]].rename(
                    columns={
                        "dataDate": "預報日期",
                        "minT": "最低溫 (°C)",
                        "maxT": "最高溫 (°C)",
                        "溫差": "日溫差 (°C)",
                    }
                )
                st.dataframe(display_df, use_container_width=True, hide_index=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # 環節 17 & 18：全台預報地圖視覺化 (Folium + Streamlit)
        st.markdown(f"### 🗺 台灣分區氣溫預報地圖 · 【{selected_date}】 [環節 17 & 18]")
        date_forecasts = get_forecast_by_date(selected_date)

        f_map_col, f_summary_col = st.columns([3, 1])

        with f_map_col:
            forecast_map = build_forecast_map(date_forecasts, selected_date)
            st_folium(
                forecast_map,
                width="100%",
                height=520,
                key=f"forecast_map_{selected_date}",
            )

        with f_summary_col:
            st.markdown(f"#### 🔍 {selected_date} 分區預報")
            reg_only = [r for r in date_forecasts if r["regionName"] in REGION_COORDS]
            for r in reg_only:
                avg_val = round((r["minT"] + r["maxT"]) / 2, 1)
                color = temp_to_color(avg_val)
                st.markdown(f"""
                <div style="background:#1A1A2E;border-radius:8px;padding:8px 12px;
                            margin-bottom:8px;border-left:3px solid {color};">
                    <b>{r['regionName']}</b>
                    <span style="float:right;color:{color};font-weight:700;">{avg_val}°C</span><br>
                    <span style="color:#888;font-size:0.8rem;">
                        最低 {r['minT']}°C ~ 最高 {r['maxT']}°C
                    </span>
                </div>
                """, unsafe_allow_html=True)

        # 環節 19：完整成果展示總表
        with st.expander("📊 查看全台所有地區一週氣溫預報完整總表 (Taiwan Weather Dashboard)", expanded=False):
            all_f_df = pd.DataFrame(get_forecast_by_date(selected_date))
            if not all_f_df.empty:
                st.dataframe(
                    all_f_df.rename(columns={"regionName": "地區名稱", "dataDate": "預報日期", "minT": "最低溫(°C)", "maxT": "最高溫(°C)"})[
                        ["地區名稱", "預報日期", "最低溫(°C)", "最高溫(°C)"]
                    ],
                    use_container_width=True,
                    hide_index=True,
                )


# ── 頁腳 ─────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("""
<div style="text-align:center;color:#666;font-size:0.85rem;padding:12px 0;">
    🌡 <b>台灣即時天氣監測 & 氣象預報系統</b> · L2CWAv2<br>
    資料來源：<a href="https://opendata.cwa.gov.tw" target="_blank" style="color:#E94560;text-decoration:none;">中央氣象署開放資料平臺 (CWA Open Data)</a>
    · 雨量雷達：<a href="https://www.rainviewer.com/" target="_blank" style="color:#4287F5;text-decoration:none;">RainViewer</a>
</div>
""", unsafe_allow_html=True)
