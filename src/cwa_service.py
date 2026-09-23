"""
cwa_service.py
Gate 1: CWA API 串接與資料解析
Gate 2: 數據清理邏輯

API: O-A0003-001 (局屬氣象站-現在天氣觀測報告)
"""
import os
import requests
import logging
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ── 常數 ────────────────────────────────────────────────────────────────────
CWA_BASE_URL = "https://opendata.cwa.gov.tw/api/v1/rest/datastore"
DATASET_ID   = "O-A0003-001"
WARNINGS_DATASET_ID = "W-C0033-001"
FORECAST_DATASET_ID = "F-D0047-091"
API_KEY      = os.getenv("CWA_API_KEY", "CWA-55FDA6D3-A43C-4AE0-BB30-E62D5F684FB2")

# 異常值門檻（氣象局慣例用 -99 表示無效資料）
INVALID_TEMP_VALUES = {-99, -99.0}

# 縣市與分區對照表（符合煥哥課程分區規範）
COUNTY_TO_REGION = {
    '基隆市': '北部地區', '臺北市': '北部地區', '新北市': '北部地區', '桃園市': '北部地區',
    '新竹市': '北部地區', '新竹縣': '北部地區', '苗栗縣': '北部地區',
    '臺中市': '中部地區', '彰化縣': '中部地區', '南投縣': '中部地區',
    '雲林縣': '中部地區', '嘉義市': '中部地區', '嘉義縣': '中部地區',
    '臺南市': '南部地區', '高雄市': '南部地區', '屏東縣': '南部地區',
    '宜蘭縣': '東北部地區',
    '花蓮縣': '東部地區',
    '臺東縣': '東南部地區',
    '澎湖縣': '離島地區', '金門縣': '離島地區', '連江縣': '離島地區'
}

# 台灣主要分區中心座標（供 Folium 地圖視覺化使用）
REGION_COORDS = {
    '北部地區':   (25.02, 121.50),
    '東北部地區': (24.75, 121.75),
    '中部地區':   (24.15, 120.68),
    '東部地區':   (23.98, 121.60),
    '南部地區':   (22.99, 120.21),
    '東南部地區': (22.75, 121.14),
    '離島地區':   (23.57, 119.58),
}


# ── Gate 1: 資料擷取與解析 ───────────────────────────────────────────────────
def fetch_raw_data(limit: int = 500) -> dict:
    """
    向 CWA 開放資料平台發送 HTTP GET 並回傳原始 JSON。

    Args:
        limit: 最多取得筆數（預設 500，涵蓋全台所有局屬測站）

    Returns:
        dict: API 回應的原始 JSON 物件

    Raises:
        RuntimeError: 當 API 請求失敗時
    """
    url = f"{CWA_BASE_URL}/{DATASET_ID}"
    params = {
        "Authorization": API_KEY,
        "limit": limit,
        "format": "JSON",
    }

    try:
        resp = requests.get(url, params=params, timeout=30, verify=False)
        resp.raise_for_status()
        data = resp.json()
        logger.info(f"[CWA] 成功取得 API 回應，狀態碼: {resp.status_code}")
        return data
    except requests.exceptions.RequestException as e:
        logger.error(f"[CWA] API 請求失敗: {e}")
        raise RuntimeError(f"CWA API 請求失敗: {e}") from e


def parse_station_record(station: dict) -> Optional[dict]:
    """
    將單一測站 JSON 物件解析成標準化的 dict。

    解析欄位：
      - StationName (str)
      - StationId (str)
      - StationLatitude (float)
      - StationLongitude (float)
      - AirTemperature (float)
      - ObsTime (str, ISO-8601)
      - WindSpeed, WindDirection, RelativeHumidity, Precipitation, Weather (類 Windy / 滿分專案擴充)

    Args:
        station: API 回傳的單一測站原始 dict

    Returns:
        dict | None: 解析後的測站資料；若必要欄位缺失則回傳 None
    """
    try:
        weather_elem = station.get("WeatherElement", {})
        geo_info     = station.get("GeoInfo", {})
        coordinates  = geo_info.get("Coordinates", [])

        # 找出 WGS84 座標
        lat = lon = None
        for coord in coordinates:
            if coord.get("CoordinateName") == "WGS84":
                lat = float(coord.get("StationLatitude", 0))
                lon = float(coord.get("StationLongitude", 0))
                break

        # 若無 WGS84 就嘗試直接取值
        if lat is None:
            lat = float(geo_info.get("StationLatitude", 0))
            lon = float(geo_info.get("StationLongitude", 0))

        obs_time_raw = station.get("ObsTime", {}).get("DateTime", "")
        air_temp_raw = weather_elem.get("AirTemperature", -99)

        # 滿分專案擴充氣象數值
        wind_speed = float(weather_elem.get("WindSpeed", 0) or 0)
        wind_direction = float(weather_elem.get("WindDirection", 0) or 0)
        humidity = float(weather_elem.get("RelativeHumidity", 0) or 0)
        
        # 降雨量解析
        precip_raw = weather_elem.get("Now", {}).get("Precipitation", 0)
        try:
            precip = float(precip_raw) if precip_raw not in ["-99", -99, "T", None] else 0.0
        except (ValueError, TypeError):
            precip = 0.0
            
        weather_desc = str(weather_elem.get("Weather", "") or "")

        return {
            "station_id":        station.get("StationId", "UNKNOWN"),
            "station_name":      station.get("StationName", "未知測站"),
            "latitude":          lat,
            "longitude":         lon,
            "air_temperature":   float(air_temp_raw),
            "wind_speed":        max(0.0, wind_speed) if wind_speed != -99 else 0.0,
            "wind_direction":    wind_direction if wind_direction != -99 else 0.0,
            "relative_humidity": humidity if humidity != -99 else 0.0,
            "precipitation":     precip,
            "weather_desc":      weather_desc,
            "obs_time":          obs_time_raw,
            "fetched_at":        datetime.utcnow().isoformat() + "Z",
        }
    except (KeyError, TypeError, ValueError) as e:
        logger.warning(f"[CWA] 解析測站資料失敗: {e} | 資料: {station.get('StationId', '?')}")
        return None


# ── Gate 2: 資料清理 ─────────────────────────────────────────────────────────
def is_valid_record(record: dict) -> bool:
    """
    檢驗一筆解析後的記錄是否為有效資料。

    過濾條件：
      1. AirTemperature 不得為 -99 或 -99.0（氣象局缺值旗標）
      2. 緯度必須在台灣合理範圍 (21° ~ 26°)
      3. 經度必須在台灣合理範圍 (119° ~ 123°)

    Args:
        record: 由 parse_station_record() 回傳的 dict

    Returns:
        bool: True 表示有效記錄
    """
    temp = record.get("air_temperature")
    lat  = record.get("latitude", 0)
    lon  = record.get("longitude", 0)

    if temp in INVALID_TEMP_VALUES or temp is None:
        return False

    # 台灣本島 + 離島合理範圍（含蘭嶼、澎湖）
    if not (20.5 <= lat <= 26.5):
        return False
    if not (119.0 <= lon <= 122.5):
        return False

    return True


def get_clean_weather_data() -> list:
    """
    完整流程：取得 → 解析 → 清理，回傳乾淨的測站清單。

    Returns:
        list[dict]: 有效的測站天氣資料列表
    """
    raw      = fetch_raw_data()
    stations = (
        raw.get("records", {})
           .get("Station", [])
    )
    logger.info(f"[CWA] 原始測站數: {len(stations)}")

    parsed  = [parse_station_record(s) for s in stations]
    valid   = [r for r in parsed if r and is_valid_record(r)]

    logger.info(
        f"[CWA] 解析完成: 原始 {len(stations)} 站 → "
        f"有效 {len(valid)} 站（剔除 {len(stations) - len(valid)} 筆異常）"
    )
    return valid


# ── 滿分專案擴充：天氣特報示警 (Warnings Banner) ─────────────────────────────
def fetch_weather_warnings() -> list:
    """
    向 CWA 抓取即時天氣特報 (W-C0033-001)。

    Returns:
        list[dict]: 目前生效中的天氣特報列表
    """
    url = f"{CWA_BASE_URL}/{WARNINGS_DATASET_ID}"
    params = {"Authorization": API_KEY, "format": "JSON"}
    try:
        resp = requests.get(url, params=params, timeout=10, verify=False)
        if resp.status_code != 200:
            return []
        data = resp.json()
        records = data.get("records", {}).get("record", [])
        warnings = []
        for r in records:
            hazard = r.get("hazardConditions", {}).get("hazards", [])
            for h in hazard:
                info = h.get("info", {})
                warnings.append({
                    "event": info.get("language", [{}])[0].get("phenomena", "天氣特報"),
                    "significance": info.get("language", [{}])[0].get("significance", "警戒"),
                    "headline": r.get("contents", {}).get("headline", ""),
                    "effective": r.get("contents", {}).get("effective", ""),
                    "expires": r.get("contents", {}).get("expires", ""),
                })
        return warnings
    except Exception as e:
        logger.warning(f"[CWA] 取得天氣特報失敗: {e}")
        return []


# ── 滿分專案擴充：RainViewer 雷達回波圖層 ────────────────────────────────────
def get_radar_tile_url() -> Optional[str]:
    """
    向 RainViewer API 取得最新雷達回波 XYZ 圖磚 URL。
    與底圖同為 Web Mercator，天生正確對齊。

    Returns:
        str | None: Folium TileLayer 可用的圖磚 URL 範本
    """
    try:
        resp = requests.get("https://api.rainviewer.com/public/weather-maps.json", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            host = data.get("host", "https://tilecache.rainviewer.com")
            radar_past = data.get("radar", {}).get("past", [])
            if radar_past:
                latest_path = radar_past[-1]["path"]
                # Leaflet / Folium XYZ 格式
                return f"{host}{latest_path}/256/{{z}}/{{x}}/{{y}}/2/1_1.png"
    except Exception as e:
        logger.warning(f"[RainViewer] 取得雷達圖磚失敗: {e}")
    return None


# ── 煥哥課程環節 4~7：一週天氣預報資料處理 ──────────────────────────────────
def get_clean_forecast_data() -> list:
    """
    取得並清洗 CWA 臺灣未來一週天氣預報 (F-D0047-091)。
    計算 6 大分區（北部、中部、南部、東北部、東部、東南部、離島）及 22 縣市的一週每日 MinT / MaxT。

    Returns:
        list[dict]: [{"region_name": str, "data_date": str, "min_t": float, "max_t": float}, ...]
    """
    from collections import defaultdict
    url = f"{CWA_BASE_URL}/{FORECAST_DATASET_ID}"
    params = {"Authorization": API_KEY, "format": "JSON"}

    try:
        resp = requests.get(url, params=params, timeout=20, verify=False)
        resp.raise_for_status()
        data = resp.json()
        locations = data.get("records", {}).get("Locations", [{}])[0].get("Location", [])
    except Exception as e:
        logger.error(f"[CWA] 取得預報資料失敗: {e}")
        return []

    # 1. 整理各縣市每日的高低溫數值
    county_daily = defaultdict(lambda: defaultdict(lambda: {"min": [], "max": []}))

    for loc in locations:
        c_name = loc.get("LocationName", "")
        for elem in loc.get("WeatherElement", []):
            el_name = elem.get("ElementName", "")
            if el_name == "最低溫度":
                for t in elem.get("Time", []):
                    d = t.get("StartTime", "")[:10]
                    vals = t.get("ElementValue", [])
                    if vals and vals[0].get("MinTemperature"):
                        try:
                            county_daily[c_name][d]["min"].append(float(vals[0]["MinTemperature"]))
                        except ValueError:
                            pass
            elif el_name == "最高溫度":
                for t in elem.get("Time", []):
                    d = t.get("StartTime", "")[:10]
                    vals = t.get("ElementValue", [])
                    if vals and vals[0].get("MaxTemperature"):
                        try:
                            county_daily[c_name][d]["max"].append(float(vals[0]["MaxTemperature"]))
                        except ValueError:
                            pass

    # 2. 彙整各分區 (6 大分區 + 離島)
    region_daily = defaultdict(lambda: defaultdict(lambda: {"min": [], "max": []}))
    for c_name, dates in county_daily.items():
        reg = COUNTY_TO_REGION.get(c_name, "其他地區")
        for d, vals in dates.items():
            if vals["min"]:
                region_daily[reg][d]["min"].extend(vals["min"])
            if vals["max"]:
                region_daily[reg][d]["max"].extend(vals["max"])

    results = []

    # 加入 6 大分區預報（優先符合煥哥課程標準）
    for reg, dates in region_daily.items():
        for d in sorted(dates.keys()):
            mins = dates[d]["min"]
            maxs = dates[d]["max"]
            if mins and maxs:
                results.append({
                    "region_name": reg,
                    "data_date":   d,
                    "min_t":       round(sum(mins) / len(mins), 1),
                    "max_t":       round(sum(maxs) / len(maxs), 1),
                })

    # 同步加入 22 縣市獨立預報（提供更細膩的選擇）
    for c_name, dates in county_daily.items():
        for d in sorted(dates.keys()):
            mins = dates[d]["min"]
            maxs = dates[d]["max"]
            if mins and maxs:
                results.append({
                    "region_name": c_name,
                    "data_date":   d,
                    "min_t":       round(min(mins), 1),
                    "max_t":       round(max(maxs), 1),
                })

    logger.info(f"[CWA] 成功解析一週預報資料共 {len(results)} 筆")
    return results


# ── 獨立執行驗證 ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json
    import warnings
    warnings.filterwarnings("ignore", message="Unverified HTTPS request")

    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    records = get_clean_weather_data()
    print(f"\nValid station count: {len(records)}")
    print("\nFirst 5 records preview:")
    for r in records[:5]:
        print(json.dumps(r, ensure_ascii=False, indent=2))

    forecasts = get_clean_forecast_data()
    print(f"\nValid forecast count: {len(forecasts)}")
    print("Sample forecast:")
    for f in forecasts[:6]:
        print(f)
