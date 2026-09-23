# 🌡 L2CWAv2 — 台灣即時天氣監測 & 一週氣溫預報系統

> **滿分專案標竿 (huanchen1107/taiwan-weather-map) × 煥哥 AI 創新微課程 24 環節全面實現**  
> 結合中央氣象署 CWA 開放資料平台，提供全台 348 個測站即時監測、一週高低溫趨勢預報、天氣特報橫幅、RainViewer 雷達回波與 LINE Bot 查詢。

---

## 🌟 核心亮點功能

### 1. 仿照滿分專案 (huanchen1107/taiwan-weather-map)
- **Esri World Dark Gray Base 專業底圖**：徹底免 API Key、零浮水印干擾，呈現極致專業的深灰暗黑科技質感。
- **即時天氣特報橫幅 (Active Warning Banner)**：串接 CWA `W-C0033-001`，於頂部自動呈現生效中特報（高溫、強風、大雨）；無特報時呈現綠色安全標章。
- **多圖層模式切換**：支援「🌡️ 氣溫分佈」、「🧭 風向風速」、「🌧️ 雨量觀測」與「📡 即時雷達回波 (RainViewer)」。
- **即時雷達回波疊加**：串接 RainViewer 免費圖磚，精準 Web Mercator 投影對齊台灣上空。

### 2. 煥哥微課程 24 環節一週預報全實現
- **CWA `F-D0047-091` 預報解析**：結構化解析 6 大分區（北部、中部、南部、東北部、東部、東南部）及 22 縣市每日 MinT / MaxT。
- **SQLite `TemperatureForecasts` 資料庫 (環節 8 & 9)**：設計獨立預報表，具備 `UNIQUE(regionName, dataDate)` 防重複插入機制。
- **地區下拉選單 (Select Region) (環節 13 & 16)**：支援即時切換各地區與縣市。
- **一週高低溫雙折線圖 (環節 14 & 16)**：Altair 互動圖表，紅線呈現最高溫 MaxT、藍線呈現最低溫 MinT，支援懸停數值。
- **一週預報資料表格 (環節 15 & 16)**：完整呈現日期、最低溫、最高溫與日溫差。
- **選擇日期顯示地圖 (Select Date) (環節 17 & 18)**：切換預報日期，全台分區中心依當日均溫自動著色並提供彈窗詳情。

---

## 📌 系統架構

```
L2CWAv2/
├── .env.example              # 環境變數範本（請複製為 .env）
├── .gitignore                # Git 忽略設定（防止機密資訊洩漏）
├── README.md                 # 專案完整說明文件
├── requirements.txt          # Python 套件依賴
├── app.py                    # Streamlit 前端（即時監測 + 一週預報雙分頁）
├── bot.py                    # LINE Bot Webhook 入口
├── data/
│   ├── weather.db            # SQLite 本地資料庫 (realtime_weather & TemperatureForecasts)
│   └── schema_preview.json   # API 解析驗證結果（Gate 1 Artifact）
├── .streamlit/
│   ├── config.toml           # Streamlit 主題設定
│   └── secrets.toml          # 雲端部署密鑰（勿提交 Git）
└── src/
    ├── __init__.py
    ├── cwa_service.py         # CWA 即時/預報/特報串接與 RainViewer 雷達
    ├── db_service.py          # SQLite Upsert 寫入與預報查詢
    └── line_flex.py           # LINE Bot Flex Message 模組
```

---

## 🚀 快速開始

### 1. 環境準備

```bash
# 克隆專案
git clone https://github.com/dds852456tw/L2CWAv2.git
cd L2CWAv2

# 建立虛擬環境（建議）
python -m venv venv
source venv/bin/activate      # Linux/Mac
venv\Scripts\activate         # Windows

# 安裝套件
pip install -r requirements.txt
```

### 2. 環境變數設定

```bash
cp .env.example .env
```

編輯 `.env`：

```dotenv
CWA_API_KEY=CWA-你的實際金鑰
LINE_CHANNEL_SECRET=你的_channel_secret
LINE_CHANNEL_ACCESS_TOKEN=你的_access_token
STREAMLIT_MAP_URL=http://localhost:8501
```

### 3. 啟動 Streamlit 地圖

```bash
python -m streamlit run app.py
```

開啟瀏覽器訪問 **http://localhost:8501** 即可看到 Airbox 暗黑地圖！

### 4. 啟動 LINE Bot（可選）

```bash
python bot.py
```

> 搭配 ngrok 本地測試：`ngrok http 5000`  
> 將 HTTPS URL + `/callback` 填入 LINE Developers Console。

---

## 🗂 5-Gate 開發紀錄

### Gate 1: API 串接與資料解析 ✅

| 項目 | 結果 |
|------|------|
| 資料集 | O-A0003-001 局屬氣象站-現在天氣觀測報告 |
| API 回應狀態 | HTTP 200 ✅ |
| 原始站數 | 363 站 |
| 有效站數 | **347 站** |
| 解析欄位 | StationName, StationId, Latitude, Longitude, AirTemperature, ObsTime |
| Artifact | `data/schema_preview.json` |

### Gate 2: 數據清理與持久化 ✅

| 項目 | 結果 |
|------|------|
| 資料庫 | `data/weather.db` (SQLite) |
| 資料表 | `realtime_weather` |
| 清理規則 | 剔除 AirTemperature = -99 / 座標超出台灣範圍 |
| 剔除筆數 | **16 筆**異常值 |
| Upsert 驗證 | 二次插入後仍為 347 筆 ✅ |

### Gate 3 & 4: Airbox 地圖 UI ✅

| 項目 | 說明 |
|------|------|
| 底圖 | Folium CartoDB dark_matter |
| 標記顏色 | 🔴 ≥30°C / 🟠 20~29°C / 🔵 <20°C |
| 快取策略 | @st.cache_data(ttl=300) — 每 5 分鐘更新 |

### Gate 5: LINE Bot 整合與部署準備 ✅

| 觸發關鍵字 | 回應 |
|-----------|------|
| 現在天氣、天氣、氣溫、溫度 | 統計摘要 + Flex Card |
| 即時地圖、地圖、map | Streamlit 地圖連結 |

---

## 🌡 LINE Bot 指令

| 訊息 | 回應 |
|------|------|
| 現在天氣 | 全台統計摘要 + 最熱測站 Flex Card |
| 即時地圖 | Streamlit 地圖連結 |
| 其他 | 使用說明 |

---

## ☁️ 部署指南

### Streamlit Cloud

1. Fork 本專案至 GitHub
2. 前往 [share.streamlit.io](https://share.streamlit.io/)，連接儲存庫
3. 在 Secrets 設定填入 API Key 與 LINE Token
4. 取得公開 URL 後更新 `STREAMLIT_MAP_URL`

### LINE Bot (Railway/Render)

1. 設定環境變數（同 `.env` 內容）
2. 取得公開 HTTPS URL，填入 LINE Developers Console Webhook
3. Webhook 路徑：`https://你的域名/callback`

---

## 🔑 API 資訊

- **資料集**: `O-A0003-001` 局屬氣象站-現在天氣觀測報告
- **更新頻率**: 每 10 分鐘
- **申請金鑰**: [opendata.cwa.gov.tw](https://opendata.cwa.gov.tw/)
- **LINE Bot SDK 文件**: [developers.line.biz](https://developers.line.biz/)

---

## 🛡️ 資安說明

| 檔案 | 狀態 | 說明 |
|------|------|------|
| `.env` | ❌ Git 排除 | 包含實際 API Key |
| `.streamlit/secrets.toml` | ❌ Git 排除 | 雲端部署密鑰 |
| `.env.example` | ✅ 可提交 | 不含實際金鑰的範本 |
| `data/weather.db` | ❌ Git 排除 | 本地資料庫 |

---

## 📦 套件

```
requests · streamlit · streamlit-folium · folium
pandas · line-bot-sdk · flask · python-dotenv
```

---

*由 Antigravity AI 全端工程師協助建置 | 2026-09-23*
