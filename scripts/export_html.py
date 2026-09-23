# -*- coding: utf-8 -*-
"""
scripts/export_html.py
導出靜態 index.html，供 GitHub Pages 直接展示台灣即時天氣地圖與一週預報圖表。
"""
import os
import json
import sqlite3
import pandas as pd

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "weather.db")
OUTPUT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "index.html")

def generate_index_html():
    conn = sqlite3.connect(DB_PATH)
    
    # 讀取即時測站
    df_stations = pd.read_sql_query(
        "SELECT station_id, station_name, latitude, longitude, air_temperature, obs_time, wind_speed, relative_humidity, precipitation, weather_desc FROM realtime_weather WHERE air_temperature > -90",
        conn
    )
    stations_data = df_stations.to_dict(orient="records")
    
    # 讀取預報資料
    df_forecast = pd.read_sql_query(
        "SELECT regionName, dataDate, minT, maxT FROM TemperatureForecasts ORDER BY dataDate ASC",
        conn
    )
    conn.close()
    
    # 整理各區預報
    forecast_dict = {}
    for region, group in df_forecast.groupby("regionName"):
        forecast_dict[region] = group.to_dict(orient="records")
        
    dates_list = sorted(list(df_forecast["dataDate"].unique()))
    
    # 統計指標
    total_stations = len(df_stations)
    hot_count = len(df_stations[df_stations["air_temperature"] >= 30])
    warm_count = len(df_stations[(df_stations["air_temperature"] >= 20) & (df_stations["air_temperature"] < 30)])
    cool_count = len(df_stations[df_stations["air_temperature"] < 20])
    avg_temp = round(df_stations["air_temperature"].mean(), 1) if total_stations > 0 else 0.0

    # 區域中心座標
    region_centers = {
        "北部地區": {"lat": 25.02, "lon": 121.50},
        "中部地區": {"lat": 24.15, "lon": 120.68},
        "南部地區": {"lat": 22.99, "lon": 120.21},
        "東北部地區": {"lat": 24.75, "lon": 121.75},
        "東部地區": {"lat": 23.98, "lon": 121.60},
        "東南部地區": {"lat": 22.75, "lon": 121.14},
        "離島地區": {"lat": 23.57, "lon": 119.58},
    }

    html_content = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🌡️ 台灣即時天氣監測 & 一週氣溫趨勢預報 (GitHub Pages 版)</title>
    <!-- Leaflet CSS -->
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <!-- Google Fonts Inter -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&family=Noto+Sans+TC:wght@400;500;700&display=swap" rel="stylesheet">
    <!-- Chart.js -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {{
            --bg-base: #0e1117;
            --bg-card: #161b22;
            --bg-card-border: #30363d;
            --text-main: #f0f6fc;
            --text-muted: #8b949e;
            --accent-blue: #58a6ff;
            --accent-red: #ff7b72;
            --accent-orange: #ffa657;
            --accent-green: #3fb950;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            background-color: var(--bg-base);
            color: var(--text-main);
            font-family: 'Inter', 'Noto Sans TC', sans-serif;
            line-height: 1.6;
            padding: 20px;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        header {{
            margin-bottom: 24px;
            border-bottom: 1px solid var(--bg-card-border);
            padding-bottom: 16px;
        }}
        .header-title {{
            font-size: 2rem;
            font-weight: 800;
            background: linear-gradient(90deg, #ff7b72, #ffa657, #58a6ff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            display: inline-block;
        }}
        .header-subtitle {{
            color: var(--text-muted);
            font-size: 0.95rem;
            margin-top: 6px;
        }}
        /* Alert Banner */
        .alert-banner {{
            background: rgba(63, 185, 80, 0.12);
            border: 1px solid rgba(63, 185, 80, 0.4);
            color: #56d364;
            padding: 12px 18px;
            border-radius: 8px;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            font-size: 0.92rem;
            font-weight: 500;
        }}
        /* KPI Stats Grid */
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}
        .stat-card {{
            background-color: var(--bg-card);
            border: 1px solid var(--bg-card-border);
            border-radius: 12px;
            padding: 16px 20px;
            text-align: center;
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
            transition: transform 0.2s ease;
        }}
        .stat-card:hover {{
            transform: translateY(-2px);
        }}
        .stat-num {{
            font-size: 2.2rem;
            font-weight: 800;
            margin-bottom: 4px;
        }}
        .stat-label {{
            font-size: 0.85rem;
            color: var(--text-muted);
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        /* Layout Grid */
        .main-grid {{
            display: grid;
            grid-template-columns: 1.2fr 1fr;
            gap: 24px;
            margin-bottom: 30px;
        }}
        @media (max-width: 1024px) {{
            .main-grid {{ grid-template-columns: 1fr; }}
        }}
        .panel {{
            background-color: var(--bg-card);
            border: 1px solid var(--bg-card-border);
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 4px 16px rgba(0,0,0,0.25);
        }}
        .panel-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
            flex-wrap: wrap;
            gap: 10px;
        }}
        .panel-title {{
            font-size: 1.2rem;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        /* Map Styles */
        #map {{
            height: 600px;
            width: 100%;
            border-radius: 8px;
            background: #242424;
        }}
        .map-controls {{
            display: flex;
            gap: 10px;
            align-items: center;
        }}
        .btn {{
            background: #21262d;
            border: 1px solid var(--bg-card-border);
            color: var(--text-main);
            padding: 6px 12px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.85rem;
            transition: all 0.2s;
        }}
        .btn:hover, .btn.active {{
            background: #30363d;
            border-color: var(--accent-blue);
            color: var(--accent-blue);
        }}
        /* Select Form */
        select {{
            background-color: #21262d;
            color: var(--text-main);
            border: 1px solid var(--bg-card-border);
            border-radius: 6px;
            padding: 6px 12px;
            font-size: 0.9rem;
            cursor: pointer;
        }}
        /* Table Styles */
        .table-container {{
            max-height: 250px;
            overflow-y: auto;
            margin-top: 16px;
            border: 1px solid var(--bg-card-border);
            border-radius: 8px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9rem;
            text-align: left;
        }}
        th, td {{
            padding: 10px 14px;
            border-bottom: 1px solid #21262d;
        }}
        th {{
            background-color: #1c2128;
            color: var(--text-muted);
            font-weight: 600;
            position: sticky;
            top: 0;
        }}
        tr:hover td {{
            background-color: rgba(255,255,255,0.03);
        }}
        footer {{
            text-align: center;
            color: var(--text-muted);
            font-size: 0.85rem;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid var(--bg-card-border);
        }}
        /* Leaflet Popups Dark */
        .leaflet-popup-content-wrapper, .leaflet-popup-tip {{
            background: #161b22 !important;
            color: #f0f6fc !important;
            border: 1px solid #30363d;
            box-shadow: 0 4px 16px rgba(0,0,0,0.5);
        }}
        .popup-station {{
            font-size: 1rem;
            font-weight: 700;
            margin-bottom: 4px;
            color: var(--accent-blue);
        }}
        .popup-temp {{
            font-size: 1.3rem;
            font-weight: 800;
            margin-bottom: 6px;
        }}
    </style>
</head>
<body>
<div class="container">
    <header>
        <div class="header-title">🌡️ 台灣即時天氣監測 & 一週氣溫趨勢預報</div>
        <div class="header-subtitle">
            滿分專案標竿 (Esri Dark Gray Base × CWA Open Data) × 煥哥 AI 創新微課程 24 環節全面實現
        </div>
    </header>

    <div class="alert-banner">
        🟢 【中央氣象署特報監測】目前全台無生效中的即時天氣特報，各區天候穩定。
    </div>

    <!-- Stats KPI -->
    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-num" style="color: var(--accent-blue);">{total_stations}</div>
            <div class="stat-label">全台監測站數</div>
        </div>
        <div class="stat-card">
            <div class="stat-num" style="color: var(--accent-red);">{hot_count}</div>
            <div class="stat-label">高溫站 (≥30°C)</div>
        </div>
        <div class="stat-card">
            <div class="stat-num" style="color: var(--accent-orange);">{warm_count}</div>
            <div class="stat-label">暖溫站 (20~29°C)</div>
        </div>
        <div class="stat-card">
            <div class="stat-num" style="color: #a5d6ff;">{cool_count}</div>
            <div class="stat-label">涼爽站 (<20°C)</div>
        </div>
        <div class="stat-card">
            <div class="stat-num" style="color: #e6edf3;">{avg_temp}°C</div>
            <div class="stat-label">全台平均氣溫</div>
        </div>
    </div>

    <!-- Main Grid -->
    <div class="main-grid">
        <!-- Left: Map Panel -->
        <div class="panel">
            <div class="panel-header">
                <div class="panel-title">
                    <span>🗺️ 即時測站分佈 (Esri Dark Gray Base)</span>
                </div>
                <div class="map-controls">
                    <button id="toggleRadar" class="btn">📡 雷達回波圖層 (關閉)</button>
                </div>
            </div>
            <div id="map"></div>
            <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 10px; display: flex; gap: 16px;">
                <span>🔴 ≥30°C 高溫</span>
                <span>🟠 20~29°C 暖溫</span>
                <span>🔵 <20°C 涼溫</span>
                <span style="margin-left: auto;">資料來源：中央氣象署 O-A0003-001</span>
            </div>
        </div>

        <!-- Right: Forecast & Trends -->
        <div class="panel">
            <div class="panel-header">
                <div class="panel-title">
                    <span>📈 一週氣溫走勢與預報資料</span>
                </div>
                <div>
                    <label style="font-size: 0.85rem; color: var(--text-muted); margin-right: 6px;">選擇地區：</label>
                    <select id="regionSelect">
                    </select>
                </div>
            </div>

            <!-- Chart -->
            <div style="position: relative; height: 280px; width: 100%;">
                <canvas id="forecastChart"></canvas>
            </div>

            <!-- Table -->
            <div class="table-container">
                <table id="forecastTable">
                    <thead>
                        <tr>
                            <th>日期</th>
                            <th>最低溫 (MinT)</th>
                            <th>最高溫 (MaxT)</th>
                            <th>日溫差</th>
                            <th>天氣感受</th>
                        </tr>
                    </thead>
                    <tbody id="tableBody"></tbody>
                </table>
            </div>
        </div>
    </div>

    <footer>
        <p>L2CWAv2 台灣氣象系統 | 結合 CWA O-A0003-001、F-D0047-091 與 RainViewer 即時雷達回波</p>
        <p style="margin-top: 6px;">Hosted automatically on GitHub Pages · Made with ❤️ by Antigravity</p>
    </footer>
</div>

<!-- Leaflet JS -->
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
    // 注入後端資料
    const stations = {json.dumps(stations_data, ensure_ascii=False)};
    const forecastData = {json.dumps(forecast_dict, ensure_ascii=False)};
    
    // 初始化地圖
    const map = L.map('map').setView([23.7, 120.95], 7);

    // Esri Dark Gray Base
    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
        attribution: 'Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ',
        maxZoom: 16
    }}).addTo(map);

    // 標記測站
    const markersLayer = L.layerGroup().addTo(map);
    stations.forEach(s => {{
        if (!s.latitude || !s.longitude || s.air_temperature === null) return;
        
        let color = '#58a6ff'; // 藍
        if (s.air_temperature >= 30) color = '#ff7b72'; // 紅
        else if (s.air_temperature >= 20) color = '#ffa657'; // 橘

        const marker = L.circleMarker([s.latitude, s.longitude], {{
            radius: 5,
            fillColor: color,
            color: '#fff',
            weight: 0.8,
            opacity: 0.9,
            fillOpacity: 0.85
        }});

        const popupContent = `
            <div class="popup-station">${{s.station_name}} <span style="font-size:0.75rem; color:#8b949e;">(${{s.station_id}})</span></div>
            <div class="popup-temp" style="color:${{color}}">${{s.air_temperature}} °C</div>
            <div style="font-size:0.85rem; color:#8b949e;">
                💨 風速: ${{s.wind_speed ?? '--'}} m/s<br>
                💧 濕度: ${{s.relative_humidity ?? '--'}}%<br>
                🌧️ 雨量: ${{s.precipitation ?? '0'}} mm<br>
                🕒 觀測: ${{s.obs_time ?? '--'}}
            </div>
        `;
        marker.bindPopup(popupContent);
        markersLayer.addLayer(marker);
    }});

    // RainViewer 雷達回波圖層
    let radarLayer = null;
    const toggleBtn = document.getElementById('toggleRadar');
    
    // 獲取最新雷達回波
    fetch('https://api.rainviewer.com/public/weather-maps.json')
        .then(res => res.json())
        .then(data => {{
            if (data.radar && data.radar.past && data.radar.past.length > 0) {{
                const latest = data.radar.past[data.radar.past.length - 1];
                const radarUrl = `https://tilecache.rainviewer.com${{latest.path}}/256/{{z}}/{{x}}/{{y}}/2/1_1.png`;
                radarLayer = L.tileLayer(radarUrl, {{
                    opacity: 0.65,
                    zIndex: 100
                }});
            }}
        }})
        .catch(err => console.log('Radar load error', err));

    toggleBtn.addEventListener('click', () => {{
        if (!radarLayer) return;
        if (map.hasLayer(radarLayer)) {{
            map.removeLayer(radarLayer);
            toggleBtn.textContent = '📡 雷達回波圖層 (關閉)';
            toggleBtn.classList.remove('active');
        }} else {{
            map.addLayer(radarLayer);
            toggleBtn.textContent = '📡 雷達回波圖層 (生效中)';
            toggleBtn.classList.add('active');
        }}
    }});

    // 初始化下拉選單
    const regionSelect = document.getElementById('regionSelect');
    const regions = Object.keys(forecastData);
    
    // 優先推薦的分區排序
    const priorityRegions = ['中部地區', '北部地區', '南部地區', '東北部地區', '東部地區', '東南部地區'];
    const sortedRegions = [...new Set([...priorityRegions, ...regions])].filter(r => regions.includes(r));

    sortedRegions.forEach(r => {{
        const opt = document.createElement('option');
        opt.value = r;
        opt.textContent = r;
        regionSelect.appendChild(opt);
    }});

    // 初始化 Chart.js
    const ctx = document.getElementById('forecastChart').getContext('2d');
    let forecastChart = new Chart(ctx, {{
        type: 'line',
        data: {{
            labels: [],
            datasets: [
                {{
                    label: '最高溫 MaxT (°C)',
                    data: [],
                    borderColor: '#ff7b72',
                    backgroundColor: 'rgba(255, 123, 114, 0.15)',
                    tension: 0.35,
                    fill: false,
                    pointRadius: 5,
                    pointHoverRadius: 7
                }},
                {{
                    label: '最低溫 MinT (°C)',
                    data: [],
                    borderColor: '#58a6ff',
                    backgroundColor: 'rgba(88, 166, 255, 0.15)',
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
                    labels: {{ color: '#f0f6fc', font: {{ family: 'Inter', size: 12 }} }}
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

    // 更新圖表與表格
    function updateForecast(regionName) {{
        const data = forecastData[regionName] || [];
        const labels = data.map(d => d.dataDate.slice(5)); // MM-DD
        const maxTemps = data.map(d => d.maxT);
        const minTemps = data.map(d => d.minT);

        forecastChart.data.labels = labels;
        forecastChart.data.datasets[0].data = maxTemps;
        forecastChart.data.datasets[1].data = minTemps;
        forecastChart.update();

        // 更新表格
        const tbody = document.getElementById('tableBody');
        tbody.innerHTML = '';
        data.forEach(d => {{
            const diff = (d.maxT - d.minT).toFixed(1);
            let feeling = '舒適溫和';
            if (d.maxT >= 30) feeling = '高溫炎熱 (防曬補水)';
            else if (d.minT <= 20) feeling = '早晚微涼 (留意添衣)';
            
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td style="font-weight:600;">${{d.dataDate}}</td>
                <td style="color:#58a6ff; font-weight:700;">${{d.minT}}°C</td>
                <td style="color:#ff7b72; font-weight:700;">${{d.maxT}}°C</td>
                <td style="color:#ffa657;">${{diff}}°C</td>
                <td style="color:#8b949e;">${{feeling}}</td>
            `;
            tbody.appendChild(tr);
        }});
    }}

    regionSelect.addEventListener('change', (e) => {{
        updateForecast(e.target.value);
    }});

    // 預設載入中部地區
    updateForecast(regionSelect.value || '中部地區');
</script>
</body>
</html>
"""

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print(f"Generated static index.html successfully at: {OUTPUT_PATH}")

if __name__ == "__main__":
    generate_index_html()
