"""
line_flex.py
Gate 5: LINE Bot Flex Message 動態圖卡模組

提供 create_weather_flex() 工廠函數，
根據測站資料生成 LINE Flex Message 的 JSON Payload。
"""
from typing import Optional


def _temp_color(temp: float) -> str:
    """依溫度回傳對應的十六進位色碼。"""
    if temp >= 30:
        return "#FF4444"   # 高溫紅
    elif temp >= 20:
        return "#FF8C00"   # 暖溫橘
    else:
        return "#4287F5"   # 涼溫藍


def _temp_label(temp: float) -> str:
    """依溫度回傳中文標籤。"""
    if temp >= 30:
        return "🔴 高溫"
    elif temp >= 20:
        return "🟠 暖和"
    else:
        return "🔵 涼爽"


DEFAULT_PUBLIC_MAP_URL = "https://dds852456tw.github.io/L2CWAv2/"


def _sanitize_map_url(url: Optional[str]) -> str:
    """確保地圖連結永遠是公開可存取網址，防止 localhost 出現在 LINE 訊息按鈕。"""
    if not url or "localhost" in url or "127.0.0.1" in url or "0.0.0.0" in url:
        return DEFAULT_PUBLIC_MAP_URL
    return url


def create_weather_flex(
    station_name: str,
    temperature: float,
    obs_time: str,
    lat: float,
    lon: float,
    map_url: Optional[str] = None,
) -> dict:
    """
    建立天氣資訊 Flex Message Bubble。

    Args:
        station_name: 測站名稱
        temperature:  氣溫 (°C)
        obs_time:     觀測時間字串
        lat:          緯度
        lon:          經度
        map_url:      Streamlit 地圖網址（可選）

    Returns:
        dict: LINE Flex Message 的完整 JSON payload（type: flex）
    """
    color = _temp_color(temperature)
    label = _temp_label(temperature)
    valid_map_url = _sanitize_map_url(map_url)

    bubble = {
        "type": "bubble",
        "size": "mega",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#1A1A2E",
            "paddingAll": "20px",
            "contents": [
                {
                    "type": "text",
                    "text": "🌡 台灣即時天氣",
                    "color": "#FFFFFF",
                    "size": "sm",
                    "weight": "bold",
                },
                {
                    "type": "text",
                    "text": station_name,
                    "color": "#E0E0E0",
                    "size": "xxl",
                    "weight": "bold",
                    "margin": "md",
                },
            ],
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#16213E",
            "paddingAll": "20px",
            "contents": [
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {
                            "type": "text",
                            "text": f"{temperature}°C",
                            "color": color,
                            "size": "5xl",
                            "weight": "bold",
                            "flex": 2,
                            "gravity": "center",
                        },
                        {
                            "type": "box",
                            "layout": "vertical",
                            "flex": 1,
                            "contents": [
                                {
                                    "type": "text",
                                    "text": label,
                                    "color": color,
                                    "size": "sm",
                                    "weight": "bold",
                                },
                                {
                                    "type": "text",
                                    "text": f"📍 {lat:.4f}N",
                                    "color": "#AAAAAA",
                                    "size": "xs",
                                    "margin": "sm",
                                },
                                {
                                    "type": "text",
                                    "text": f"📍 {lon:.4f}E",
                                    "color": "#AAAAAA",
                                    "size": "xs",
                                },
                            ],
                        },
                    ],
                },
                {
                    "type": "separator",
                    "margin": "lg",
                    "color": "#333355",
                },
                {
                    "type": "text",
                    "text": f"🕐 觀測時間：{obs_time}",
                    "color": "#888888",
                    "size": "xs",
                    "margin": "lg",
                },
            ],
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#0F3460",
            "paddingAll": "15px",
            "contents": [
                {
                    "type": "button",
                    "action": {
                        "type": "uri",
                        "label": "🗺 查看即時地圖",
                        "uri": valid_map_url,
                    },
                    "style": "primary",
                    "color": "#E94560",
                    "height": "sm",
                }
            ],
        },
    }

    return {
        "type": "flex",
        "altText": f"【{station_name}】現在氣溫 {temperature}°C {label}",
        "contents": bubble,
    }


def create_map_flex(map_url: Optional[str] = None) -> dict:
    """
    建立「即時地圖」快捷 Flex Message。

    Args:
        map_url: Streamlit 地圖網址

    Returns:
        dict: LINE Flex Message JSON payload
    """
    valid_map_url = _sanitize_map_url(map_url)
    return {
        "type": "flex",
        "altText": "🗺 台灣即時天氣地圖 - 點擊查看",
        "contents": {
            "type": "bubble",
            "size": "kilo",
            "body": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#1A1A2E",
                "paddingAll": "20px",
                "contents": [
                    {
                        "type": "text",
                        "text": "🗺 台灣即時天氣地圖",
                        "color": "#FFFFFF",
                        "weight": "bold",
                        "size": "lg",
                    },
                    {
                        "type": "text",
                        "text": "Airbox 風格暗黑地圖，即時顯示全台測站溫度",
                        "color": "#AAAAAA",
                        "size": "sm",
                        "margin": "md",
                        "wrap": True,
                    },
                ],
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#0F3460",
                "paddingAll": "15px",
                "contents": [
                    {
                        "type": "button",
                        "action": {
                            "type": "uri",
                            "label": "開啟地圖",
                            "uri": valid_map_url,
                        },
                        "style": "primary",
                        "color": "#E94560",
                    }
                ],
            },
        },
    }
