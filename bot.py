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

from src.cwa_service import get_clean_weather_data
from src.db_service import init_db, upsert_records, get_all_stations, get_temp_distribution
from src.line_flex import create_weather_flex, create_map_flex

# ── 設定 ─────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

LINE_CHANNEL_SECRET      = os.getenv("LINE_CHANNEL_SECRET", "")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
STREAMLIT_MAP_URL        = os.getenv("STREAMLIT_MAP_URL", "http://localhost:8501")

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

    關鍵字觸發：
      - 「現在天氣」或「天氣」 → 回傳最熱測站的 Flex Message 圖卡
      - 「即時地圖」或「地圖」 → 回傳 Streamlit 地圖連結
      - 其他 → 回傳使用說明
    """
    user_text = event.message.text.strip()
    logger.info(f"[Bot] 使用者訊息: {user_text}")

    reply_messages = []

    if any(kw in user_text for kw in ["現在天氣", "天氣", "氣溫", "溫度"]):
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
                    # 安全嘗試寫入暫存 DB（若唯讀環境寫入失敗也不影響對使用者的回覆）
                    try:
                        upsert_records(records)
                    except Exception as we:
                        logger.debug(f"[Bot] 寫入暫存 DB 失敗 (可安全忽略): {we}")

            if stations:
                # 篩選出有效氣溫測站並找出最熱站點
                valid_stations = [s for s in stations if s.get("air_temperature") is not None and s.get("air_temperature") > -90]
                target_pool = valid_stations if valid_stations else stations
                hottest = max(target_pool, key=lambda s: s.get("air_temperature", -99))

                flex_payload = create_weather_flex(
                    station_name=hottest.get("station_name", "觀測站"),
                    temperature=hottest.get("air_temperature", 0.0),
                    obs_time=hottest.get("obs_time", ""),
                    lat=hottest.get("latitude", 23.5),
                    lon=hottest.get("longitude", 121.0),
                    map_url=STREAMLIT_MAP_URL,
                )

                # 即時在記憶體中快速計算全台統計摘要（無需強制依賴 SQL PRAGMA/DB 連線）
                temps = [s["air_temperature"] for s in valid_stations]
                if temps:
                    avg_temp = round(sum(temps) / len(temps), 1)
                    max_temp = max(temps)
                    min_temp = min(temps)
                else:
                    avg_temp = max_temp = min_temp = "--"

                summary = (
                    f"📊 全台天氣概況（{len(valid_stations)} 站）\n"
                    f"🌡 平均：{avg_temp}°C\n"
                    f"🔴 最高：{max_temp}°C\n"
                    f"🔵 最低：{min_temp}°C"
                )
                reply_messages = [
                    TextMessage(text=summary),
                    FlexMessage(
                        alt_text=flex_payload["altText"],
                        contents=FlexContainer.from_dict(flex_payload["contents"]),
                    ),
                ]
            else:
                reply_messages = [TextMessage(text="⚠️ 目前無法自氣象署取得即時觀測資料，請確認 API Key 設定或稍後再試。")]

        except Exception as e:
            logger.error(f"[Bot] 天氣查詢失敗: {e}")
            reply_messages = [TextMessage(text=f"❌ 查詢天氣時發生錯誤：{e}")]

    elif any(kw in user_text for kw in ["即時地圖", "地圖", "map"]):
        flex_payload = create_map_flex(STREAMLIT_MAP_URL)
        reply_messages = [
            FlexMessage(
                alt_text=flex_payload["altText"],
                contents=FlexContainer.from_dict(flex_payload["contents"]),
            )
        ]

    else:
        reply_messages = [
            TextMessage(
                text=(
                    "👋 你好！我是台灣即時天氣機器人 🌡\n\n"
                    "📌 指令說明：\n"
                    "• 「現在天氣」— 查看即時溫度\n"
                    "• 「即時地圖」— 開啟暗黑天氣地圖\n\n"
                    "請輸入以上關鍵字開始使用！"
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
