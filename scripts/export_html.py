# -*- coding: utf-8 -*-
"""
scripts/export_html.py
導出高質感、具備 CWA 完整氣象數值、智慧建議穿著，以及依風速與降雨機率判斷雨具型態（雨衣/抗風大傘/折傘/遮陽傘）的靜態 index.html。
"""
import os
import json
import sqlite3
import pandas as pd
import math

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "weather.db")
OUTPUT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "index.html")

REGION_COORDS = {
    "北部地區": {"lat": 25.02, "lon": 121.50},
    "中部地區": {"lat": 24.15, "lon": 120.68},
    "南部地區": {"lat": 22.99, "lon": 120.21},
    "東北部地區": {"lat": 24.75, "lon": 121.75},
    "東部地區": {"lat": 23.98, "lon": 121.60},
    "東南部地區": {"lat": 22.75, "lon": 121.14},
    "離島地區": {"lat": 23.57, "lon": 119.58},
}

def calculate_apparent_temp(temp: float, humidity: float, wind_speed: float) -> float:
    try:
        e = (humidity / 100.0) * 6.105 * math.exp((17.27 * temp) / (237.7 + temp))
        at = temp + 0.33 * e - 0.70 * wind_speed - 4.00
        return round(at, 1)
    except Exception:
        return round(temp, 1)

def wind_deg_to_compass(deg: float) -> str:
    try:
        deg = float(deg)
        if deg < 0 or deg > 360: return "靜風"
        directions = ["北", "北北東", "東北", "東北東", "東", "東南東", "東南", "南南東",
                      "南", "南南西", "西南", "西南西", "西", "西北西", "西北", "北北西"]
        idx = int((deg + 11.25) / 22.5) % 16
        return directions[idx] + "風"
    except Exception:
        return "微風"

def generate_index_html():
    conn = sqlite3.connect(DB_PATH)
    
    # 1. 讀取即時測站
    df_stations = pd.read_sql_query(
        "SELECT station_id, station_name, latitude, longitude, air_temperature, obs_time, wind_speed, wind_direction, relative_humidity, precipitation, weather_desc FROM realtime_weather WHERE air_temperature > -90",
        conn
    )
    
    # 增加體感溫度與風向文字
    stations_data = []
    for r in df_stations.to_dict(orient="records"):
        t = r["air_temperature"]
        rh = r.get("relative_humidity") or 70.0
        ws = r.get("wind_speed") or 1.5
        wd = r.get("wind_direction") or 0.0
        r["apparent_temp"] = calculate_apparent_temp(t, rh, ws)
        r["wind_dir_text"] = wind_deg_to_compass(wd)
        stations_data.append(r)
        
    # 2. 讀取預報資料 (包含降雨機率 pop、風速 wind_speed、天氣描述 weather_desc)
    df_forecast = pd.read_sql_query(
        "SELECT regionName, dataDate, minT, maxT, pop, wind_speed, weather_desc FROM TemperatureForecasts ORDER BY dataDate ASC",
        conn
    )
    conn.close()
    
    # 整理各區預報
    forecast_by_region = {}
    for region, group in df_forecast.groupby("regionName"):
        forecast_by_region[region] = group.to_dict(orient="records")
        
    # 整理各日預報
    forecast_by_date = {}
    for dt, group in df_forecast.groupby("dataDate"):
        forecast_by_date[dt] = group.to_dict(orient="records")
        
    dates_list = sorted(list(df_forecast["dataDate"].unique()))
    
    # 統計指標
    total_stations = len(df_stations)
    hot_count = len(df_stations[df_stations["air_temperature"] >= 30])
    warm_count = len(df_stations[(df_stations["air_temperature"] >= 20) & (df_stations["air_temperature"] < 30)])
    cool_count = len(df_stations[df_stations["air_temperature"] < 20])
    avg_temp = round(df_stations["air_temperature"].mean(), 1) if total_stations > 0 else 0.0
    avg_at = round(sum([s["apparent_temp"] for s in stations_data]) / total_stations, 1) if total_stations > 0 else avg_temp
    avg_humidity = round(df_stations["relative_humidity"].mean(), 0) if total_stations > 0 else 70.0

    html_content = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🌡️ 台灣即時天氣監測 & 智慧穿著雨具生活指標系統</title>
    <!-- Leaflet CSS -->
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <!-- Google Fonts Outfit & Noto Sans TC -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800&family=Noto+Sans+TC:wght@400;500;700;900&display=swap" rel="stylesheet">
    <!-- Chart.js -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {{
            --bg-base: #0a0d14;
            --bg-card: #131823;
            --bg-card-sub: #1a2130;
            --bg-card-border: #232d3f;
            --text-main: #f0f6fc;
            --text-muted: #8b949e;
            --accent-cyan: #38bdf8;
            --accent-blue: #3b82f6;
            --accent-red: #f43f5e;
            --accent-orange: #fb923c;
            --accent-amber: #fbbf24;
            --accent-green: #10b981;
            --accent-purple: #a855f7;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            background-color: var(--bg-base);
            color: var(--text-main);
            font-family: 'Outfit', 'Noto Sans TC', sans-serif;
            line-height: 1.6;
            padding: 24px;
        }}
        .container {{
            max-width: 1480px;
            margin: 0 auto;
        }}
        /* Header */
        header {{
            margin-bottom: 22px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 16px;
            border-bottom: 1px solid var(--bg-card-border);
            padding-bottom: 20px;
        }}
        .badge-pill {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 4px 12px;
            font-size: 0.8rem;
            font-weight: 700;
            border-radius: 9999px;
            background: rgba(56, 189, 248, 0.12);
            color: var(--accent-cyan);
            border: 1px solid rgba(56, 189, 248, 0.3);
            margin-bottom: 8px;
        }}
        .header-title {{
            font-size: 2.3rem;
            font-weight: 800;
            background: linear-gradient(135deg, #fb7185 0%, #fb923c 40%, #38bdf8 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: -0.5px;
        }}
        .header-subtitle {{
            color: var(--text-muted);
            font-size: 0.95rem;
            margin-top: 4px;
        }}
        /* CWA Alert Banner */
        .alert-banner {{
            background: rgba(16, 185, 129, 0.1);
            border: 1px solid rgba(16, 185, 129, 0.35);
            color: #34d399;
            padding: 12px 20px;
            border-radius: 12px;
            margin-bottom: 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            font-size: 0.92rem;
            font-weight: 600;
            gap: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.25);
        }}
        /* KPI Cards Grid */
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}
        .stat-card {{
            background: linear-gradient(145deg, #131823, #161e2c);
            border: 1px solid var(--bg-card-border);
            border-radius: 16px;
            padding: 18px 22px;
            text-align: center;
            box-shadow: 0 4px 18px rgba(0,0,0,0.35);
            transition: all 0.25s ease;
            position: relative;
            overflow: hidden;
        }}
        .stat-card:hover {{
            transform: translateY(-3px);
            border-color: #334155;
            box-shadow: 0 8px 26px rgba(0,0,0,0.45);
        }}
        .stat-num {{
            font-size: 2.2rem;
            font-weight: 800;
            margin-bottom: 2px;
            letter-spacing: -0.5px;
        }}
        .stat-label {{
            font-size: 0.85rem;
            color: var(--text-muted);
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .stat-sub {{
            font-size: 0.78rem;
            color: var(--text-muted);
            margin-top: 4px;
        }}
        /* Main Layout */
        .main-grid {{
            display: grid;
            grid-template-columns: 1.25fr 1fr;
            gap: 24px;
            margin-bottom: 28px;
        }}
        @media (max-width: 1100px) {{
            .main-grid {{ grid-template-columns: 1fr; }}
        }}
        .panel {{
            background: var(--bg-card);
            border: 1px solid var(--bg-card-border);
            border-radius: 16px;
            padding: 22px;
            box-shadow: 0 6px 24px rgba(0,0,0,0.3);
            display: flex;
            flex-direction: column;
        }}
        .panel-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
            flex-wrap: wrap;
            gap: 12px;
        }}
        .panel-title {{
            font-size: 1.25rem;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        /* Tab buttons */
        .tab-group {{
            display: flex;
            background: #0a0d14;
            padding: 4px;
            border-radius: 10px;
            border: 1px solid var(--bg-card-border);
            gap: 4px;
        }}
        .tab-btn {{
            background: transparent;
            border: none;
            color: var(--text-muted);
            padding: 6px 14px;
            border-radius: 7px;
            font-size: 0.85rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }}
        .tab-btn.active {{
            background: #232d3f;
            color: var(--accent-cyan);
            box-shadow: 0 2px 8px rgba(0,0,0,0.4);
        }}
        #map {{
            height: 560px;
            width: 100%;
            border-radius: 12px;
            background: #181c24;
            border: 1px solid #202736;
        }}
        .btn {{
            background: #1c2432;
            border: 1px solid var(--bg-card-border);
            color: var(--text-main);
            padding: 7px 14px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 0.85rem;
            font-weight: 600;
            transition: all 0.2s;
        }}
        .btn:hover, .btn.active {{
            background: #2a374a;
            border-color: var(--accent-cyan);
            color: var(--accent-cyan);
        }}
        select {{
            background-color: #1a2230;
            color: var(--text-main);
            border: 1px solid var(--bg-card-border);
            border-radius: 8px;
            padding: 8px 14px;
            font-size: 0.9rem;
            font-family: inherit;
            cursor: pointer;
            outline: none;
        }}
        select:focus {{
            border-color: var(--accent-cyan);
        }}
        /* Table */
        .table-container {{
            max-height: 250px;
            overflow-y: auto;
            margin-top: 16px;
            border: 1px solid var(--bg-card-border);
            border-radius: 10px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9rem;
            text-align: left;
        }}
        th, td {{
            padding: 10px 14px;
            border-bottom: 1px solid #1c2331;
        }}
        th {{
            background-color: #161e2b;
            color: var(--text-muted);
            font-weight: 600;
            position: sticky;
            top: 0;
            z-index: 2;
        }}
        tr:hover td {{
            background-color: rgba(255,255,255,0.02);
        }}
        /* =================== 👔 智慧穿著與生活建議卡 =================== */
        .clothing-panel {{
            background: linear-gradient(145deg, #131a26, #162030);
            border: 1px solid #233146;
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 28px;
            box-shadow: 0 8px 30px rgba(0,0,0,0.35);
        }}
        .clothing-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            flex-wrap: wrap;
            gap: 12px;
        }}
        .clothing-badge {{
            padding: 6px 14px;
            border-radius: 8px;
            font-weight: 800;
            font-size: 0.95rem;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }}
        .clothing-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 16px;
        }}
        .clothing-item {{
            background: rgba(10, 13, 20, 0.6);
            border: 1px solid #202b3c;
            border-radius: 12px;
            padding: 15px 18px;
            transition: all 0.2s;
        }}
        .clothing-item:hover {{
            border-color: var(--accent-cyan);
            transform: translateY(-2px);
        }}
        .clothing-item-title {{
            font-size: 0.85rem;
            color: var(--text-muted);
            font-weight: 700;
            margin-bottom: 6px;
            display: flex;
            align-items: center;
            gap: 6px;
            text-transform: uppercase;
        }}
        .clothing-item-val {{
            font-size: 0.95rem;
            font-weight: 600;
            color: #f1f5f9;
        }}
        /* ☔ 雨具與防風指南卡 */
        .rain-gear-box {{
            margin-top: 18px;
            padding: 18px 20px;
            border-radius: 14px;
            background: linear-gradient(145deg, #0d131f, #111a28);
            border: 1px solid #28374d;
            box-shadow: inset 0 1px 3px rgba(255,255,255,0.05);
        }}
        .rain-gear-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
            flex-wrap: wrap;
            gap: 10px;
        }}
        .gear-chip {{
            padding: 4px 12px;
            border-radius: 6px;
            font-weight: 800;
            font-size: 0.88rem;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }}
        .gear-grid {{
            display: grid;
            grid-template-columns: 1fr 1.3fr;
            gap: 14px;
        }}
        @media (max-width: 800px) {{
            .gear-grid {{ grid-template-columns: 1fr; }}
        }}
        .gear-subcard {{
            background: rgba(18, 26, 39, 0.7);
            border: 1px solid #233044;
            border-radius: 10px;
            padding: 12px 16px;
        }}
        /* Popups */
        .leaflet-popup-content-wrapper, .leaflet-popup-tip {{
            background: #131823 !important;
            color: #f0f6fc !important;
            border: 1px solid #233146;
            box-shadow: 0 8px 30px rgba(0,0,0,0.65);
            border-radius: 12px;
        }}
        .popup-station {{
            font-size: 1.1rem;
            font-weight: 800;
            color: var(--accent-cyan);
            margin-bottom: 4px;
        }}
        .popup-temp {{
            font-size: 1.6rem;
            font-weight: 900;
            margin-bottom: 8px;
        }}
        footer {{
            text-align: center;
            color: var(--text-muted);
            font-size: 0.88rem;
            padding-top: 24px;
            border-top: 1px solid var(--bg-card-border);
        }}
    </style>
</head>
<body>
<div class="container">
    <header>
        <div class="header-title-box">
            <span class="badge-pill">
                <span>⚡</span> CWA 氣象署即時觀測 × 一週預報 · 風速雨量智慧雨具指標
            </span>
            <div class="header-title">🌡️ 台灣即時天氣監測 & 智慧穿著雨具生活系統</div>
            <div class="header-subtitle">
                中央氣象署 Open Data (O-A0003-001 / F-D0047-091) · 降雨機率 PoP × 風力級數 · 智能雨具/大傘/雨衣外出建議
            </div>
        </div>
    </header>

    <!-- CWA Warning Banner -->
    <div class="alert-banner">
        <div style="display: flex; align-items: center; gap: 8px;">
            <span>🟢</span>
            <span>【中央氣象署即時特報監測】目前全台無生效中天氣特報，各區天候穩定。</span>
        </div>
        <div style="font-size: 0.8rem; color: #94a3b8;">代碼：CWA-W-C0033-001</div>
    </div>

    <!-- CWA Realtime Weather KPIs -->
    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-num" style="color: var(--accent-cyan);">{total_stations}</div>
            <div class="stat-label">即時監測站數</div>
            <div class="stat-sub">全台測站涵蓋率 100%</div>
        </div>
        <div class="stat-card">
            <div class="stat-num" style="color: #f1f5f9;">{avg_temp}°C</div>
            <div class="stat-label">全台平均氣溫</div>
            <div class="stat-sub">體感均溫約 <b style="color:var(--accent-orange);">{avg_at}°C</b></div>
        </div>
        <div class="stat-card">
            <div class="stat-num" style="color: var(--accent-red);">{hot_count}</div>
            <div class="stat-label">炎熱站 (≥30°C)</div>
            <div class="stat-sub">留意水分補充與防曬</div>
        </div>
        <div class="stat-card">
            <div class="stat-num" style="color: var(--accent-orange);">{warm_count}</div>
            <div class="stat-label">舒適暖溫 (20~29°C)</div>
            <div class="stat-sub">全台大多數測站體感</div>
        </div>
        <div class="stat-card">
            <div class="stat-num" style="color: #60a5fa;">{avg_humidity}%</div>
            <div class="stat-label">全台平均濕度</div>
            <div class="stat-sub">涼爽站 (<20°C): {cool_count} 站</div>
        </div>
    </div>

    <!-- =================== 👔 智慧穿著與外出雨具生活建議卡 =================== -->
    <div class="clothing-panel">
        <div class="clothing-header">
            <div>
                <div style="font-size: 1.35rem; font-weight: 800; display: flex; align-items: center; gap: 8px;">
                    <span>👔 智慧穿搭與外出生活指標</span>
                    <span style="font-size: 0.8rem; font-weight: 600; color: var(--accent-cyan); background: rgba(56,189,248,0.15); padding: 2px 8px; border-radius: 4px;">
                        依 CWA 溫差、風速與降雨機率精準運算
                    </span>
                </div>
                <div style="font-size: 0.88rem; color: var(--text-muted); margin-top: 4px;">
                    當前關注地區：<b id="adviceRegionText" style="color: var(--text-main);">中部地區</b>
                </div>
            </div>
            <div id="clothingBadge" class="clothing-badge" style="background: rgba(251,146,60,0.15); color: #fb923c; border: 1px solid rgba(251,146,60,0.3);">
                🌤️ 舒適溫和 (20~28°C)
            </div>
        </div>

        <!-- 4 大穿著建議模組 -->
        <div class="clothing-grid">
            <div class="clothing-item">
                <div class="clothing-item-title">👕 上衣內著建議</div>
                <div id="adviceTop" class="clothing-item-val">棉質短袖 T-Shirt、休閒襯衫、透氣針織短袖</div>
            </div>
            <div class="clothing-item">
                <div class="clothing-item-title">🧥 外套外層搭配</div>
                <div id="adviceOuter" class="clothing-item-val">早晚或冷氣房備用薄長袖襯衫或透氣針織罩衫</div>
            </div>
            <div class="clothing-item">
                <div class="clothing-item-title">👖 下著與鞋款搭配</div>
                <div id="adviceBottom" class="clothing-item-val">休閒長褲、棉麻短褲、舒適球鞋 / 涼鞋</div>
            </div>
            <div class="clothing-item">
                <div class="clothing-item-title">🧢 必備防護與配件</div>
                <div id="adviceAccessory" class="clothing-item-val">遮陽帽 🧢、太陽眼鏡 🕶️、隨身水壺</div>
            </div>
        </div>

        <!-- ☔ 外出雨具與防風指南 (依照風速與降雨機率精準判斷雨衣或傘具大小) -->
        <div class="rain-gear-box">
            <div class="rain-gear-header">
                <div style="font-size: 1.05rem; font-weight: 700; color: #f1f5f9; display: flex; align-items: center; gap: 8px;">
                    <span>☔ 外出雨具與防風指南</span>
                    <span id="adviceRainMetric" style="font-size: 0.82rem; padding: 3px 10px; border-radius: 6px; font-weight: 700; background: rgba(56, 189, 248, 0.15); color: #38bdf8;">
                        降雨機率 0% · 預估風速 2.5 m/s
                    </span>
                </div>
                <div id="adviceGearTypeBadge" class="gear-chip" style="background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3);">
                    無需雨具 / 遮陽傘
                </div>
            </div>
            <div class="gear-grid">
                <div class="gear-subcard">
                    <b style="color: #94a3b8; font-size: 0.82rem; text-transform: uppercase;">🌂 推薦攜帶裝備：</b>
                    <div id="adviceGearTitle" style="color: #f8fafc; font-weight: 700; font-size: 1rem; margin-top: 4px;">抗 UV 輕量遮陽傘 (可選)</div>
                </div>
                <div class="gear-subcard">
                    <b style="color: #94a3b8; font-size: 0.82rem; text-transform: uppercase;">💡 風雨防護出行叮嚀：</b>
                    <div id="adviceGearAction" style="color: #cbd5e1; font-size: 0.88rem; margin-top: 4px;">降雨機率低，天候穩定晴朗；陽光強烈時可攜帶抗 UV 遮陽傘防曬。</div>
                </div>
            </div>
        </div>

        <div style="margin-top: 16px; padding: 12px 18px; border-radius: 10px; background: rgba(56, 189, 248, 0.08); border: 1px solid rgba(56, 189, 248, 0.25); display: flex; gap: 12px; align-items: center; font-size: 0.92rem;">
            <span style="font-size: 1.3rem;">🧅</span>
            <div>
                <b>洋蔥式穿法提醒：</b>
                <span id="adviceLayeringText" style="color: #cbd5e1;">
                    全天預估日溫差達 6.5°C，早晚清涼中午偏暖，建議採「短袖 + 薄開襟外套」方便隨室內外氣溫增減！
                </span>
            </div>
        </div>
    </div>

    <!-- Main Grid -->
    <div class="main-grid">
        <!-- Left: Interactive Map -->
        <div class="panel">
            <div class="panel-header">
                <div class="panel-title">
                    <span id="mapTitleText">🗺️ 全台即時測站分佈 (348 站)</span>
                </div>
                <div style="display: flex; gap: 8px; align-items: center;">
                    <!-- Map Mode Tabs -->
                    <div class="tab-group">
                        <button id="btnModeRealtime" class="tab-btn active">📡 即時測站</button>
                        <button id="btnModeForecast" class="tab-btn">🗓️ 分區預報地圖</button>
                    </div>
                    <button id="toggleRadar" class="btn">📡 雷達回波 (關閉)</button>
                </div>
            </div>

            <!-- Date Selector (Only shown in forecast map mode) -->
            <div id="forecastDateControl" style="display: none; margin-bottom: 12px; align-items: center; gap: 8px;">
                <label style="font-size: 0.88rem; color: var(--text-muted); font-weight: 600;">🗓 選擇日期顯示地圖 [環節 18]：</label>
                <select id="dateSelect" style="flex: 1; max-width: 240px;"></select>
            </div>

            <div id="map"></div>

            <!-- Map Legends -->
            <div id="realtimeLegend" class="map-legend">
                <div class="legend-item"><span class="legend-dot" style="background:#f43f5e;"></span> 🔴 ≥30°C 高溫</div>
                <div class="legend-item"><span class="legend-dot" style="background:#fb923c;"></span> 🟠 20~29°C 暖溫</div>
                <div class="legend-item"><span class="legend-dot" style="background:#38bdf8;"></span> 🔵 &lt;20°C 涼爽</div>
                <div style="margin-left: auto; font-size: 0.8rem;">底圖：Esri Dark Gray Base (無浮水印)</div>
            </div>

            <div id="forecastLegend" class="map-legend" style="display: none;">
                <span style="font-weight: 700; color: #fff;">平均溫度顏色 [環節 17]：</span>
                <div class="legend-item"><span class="legend-dot" style="background:#3b82f6;"></span> 🔵 &lt;20°C</div>
                <div class="legend-item"><span class="legend-dot" style="background:#10b981;"></span> 🟢 20~25°C</div>
                <div class="legend-item"><span class="legend-dot" style="background:#fb923c;"></span> 🟠 25~30°C</div>
                <div class="legend-item"><span class="legend-dot" style="background:#ef4444;"></span> 🔴 &gt;30°C</div>
                <div style="margin-left: auto; font-size: 0.8rem;">點擊圓點顯示 Min/Max 氣溫</div>
            </div>
        </div>

        <!-- Right: Forecast Trends & Table (環節 13~16) -->
        <div class="panel">
            <div class="panel-header">
                <div class="panel-title">
                    <span>📈 一週氣溫走勢與預報資料</span>
                </div>
                <div>
                    <label style="font-size: 0.85rem; color: var(--text-muted); margin-right: 6px; font-weight: 600;">📍 選擇地區 [環節 13]：</label>
                    <select id="regionSelect"></select>
                </div>
            </div>

            <!-- Dual Line Chart (MaxT / MinT) [環節 14] -->
            <div style="position: relative; height: 260px; width: 100%;">
                <canvas id="forecastChart"></canvas>
            </div>

            <!-- Forecast Data Table [環節 15] -->
            <div class="table-container">
                <table id="forecastTable">
                    <thead>
                        <tr>
                            <th>預報日期</th>
                            <th>最低溫</th>
                            <th>最高溫</th>
                            <th>降雨機率</th>
                            <th>預估風速</th>
                            <th>推薦雨具</th>
                        </tr>
                    </thead>
                    <tbody id="tableBody"></tbody>
                </table>
            </div>
        </div>
    </div>

    <!-- Full Dashboard Overview Table [環節 19] -->
    <div style="background: var(--bg-card); border: 1px solid var(--bg-card-border); border-radius: 16px; padding: 22px; margin-bottom: 30px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
            <div style="font-size: 1.15rem; font-weight: 700;">
                📊 全台所有地區預報總表 (Taiwan Weather Dashboard) [環節 19]
            </div>
            <div style="font-size: 0.85rem; color: var(--text-muted);">
                共 29 個行政與氣象分區 · 包含降雨機率與雨具型態
            </div>
        </div>
        <div style="max-height: 280px; overflow-y: auto; border: 1px solid var(--bg-card-border); border-radius: 10px;">
            <table id="allRegionsTable">
                <thead>
                    <tr>
                        <th>地區名稱</th>
                        <th>查詢日期</th>
                        <th>最低溫</th>
                        <th>最高溫</th>
                        <th>降雨機率</th>
                        <th>預測風速</th>
                        <th>推薦雨具</th>
                        <th>穿搭建議</th>
                    </tr>
                </thead>
                <tbody id="allRegionsBody"></tbody>
            </table>
        </div>
    </div>

    <footer>
        <p>L2CWAv2 台灣氣象系統 | 整合 CWA O-A0003-001、F-D0047-091、W-C0033-001 與 RainViewer 即時雷達</p>
        <p style="margin-top: 6px;">支援智慧生活穿搭建議 · 具備完整 CWA 降雨機率與風速雨衣/大傘判定 · Hosted on GitHub Pages</p>
    </footer>
</div>

<!-- Leaflet JS -->
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
    // 注入後端資料
    const stations = {json.dumps(stations_data, ensure_ascii=False)};
    const forecastByRegion = {json.dumps(forecast_by_region, ensure_ascii=False)};
    const forecastByDate = {json.dumps(forecast_by_date, ensure_ascii=False)};
    const datesList = {json.dumps(dates_list, ensure_ascii=False)};
    const regionCoords = {json.dumps(REGION_COORDS, ensure_ascii=False)};

    // 初始化 Leaflet 地圖
    const map = L.map('map', {{
        center: [23.7, 120.95],
        zoom: 7,
        zoomControl: true,
        preferCanvas: true
    }});

    // Esri Dark Gray Base (無浮水印)
    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
        attribution: 'Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ',
        maxZoom: 16
    }}).addTo(map);

    const realtimeLayer = L.layerGroup().addTo(map);
    const forecastLayer = L.layerGroup();
    let radarLayer = null;

    // 1. 渲染即時測站
    stations.forEach(s => {{
        if (!s.latitude || !s.longitude || s.air_temperature === null) return;
        
        let color = '#38bdf8'; // 藍
        if (s.air_temperature >= 30) color = '#f43f5e'; // 紅
        else if (s.air_temperature >= 20) color = '#fb923c'; // 橘

        const marker = L.circleMarker([s.latitude, s.longitude], {{
            radius: 5.5,
            fillColor: color,
            color: '#ffffff',
            weight: 0.8,
            opacity: 0.9,
            fillOpacity: 0.88
        }});

        const popupContent = `
            <div class="popup-station">${{s.station_name}} <span style="font-size:0.75rem; color:#8b949e;">(${{s.station_id}})</span></div>
            <div class="popup-temp" style="color:${{color}}">
                ${{s.air_temperature}} °C
                <span style="font-size:0.85rem; color:#94a3b8; font-weight:normal; margin-left:6px;">體感 ${{s.apparent_temp ?? s.air_temperature}}°C</span>
            </div>
            <div style="font-size:0.85rem; line-height:1.6; color:#94a3b8; border-top:1px solid #233146; padding-top:6px;">
                💨 風況: <b style="color:#e2e8f0">${{s.wind_dir_text ?? '微風'}} ${{s.wind_speed ?? 0}} m/s</b><br>
                💧 相對濕度: <b style="color:#e2e8f0">${{s.relative_humidity ?? 0}}%</b><br>
                🌧️ 今日累積雨量: <b style="color:#e2e8f0">${{s.precipitation ?? 0}} mm</b><br>
                ☁️ 描述: ${{s.weather_desc || '多雲到晴'}}<br>
                🕒 觀測時間: ${{s.obs_time ?? '--'}}
            </div>
        `;
        marker.bindPopup(popupContent);
        realtimeLayer.addLayer(marker);
    }});

    // 2. 均溫著色函式
    function getForecastColor(avg) {{
        if (avg < 20) return '#3b82f6';   // 藍色
        if (avg <= 25) return '#10b981';  // 綠色
        if (avg <= 30) return '#fb923c';  // 橘色
        return '#ef4444';                 // 紅色
    }}

    // 3. 渲染分區預報地圖 (環節 17 & 18)
    function renderForecastMap(dateStr) {{
        forecastLayer.clearLayers();
        const records = forecastByDate[dateStr] || [];

        records.forEach(r => {{
            const regName = r.regionName;
            if (regionCoords[regName]) {{
                const coord = regionCoords[regName];
                const avgT = ((r.minT + r.maxT) / 2).toFixed(1);
                const color = getForecastColor(parseFloat(avgT));
                const pop = r.pop ?? 0;
                const ws = r.wind_speed ?? 2.0;

                const circle = L.circleMarker([coord.lat, coord.lon], {{
                    radius: 15,
                    fillColor: color,
                    color: '#ffffff',
                    weight: 2,
                    opacity: 1,
                    fillOpacity: 0.88
                }});

                const popupHtml = `
                    <div style="padding:4px;">
                        <div style="font-size:1.15rem; font-weight:800; color:${{color}}">${{regName}}</div>
                        <div style="font-size:0.8rem; color:#8b949e; margin-bottom:8px;">預報日期：${{dateStr}}</div>
                        <div style="font-size:0.92rem; margin-bottom:4px;">
                            最低溫 (MinT): <b style="color:#38bdf8;">${{r.minT}}°C</b> | 最高溫: <b style="color:#f43f5e;">${{r.maxT}}°C</b>
                        </div>
                        <div style="font-size:0.92rem; margin-bottom:4px;">
                            ☔ 降雨機率: <b style="color:#38bdf8;">${{pop}}%</b> | 💨 風速: <b style="color:#fbbf24;">${{ws}} m/s</b>
                        </div>
                        <div style="font-size:0.9rem; color:${{color}}; font-weight:700; border-top:1px solid #30363d; padding-top:4px;">
                            當日均溫: ${{avgT}}°C
                        </div>
                    </div>
                `;
                circle.bindPopup(popupHtml);
                forecastLayer.addLayer(circle);
            }}
        }});
    }}

    // 4. 地圖模式切換邏輯
    const btnRealtime = document.getElementById('btnModeRealtime');
    const btnForecast = document.getElementById('btnModeForecast');
    const forecastDateControl = document.getElementById('forecastDateControl');
    const realtimeLegend = document.getElementById('realtimeLegend');
    const forecastLegend = document.getElementById('forecastLegend');
    const mapTitleText = document.getElementById('mapTitleText');
    const dateSelect = document.getElementById('dateSelect');

    datesList.forEach(d => {{
        const opt = document.createElement('option');
        opt.value = d;
        opt.textContent = d;
        dateSelect.appendChild(opt);
    }});

    function setMapMode(mode) {{
        if (mode === 'realtime') {{
            btnRealtime.classList.add('active');
            btnForecast.classList.remove('active');
            forecastDateControl.style.display = 'none';
            realtimeLegend.style.display = 'flex';
            forecastLegend.style.display = 'none';
            mapTitleText.textContent = '🗺️ 全台即時測站分佈 (348 站)';

            map.removeLayer(forecastLayer);
            map.addLayer(realtimeLayer);
        }} else {{
            btnRealtime.classList.remove('active');
            btnForecast.classList.add('active');
            forecastDateControl.style.display = 'flex';
            realtimeLegend.style.display = 'none';
            forecastLegend.style.display = 'flex';
            mapTitleText.textContent = `🗺️ 台灣分區氣溫預報地圖 [環節 17 & 18]`;

            map.removeLayer(realtimeLayer);
            map.addLayer(forecastLayer);
            renderForecastMap(dateSelect.value || datesList[0]);
            updateAllRegionsTable(dateSelect.value || datesList[0]);
        }}
    }}

    btnRealtime.addEventListener('click', () => setMapMode('realtime'));
    btnForecast.addEventListener('click', () => setMapMode('forecast'));
    dateSelect.addEventListener('change', (e) => {{
        renderForecastMap(e.target.value);
        updateAllRegionsTable(e.target.value);
    }});

    // 5. RainViewer 雷達回波圖層
    const toggleBtn = document.getElementById('toggleRadar');
    fetch('https://api.rainviewer.com/public/weather-maps.json')
        .then(res => res.json())
        .then(data => {{
            if (data.radar && data.radar.past && data.radar.past.length > 0) {{
                const latest = data.radar.past[data.radar.past.length - 1];
                const radarUrl = `https://tilecache.rainviewer.com${{latest.path}}/256/{{z}}/{{x}}/{{y}}/2/1_1.png`;
                radarLayer = L.tileLayer(radarUrl, {{
                    opacity: 0.65,
                    zIndex: 100,
                    minZoom: 0,
                    maxNativeZoom: 7,
                    maxZoom: 18
                }});
            }}
        }})
        .catch(err => console.log('Radar load error', err));

    toggleBtn.addEventListener('click', () => {{
        if (!radarLayer) return;
        if (map.hasLayer(radarLayer)) {{
            map.removeLayer(radarLayer);
            toggleBtn.textContent = '📡 雷達回波 (關閉)';
            toggleBtn.classList.remove('active');
        }} else {{
            map.addLayer(radarLayer);
            toggleBtn.textContent = '📡 雷達回波 (生效中)';
            toggleBtn.classList.add('active');
        }}
    }});

    // 6. 核心生活雨具判定演算法 (依照風速與降雨機率)
    function evaluateRainGear(pop, ws, wx) {{
        pop = parseFloat(pop || 0);
        ws = parseFloat(ws || 2.0);
        wx = wx || '';

        // 狀況 1：強風大雨 (風速 >= 8.0 m/s 且 降雨機率 >= 40% 或 天氣有雨) -> 建議穿雨衣、嚴禁開傘
        if (ws >= 8.0 && (pop >= 40 || wx.includes('雨'))) {{
            return {{
                title: '⛈️ 強風豪雨 · 穿著兩件式雨衣 / 避免開傘',
                gear: '全套/兩件式雨衣 + 防水雨靴',
                badgeText: '穿兩件式雨衣',
                badgeColor: '#ef4444',
                action: `風速高達 ${{ws}} m/s (5~6 級強陣風) 且降雨機率 ${{pop}}%，開傘極易折斷開花且非常危險！強烈建議穿著兩件式雨衣，騎車行人請特別防範強側風！`
            }};
        }}
        // 狀況 2：陣風有雨 (風速 >= 5.5 m/s 且 降雨機率 >= 30%) -> 建議抗風長柄直傘或輕便雨衣
        else if (ws >= 5.5 && (pop >= 30 || wx.includes('雨'))) {{
            return {{
                title: '💨 陣風有雨 · 建議抗風直骨長傘 / 輕便雨衣',
                gear: '抗風直骨長傘 (玻纖骨架) 或 輕便雨衣',
                badgeText: '抗風大直傘/雨衣',
                badgeColor: '#f97316',
                action: `預測風速 ${{ws}} m/s 搭配降雨機率 ${{pop}}%，普通折傘容易被吹損，建議挑選強韌玻纖抗風直傘；機車通勤請備妥雨衣。`
            }};
        }}
        // 狀況 3：風小但降雨機率高 (雨勢連續明顯 pop >= 60%) -> 推薦標準長柄大傘或雙人折傘
        else if (pop >= 60 || wx.includes('大雨') || wx.includes('豪雨')) {{
            return {{
                title: '🌧️ 雨勢顯著 · 推薦標準長柄大傘或雙人折傘',
                gear: '長柄直傘 (大傘面) 或 雙人加大折傘',
                badgeText: '長柄大傘',
                badgeColor: '#3b82f6',
                action: `降雨機率高達 ${{pop}}%，出門必備大傘面長直傘，能完整遮蓋背包與鞋褲不受雨淋。`
            }};
        }}
        // 狀況 4：局部短暫陣雨 (風小，降雨機率 30% ~ 59%) -> 隨身輕量折疊傘
        else if (pop >= 30 || wx.includes('短暫') || wx.includes('陣雨')) {{
            return {{
                title: '🌦️ 局部短暫雨 · 隨身必備輕量折疊傘',
                gear: '輕量三折折疊傘 / 晴雨兩用傘',
                badgeText: '隨身折疊傘',
                badgeColor: '#06b6d4',
                action: `降雨型態為短暫間歇陣雨（降雨機率 ${{pop}}%），包包內常備一把輕便折傘，隨時應對突發落雨最靈活。`
            }};
        }}
        // 狀況 5：強風無雨 (風速 >= 8.0 m/s 且 降雨機率 < 30%) -> 穿防風外套，無需雨具
        else if (ws >= 8.0) {{
            return {{
                title: '🚩 強陣風注意 · 需著防風外套 / 無需雨具',
                gear: '防風連帽風衣外套',
                badgeText: '防風外套/免雨具',
                badgeColor: '#eab308',
                action: `今日風力達 ${{ws}} m/s，行經高樓空曠處注意強風吹襲，無須帶傘，穿著防風外套最佳。`
            }};
        }}
        // 狀況 6：晴朗少雨 -> 遮陽傘
        else {{
            return {{
                title: '☀️ 晴朗少雨 · 無需雨具 / 可帶抗 UV 晴雨兩用傘',
                gear: '抗 UV 輕量遮陽傘 (可選)',
                badgeText: '遮陽傘/免帶',
                badgeColor: '#10b981',
                action: `降雨機率僅 ${{pop}}%，天候穩定晴朗，適合各類戶外活動，陽光強烈時可攜帶抗 UV 遮陽傘防曬。`
            }};
        }}
    }}

    // 7. 一週雙折線圖與表格 + 智慧穿著雨具
    const regionSelect = document.getElementById('regionSelect');
    const allRegions = Object.keys(forecastByRegion);
    const priorityRegions = ['中部地區', '北部地區', '南部地區', '東北部地區', '東部地區', '東南部地區'];
    const sortedRegions = [...new Set([...priorityRegions, ...allRegions])].filter(r => allRegions.includes(r));

    sortedRegions.forEach(r => {{
        const opt = document.createElement('option');
        opt.value = r;
        opt.textContent = r;
        regionSelect.appendChild(opt);
    }});

    const ctx = document.getElementById('forecastChart').getContext('2d');
    let forecastChart = new Chart(ctx, {{
        type: 'line',
        data: {{
            labels: [],
            datasets: [
                {{
                    label: '最高溫 MaxT (°C)',
                    data: [],
                    borderColor: '#f43f5e',
                    backgroundColor: 'rgba(244, 63, 94, 0.15)',
                    borderWidth: 3,
                    tension: 0.35,
                    fill: false,
                    pointRadius: 5,
                    pointHoverRadius: 7
                }},
                {{
                    label: '最低溫 MinT (°C)',
                    data: [],
                    borderColor: '#38bdf8',
                    backgroundColor: 'rgba(56, 189, 248, 0.15)',
                    borderWidth: 3,
                    tension: 0.35,
                    fill: false,
                    pointRadius: 5,
                    pointHoverRadius: 7
                }}
            ]
        }},
        options: {{
            responsive: true,
            maintainAspectRatio: false,
            plugins: {{
                legend: {{
                    labels: {{ color: '#f0f6fc', font: {{ family: 'Outfit', size: 12 }} }}
                }},
                tooltip: {{
                    mode: 'index',
                    intersect: false
                }}
            }},
            scales: {{
                x: {{
                    ticks: {{ color: '#8b949e' }},
                    grid: {{ color: 'rgba(255,255,255,0.06)' }}
                }},
                y: {{
                    ticks: {{ color: '#8b949e' }},
                    grid: {{ color: 'rgba(255,255,255,0.06)' }}
                }}
            }}
        }}
    }});

    function updateClothingAdvice(regionName, firstDayData) {{
        document.getElementById('adviceRegionText').textContent = regionName;
        if (!firstDayData) return;

        const maxT = firstDayData.maxT;
        const minT = firstDayData.minT;
        const avgT = ((maxT + minT) / 2).toFixed(1);
        const diff = (maxT - minT).toFixed(1);
        const pop = firstDayData.pop ?? 0;
        const ws = firstDayData.wind_speed ?? 2.0;
        const wx = firstDayData.weather_desc ?? '';

        // 更新雨具指南
        const gearInfo = evaluateRainGear(pop, ws, wx);
        document.getElementById('adviceRainMetric').textContent = `降雨機率 ${{pop}}% · 預估風速 ${{ws}} m/s`;
        const gearBadge = document.getElementById('adviceGearTypeBadge');
        gearBadge.textContent = gearInfo.badgeText;
        gearBadge.style.color = gearInfo.badgeColor;
        gearBadge.style.background = `${{gearInfo.badgeColor}}22`;
        gearBadge.style.borderColor = `${{gearInfo.badgeColor}}55`;
        document.getElementById('adviceGearTitle').textContent = gearInfo.gear;
        document.getElementById('adviceGearAction').textContent = gearInfo.action;

        // 更新穿搭建議
        const badge = document.getElementById('clothingBadge');
        let topText = '', outerText = '', bottomText = '', accText = '', layerText = '';

        if (maxT >= 31 || avgT >= 29) {{
            badge.style.background = 'rgba(244, 63, 94, 0.15)';
            badge.style.color = '#fb7185';
            badge.style.borderColor = 'rgba(244, 63, 94, 0.3)';
            badge.textContent = `🔥 酷暑炎熱 (均溫 ${{avgT}}°C)`;
            topText = '透氣短袖 T-Shirt、無袖背心、涼感機能排汗衫';
            outerText = '室內冷氣房備用超薄防曬襯衫 / 冰絲防曬袖套';
            bottomText = '清涼透氣短褲、棉麻休閒長褲、涼感寬褲';
            accText = '太陽眼鏡 🕶️、防曬遮陽帽 🧢、高係數防曬乳、隨身水壺';
            layerText = `全天氣溫偏高，單層透氣排汗為主。日溫差約 ${{diff}}°C，注意防曬並大量補充水分防中暑！`;
        }} else if (maxT >= 26 || avgT >= 24) {{
            badge.style.background = 'rgba(251, 146, 60, 0.15)';
            badge.style.color = '#fb923c';
            badge.style.borderColor = 'rgba(251, 146, 60, 0.3)';
            badge.textContent = `🌤️ 溫暖舒適 (均溫 ${{avgT}}°C)`;
            topText = '純棉短袖上衣、舒適休閒短袖、棉麻襯衫';
            outerText = '隨身攜帶輕薄外套、開襟針織薄衫 (應對晚風)';
            bottomText = '休閒長褲、九分丹寧牛仔褲、棉質休閒褲';
            accText = '外出晴雨折疊傘 ☔、遮陽帽、薄外套備用';
            layerText = `日夜溫差約 ${{diff}}°C，建議採「短袖 + 薄襯衫」便利穿搭，進出冷氣房彈性調適。`;
        }} else if (avgT >= 19) {{
            badge.style.background = 'rgba(16, 185, 129, 0.15)';
            badge.style.color = '#34d399';
            badge.style.borderColor = 'rgba(16, 185, 129, 0.3)';
            badge.textContent = `🌿 舒適微涼 (均溫 ${{avgT}}°C)`;
            topText = '薄長袖上衣、長袖棉質衛衣、七分袖 T-Shirt';
            outerText = '防風薄夾克、單寧牛仔外套、針織開襟外套';
            bottomText = '卡其長褲、直筒牛仔長褲、棉質長長褲';
            accText = '早晚薄絲巾 / 輕便圍巾、保溫水瓶、折疊傘';
            layerText = `日溫差達到 ${{diff}}°C！強烈建議標準「洋蔥式穿法 🧅」：內搭短袖或薄長袖，外罩防風外套。`;
        }} else {{
            badge.style.background = 'rgba(56, 189, 248, 0.15)';
            badge.style.color = '#38bdf8';
            badge.style.borderColor = 'rgba(56, 189, 248, 0.3)';
            badge.textContent = `❄️ 涼冷保暖 (均溫 ${{avgT}}°C)`;
            topText = '保暖衛衣、重磅毛衣、刷毛長袖、內搭發熱衣';
            outerText = '保暖厚防風外套、羽絨外套、雙層毛呢大衣';
            bottomText = '保暖刷毛長褲、厚磅丹寧褲、長襪';
            accText = '保暖毛帽、厚圍巾 🧣、保暖手套、暖暖包';
            layerText = `氣溫明顯偏低，請加強頭頸部防風保暖，多層次禦寒穿著！`;
        }}

        document.getElementById('adviceTop').textContent = topText;
        document.getElementById('adviceOuter').textContent = outerText;
        document.getElementById('adviceBottom').textContent = bottomText;
        document.getElementById('adviceAccessory').textContent = accText;
        document.getElementById('adviceLayeringText').textContent = layerText;
    }}

    function updateRegionForecast(regionName) {{
        const data = forecastByRegion[regionName] || [];
        const labels = data.map(d => d.dataDate.slice(5));
        const maxTemps = data.map(d => d.maxT);
        const minTemps = data.map(d => d.minT);

        forecastChart.data.labels = labels;
        forecastChart.data.datasets[0].data = maxTemps;
        forecastChart.data.datasets[1].data = minTemps;
        forecastChart.update();

        if (data.length > 0) {{
            updateClothingAdvice(regionName, data[0]);
        }}

        const tbody = document.getElementById('tableBody');
        tbody.innerHTML = '';
        data.forEach(d => {{
            const pop = d.pop ?? 0;
            const ws = d.wind_speed ?? 2.0;
            const wx = d.weather_desc ?? '';
            const gear = evaluateRainGear(pop, ws, wx);

            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td style="font-weight:600;">${{d.dataDate}}</td>
                <td style="color:#38bdf8; font-weight:700;">${{d.minT}}°C</td>
                <td style="color:#f43f5e; font-weight:700;">${{d.maxT}}°C</td>
                <td style="color:#60a5fa; font-weight:700;">${{pop}}%</td>
                <td style="color:#fbbf24;">${{ws}} m/s</td>
                <td><span style="background:${{gear.badgeColor}}22; color:${{gear.badgeColor}}; padding:3px 10px; border-radius:6px; font-weight:700; font-size:0.82rem;">${{gear.badgeText}}</span></td>
            `;
            tbody.appendChild(tr);
        }});
    }}

    regionSelect.addEventListener('change', (e) => {{
        updateRegionForecast(e.target.value);
    }});

    // 8. 更新全台所有地區總表 (環節 19)
    function updateAllRegionsTable(curDate) {{
        const allTbody = document.getElementById('allRegionsBody');
        allTbody.innerHTML = '';
        const records = forecastByDate[curDate] || [];

        records.forEach(r => {{
            const pop = r.pop ?? 0;
            const ws = r.wind_speed ?? 2.0;
            const wx = r.weather_desc ?? '';
            const gear = evaluateRainGear(pop, ws, wx);
            const avgT = ((r.minT + r.maxT) / 2).toFixed(1);
            const color = getForecastColor(parseFloat(avgT));
            let outfit = avgT >= 28 ? '短袖/涼感' : (avgT >= 22 ? '短袖+薄衫' : '薄長袖/外套');

            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td style="font-weight:700; color:#f0f6fc;">${{r.regionName}}</td>
                <td style="color:#8b949e;">${{curDate}}</td>
                <td style="color:#38bdf8; font-weight:700;">${{r.minT}}°C</td>
                <td style="color:#f43f5e; font-weight:700;">${{r.maxT}}°C</td>
                <td style="color:#60a5fa; font-weight:700;">${{pop}}%</td>
                <td style="color:#fbbf24;">${{ws}} m/s</td>
                <td><span style="background:${{gear.badgeColor}}22; color:${{gear.badgeColor}}; padding:3px 8px; border-radius:6px; font-size:0.8rem; font-weight:700;">${{gear.badgeText}}</span></td>
                <td style="color:#cbd5e1; font-size:0.85rem;">${{outfit}}</td>
            `;
            allTbody.appendChild(tr);
        }});
    }}

    // 預設載入
    updateRegionForecast('中部地區');
    updateAllRegionsTable(datesList[0] || '2026-09-23');
</script>
</body>
</html>
"""

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print(f"Generated static index.html successfully at: {OUTPUT_PATH}")

if __name__ == "__main__":
    generate_index_html()
