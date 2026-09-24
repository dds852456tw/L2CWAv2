"""
bot.py
Gate 5: LINE Bot Webhook 入口與訊息邏輯

整合 CWA 天氣資料與 LINE Bot SDK，
提供「現在天氣」與「即時地圖」關鍵字回應。
"""
import os
import logging
import warnings
warnings.filterwarnings("ignore")

from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    FlexMessage,
    FlexContainer,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from dotenv import load_dotenv

load_dotenv()

import sys
sys.path.insert(0, os.path.dirname(__file__))

from src.cwa_service import get_clean_weather_data, get_clothing_advice, get_clean_forecast_data
from src.db_service import (
    init_db,
    upsert_records,
    get_all_stations,
    get_temp_distribution,
    get_forecast_by_region,
    get_forecast_regions,
)
from src.line_flex import create_weather_flex, create_map_flex

# ── 設定 ─────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

LINE_CHANNEL_SECRET      = os.getenv("LINE_CHANNEL_SECRET", "")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
DEFAULT_MAP_URL = "https://dds852456tw.github.io/L2CWAv2/"
_raw_map_url = os.getenv("STREAMLIT_MAP_URL", DEFAULT_MAP_URL).strip()
if not _raw_map_url or any(h in _raw_map_url.lower() for h in ["localhost", "127.0.0.1", "0.0.0.0"]):
    STREAMLIT_MAP_URL = DEFAULT_MAP_URL
else:
    STREAMLIT_MAP_URL = _raw_map_url

COUNTY_MAP = {
    "台北市": "臺北市", "台北": "臺北市", "臺北市": "臺北市", "臺北": "臺北市",
    "新北市": "新北市", "新北": "新北市",
    "桃園市": "桃園市", "桃園": "桃園市",
    "台中市": "臺中市", "台中": "臺中市", "臺中市": "臺中市", "臺中": "臺中市",
    "台南市": "臺南市", "台南": "臺南市", "臺南市": "臺南市", "臺南": "臺南市",
    "高雄市": "高雄市", "高雄": "高雄市",
    "基隆市": "基隆市", "基隆": "基隆市",
    "新竹市": "新竹市", "新竹縣": "新竹縣", "新竹": "新竹市",
    "苗栗縣": "苗栗縣", "苗栗": "苗栗縣",
    "彰化縣": "彰化縣", "彰化": "彰化縣",
    "南投縣": "南投縣", "南投": "南投縣",
    "雲林縣": "雲林縣", "雲林": "雲林縣",
    "嘉義市": "嘉義市", "嘉義縣": "嘉義縣", "嘉義": "嘉義市",
    "屏東縣": "屏東縣", "屏東": "屏東縣",
    "宜蘭縣": "宜蘭縣", "宜蘭": "宜蘭縣",
    "花蓮縣": "花蓮縣", "花蓮": "花蓮縣",
    "台東縣": "臺東縣", "台東": "臺東縣", "臺東縣": "臺東縣", "臺東": "臺東縣",
    "澎湖縣": "澎湖縣", "澎湖": "澎湖縣",
    "金門縣": "金門縣", "金門": "金門縣",
    "連江縣": "連江縣", "連江": "連江縣", "馬祖": "連江縣",
    "北部": "北部地區", "中部": "中部地區", "南部": "南部地區",
    "東北部": "東北部地區", "東部": "東部地區", "東南部": "東南部地區", "離島": "離島地區"
}


def filter_stations_by_region(stations: list, region_name: str) -> list:
    """
    依縣市或分區精準過濾測站。
    1. 優先比對 county_name（正體臺與台相容）
    2. 次要比對 station_name（正體臺與台相容）
    """
    if not region_name or not stations:
        return stations
    norm_reg = region_name.replace("臺", "台")
    pure_name = norm_reg.replace("市", "").replace("縣", "").replace("地區", "")

    # 1. 優先精準比對 county_name
    c_matches = []
    for s in stations:
        c_name = (s.get("county_name") or "").replace("臺", "台")
        if pure_name and pure_name in c_name:
            c_matches.append(s)
    if c_matches:
        return c_matches

    # 2. 次要比對 station_name
    s_matches = []
    for s in stations:
        s_name = (s.get("station_name") or "").replace("臺", "台")
        if pure_name and pure_name in s_name:
            s_matches.append(s)
    if s_matches:
        return s_matches

    return stations

# ── Flask & LINE SDK 初始化 ───────────────────────────────────────────────────
app     = Flask(__name__)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)


# ── Webhook 路由 ─────────────────────────────────────────────────────────────
@app.route("/callback", methods=["POST"])
def callback():
    """LINE Platform 發送 Webhook 事件到此端點。"""
    signature = request.headers.get("X-Line-Signature", "")
    body      = request.get_data(as_text=True)
    logger.info(f"[Bot] 收到 Webhook 事件: {body[:200]}")

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.warning("[Bot] 簽名驗證失敗，拒絕請求")
        abort(400)

    return "OK"


@app.route("/", methods=["GET"])
def index():
    """首頁端點。"""
    return {
        "status": "online",
        "service": "L2CWAv2 Taiwan Weather Bot & API",
        "endpoints": {
            "health": "/health",
            "webhook": "/callback (POST)"
        },
        "description": "CWA Open Data Taiwan Weather Monitoring System"
    }, 200


@app.route("/health", methods=["GET"])
def health():
    """健康檢查端點。"""
    return {"status": "ok", "service": "L2CWAv2 LINE Bot"}, 200


# ── 訊息事件處理 ─────────────────────────────────────────────────────────────
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event: MessageEvent):
    """
    處理使用者文字訊息。

    支援關鍵字：
      - 「現在天氣」或「天氣」 → 最熱測站 Flex Message 圖卡與全台統計
      - 「建議穿著」、「穿什麼」、「帶傘」、「雨衣」、「雨傘」 → 依風速與降雨機率判斷雨具及穿搭
      - 指定縣市（例如「台北 天氣」、「台中 要帶傘嗎」） → 查詢該縣市即時預報與生活指南
      - 「即時地圖」或「地圖」 → 回傳 Streamlit 地圖連結
      - 其他 → 回傳操作指令指南
    """
    user_text = event.message.text.strip()
    logger.info(f"[Bot] 使用者訊息: {user_text}")

    reply_messages = []

    # 檢查是否指定特定縣市 (長詞優先比對)
    matched_region = None
    for kw in sorted(COUNTY_MAP.keys(), key=lambda x: -len(x)):
        if kw in user_text:
            matched_region = COUNTY_MAP[kw]
            break

    # 1. 穿搭、雨具、風速、降雨機率或帶傘判斷
    is_clothing_query = any(kw in user_text for kw in [
        "穿什麼", "穿著", "穿搭", "衣服", "建議穿著",
        "帶傘", "雨傘", "雨衣", "雨具", "傘", "風速", "降雨機率", "出門"
    ])

    if is_clothing_query or (matched_region and any(w in user_text for w in ["傘", "穿", "雨"])):
        target_name = matched_region or "北部地區"
        try:
            # 優先從 DB 撈取該分區的一週預報記錄
            f_rows = []
            try:
                f_rows = get_forecast_by_region(target_name)
            except Exception:
                pass

            # 若 DB 暫無資料，fallback 直打 CWA 預報 API
            if not f_rows:
                all_forecasts = get_clean_forecast_data()
                f_rows = [f for f in all_forecasts if f.get("region_name") == target_name]
                if not f_rows and all_forecasts:
                    f_rows = all_forecasts[:7]

            if f_rows:
                from datetime import datetime
                today_str = datetime.now().strftime("%Y-%m-%d")
                future_rows = [r for r in f_rows if (r.get("data_date") or r.get("dataDate", "")) >= today_str]
                today_f = future_rows[0] if future_rows else f_rows[0]

                min_t = float(today_f.get("min_t") or today_f.get("minT") or 22.0)
                max_t = float(today_f.get("max_t") or today_f.get("maxT") or 30.0)
                pop = float(today_f.get("pop", 0.0) or 0.0)
                ws = float(today_f.get("wind_speed", 2.0) or 2.0)
                wx = str(today_f.get("weather_desc", "多雲到晴") or "多雲到晴")

                # 防呆校正：若天氣現象含雨但機率為 0%，校正至合理值；風速保障常態基準
                if "雨" in wx and pop < 30.0:
                    pop = 40.0
                if ws <= 0.0:
                    ws = 2.0

                advice = get_clothing_advice(min_t, max_t, pop=pop, wind_speed=ws, weather_desc=wx)

                reply_text = (
                    f"👔【{target_name}】智慧穿搭與外出雨具指南\n"
                    f"📅 日期：{today_f.get('data_date') or today_f.get('dataDate', '')} ({wx})\n"
                    f"🌡 氣溫：{min_t}°C ~ {max_t}°C (體感：{advice['level']})\n"
                    f"🌧 降雨機率：{int(advice['pop'])}%\n"
                    f"💨 預估風速：{advice['wind_speed']} m/s\n\n"
                    f"☔ 外出雨具指引：\n"
                    f"{advice['umbrella_title']}\n"
                    f"👉 推薦配備：{advice['umbrella_gear']}\n"
                    f"💡 叮嚀：{advice['umbrella_action']}\n\n"
                    f"─────────────────\n"
                    f"👕 上衣：{advice['top']}\n"
                    f"🧥 外套：{advice['outer']}\n"
                    f"👖 下著：{advice['bottom']}\n"
                    f"🧢 配件：{advice['accessory']}\n\n"
                    f"🧅 溫差叮嚀：{advice['temp_diff_tip']}"
                )
                reply_messages = [TextMessage(text=reply_text)]
            else:
                reply_messages = [TextMessage(text="⚠️ 目前暫無該地區預報數據，請稍候再試。")]
        except Exception as e:
            logger.error(f"[Bot] 穿著/雨具建議查詢失敗: {e}")
            reply_messages = [TextMessage(text=f"❌ 查詢失敗：{e}")]

    # 2. 地圖連結
    elif any(kw in user_text for kw in ["即時地圖", "地圖", "map"]):
        flex_payload = create_map_flex(STREAMLIT_MAP_URL)
        reply_messages = [
            FlexMessage(
                alt_text=flex_payload["altText"],
                contents=FlexContainer.from_dict(flex_payload["contents"]),
            )
        ]

    # 3. 即時天氣概況
    elif any(kw in user_text for kw in ["現在天氣", "天氣", "氣溫", "溫度"]) or matched_region:
        try:
            stations = []
            
            # 1. 優先嘗試自本地/暫存資料庫讀取 (Read-Only)
            try:
                stations = get_all_stations()
            except Exception as dbe:
                logger.warning(f"[Bot] 從 DB 讀取測站失敗，啟動 API Fallback: {dbe}")

            # 2. 若 DB 為空或讀取受阻，直接呼叫 CWA API 獲取即時觀測 (Fallback 機制)
            if not stations:
                logger.info("[Bot] 直接從中央氣象署 CWA API 獲取即時資料")
                records = get_clean_weather_data()
                if records:
                    stations = records
                    try:
                        upsert_records(records)
                    except Exception as we:
                        logger.debug(f"[Bot] 寫入暫存 DB 失敗 (可安全忽略): {we}")

            if stations:
                # 若使用者指定縣市，精準過濾該縣市測站
                if matched_region:
                    target_pool = filter_stations_by_region(stations, matched_region)
                else:
                    target_pool = stations

                valid_stations = [s for s in target_pool if s.get("air_temperature") is not None and s.get("air_temperature") > -90]
                pool_to_pick = valid_stations if valid_stations else target_pool
                hottest = max(pool_to_pick, key=lambda s: s.get("air_temperature", -99))

                flex_payload = create_weather_flex(
                    station_name=hottest.get("station_name", "觀測站"),
                    temperature=hottest.get("air_temperature", 0.0),
                    obs_time=hottest.get("obs_time", ""),
                    lat=hottest.get("latitude", 23.5),
                    lon=hottest.get("longitude", 121.0),
                    map_url=STREAMLIT_MAP_URL,
                )

                temps = [s["air_temperature"] for s in valid_stations]
                if temps:
                    avg_temp = round(sum(temps) / len(temps), 1)
                    max_temp = max(temps)
                    min_temp = min(temps)
                else:
                    avg_temp = max_temp = min_temp = "--"

                summary = (
                    f"📊 {'【' + matched_region + '】' if matched_region else '全台'}即時觀測（{len(valid_stations)} 站）\n"
                    f"🌡 平均：{avg_temp}°C\n"
                    f"🔴 最高：{max_temp}°C\n"
                    f"🔵 最低：{min_temp}°C\n"
                    f"💡 提示：輸入「建議穿著」、「要帶傘嗎」可獲取風速、降雨機率與雨具穿搭指南！"
                )
                reply_messages = [
                    TextMessage(text=summary),
                    FlexMessage(
                        alt_text=flex_payload["altText"],
                        contents=FlexContainer.from_dict(flex_payload["contents"]),
                    ),
                ]
            else:
                reply_messages = [TextMessage(text="⚠️ 目前無法自氣象署取得即時觀測資料，請稍後再試。")]

        except Exception as e:
            logger.error(f"[Bot] 天氣查詢失敗: {e}")
            reply_messages = [TextMessage(text=f"❌ 查詢天氣時發生錯誤：{e}")]

    # 4. 指令說明
    else:
        reply_messages = [
            TextMessage(
                text=(
                    "👋 你好！我是台灣即時天氣與智慧生活機器人 🌡\n\n"
                    "📌 推薦指令：\n"
                    "• 「現在天氣」— 查看即時溫度與最熱測站\n"
                    "• 「建議穿著」或「要帶傘嗎」— 依風速與降雨機率判斷雨衣或傘大小、穿搭指標\n"
                    "• 「台北 天氣 / 穿搭」— 查詢指定縣市的天氣與雨具建議\n"
                    "• 「即時地圖」— 開啟暗黑即時天氣地圖\n\n"
                    "請直接輸入以上文字即可開始！"
                )
            )
        ]

    with ApiClient(configuration) as api_client:
        line_api = MessagingApi(api_client)
        line_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=reply_messages,
            )
        )


# ── 啟動 ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    logger.info("[Bot] 初始化資料庫完成")
    logger.info(f"[Bot] LINE Bot 啟動，監聽 port 5000")
    logger.info(f"[Bot] Webhook URL: http://YOUR_DOMAIN/callback")
    app.run(host="0.0.0.0", port=5000, debug=False)
