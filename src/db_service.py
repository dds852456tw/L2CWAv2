"""
db_service.py
Gate 2: SQLite 資料庫寫入與 Upsert 查詢服務
"""
import os
import sqlite3
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# ── 資料庫路徑 ───────────────────────────────────────────────────────────────
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH   = os.path.join(_BASE_DIR, "data", "weather.db")


# ── DDL 建立資料表 ────────────────────────────────────────────────────────────
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS realtime_weather (
    station_id        TEXT    PRIMARY KEY,
    station_name      TEXT    NOT NULL,
    latitude          REAL    NOT NULL,
    longitude         REAL    NOT NULL,
    air_temperature   REAL    NOT NULL,
    obs_time          TEXT    NOT NULL,
    fetched_at        TEXT    NOT NULL,
    updated_at        TEXT    NOT NULL
);
"""

CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_obs_time ON realtime_weather (obs_time);
"""

# 煥哥課程環節 9：一週預報資料庫設計
CREATE_FORECAST_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS TemperatureForecasts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    regionName  TEXT    NOT NULL,
    dataDate    TEXT    NOT NULL,
    minT        REAL    NOT NULL,
    maxT        REAL    NOT NULL,
    updated_at  TEXT    NOT NULL,
    UNIQUE(regionName, dataDate)
);
"""

CREATE_FORECAST_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_forecast_region ON TemperatureForecasts (regionName);
CREATE INDEX IF NOT EXISTS idx_forecast_date ON TemperatureForecasts (dataDate);
"""


# ── 連線與初始化 ─────────────────────────────────────────────────────────────
def get_connection() -> sqlite3.Connection:
    """建立並回傳 SQLite 連線，同時確保 data/ 目錄存在。"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """建立資料表與索引，並確保擴充欄位已存在。"""
    with get_connection() as conn:
        conn.execute(CREATE_TABLE_SQL)
        conn.execute(CREATE_INDEX_SQL)
        conn.execute(CREATE_FORECAST_TABLE_SQL)
        conn.executescript(CREATE_FORECAST_INDEX_SQL)

        # 動態補足 realtime_weather 擴充欄位（風速、風向、濕度、雨量、天氣描述）
        existing_cols = {row["name"] for row in conn.execute("PRAGMA table_info(realtime_weather)").fetchall()}
        new_cols = {
            "wind_speed": "REAL DEFAULT 0.0",
            "wind_direction": "REAL DEFAULT 0.0",
            "relative_humidity": "REAL DEFAULT 0.0",
            "precipitation": "REAL DEFAULT 0.0",
            "weather_desc": "TEXT DEFAULT ''"
        }
        for col_name, col_type in new_cols.items():
            if col_name not in existing_cols:
                try:
                    conn.execute(f"ALTER TABLE realtime_weather ADD COLUMN {col_name} {col_type};")
                except Exception:
                    pass

        conn.commit()
    logger.info(f"[DB] 資料庫初始化完成: {DB_PATH}")


# ── Upsert 寫入 ──────────────────────────────────────────────────────────────
UPSERT_SQL = """
INSERT INTO realtime_weather
    (station_id, station_name, latitude, longitude,
     air_temperature, obs_time, fetched_at, updated_at,
     wind_speed, wind_direction, relative_humidity, precipitation, weather_desc)
VALUES
    (:station_id, :station_name, :latitude, :longitude,
     :air_temperature, :obs_time, :fetched_at, :updated_at,
     :wind_speed, :wind_direction, :relative_humidity, :precipitation, :weather_desc)
ON CONFLICT(station_id) DO UPDATE SET
    station_name      = excluded.station_name,
    latitude          = excluded.latitude,
    longitude         = excluded.longitude,
    air_temperature   = excluded.air_temperature,
    obs_time          = excluded.obs_time,
    fetched_at        = excluded.fetched_at,
    updated_at        = excluded.updated_at,
    wind_speed        = excluded.wind_speed,
    wind_direction    = excluded.wind_direction,
    relative_humidity = excluded.relative_humidity,
    precipitation     = excluded.precipitation,
    weather_desc      = excluded.weather_desc;
"""


def upsert_records(records: list) -> int:
    """
    批量 Upsert 測站天氣記錄（不重複插入）。
    """
    now = datetime.utcnow().isoformat() + "Z"
    rows = []
    for r in records:
        rows.append({
            "station_id":        r.get("station_id"),
            "station_name":      r.get("station_name"),
            "latitude":          r.get("latitude"),
            "longitude":         r.get("longitude"),
            "air_temperature":   r.get("air_temperature"),
            "obs_time":          r.get("obs_time"),
            "fetched_at":        r.get("fetched_at", now),
            "updated_at":        now,
            "wind_speed":        r.get("wind_speed", 0.0),
            "wind_direction":    r.get("wind_direction", 0.0),
            "relative_humidity": r.get("relative_humidity", 0.0),
            "precipitation":     r.get("precipitation", 0.0),
            "weather_desc":      r.get("weather_desc", ""),
        })

    with get_connection() as conn:
        conn.executemany(UPSERT_SQL, rows)
        conn.commit()

    logger.info(f"[DB] Upsert 完成，寫入 {len(rows)} 筆")
    return len(rows)


# 煥哥課程環節 8 & 9：一週預報資料庫寫入 (重複執行不重複插入)
UPSERT_FORECAST_SQL = """
INSERT INTO TemperatureForecasts
    (regionName, dataDate, minT, maxT, updated_at)
VALUES
    (:region_name, :data_date, :min_t, :max_t, :updated_at)
ON CONFLICT(regionName, dataDate) DO UPDATE SET
    minT       = excluded.minT,
    maxT       = excluded.maxT,
    updated_at = excluded.updated_at;
"""


def upsert_forecast_records(records: list) -> int:
    """
    批量 Upsert 一週氣溫預報記錄（防重複插入）。
    """
    now = datetime.utcnow().isoformat() + "Z"
    rows = [{**r, "updated_at": now} for r in records]

    with get_connection() as conn:
        conn.executemany(UPSERT_FORECAST_SQL, rows)
        conn.commit()

    logger.info(f"[DB] Forecast Upsert 完成，寫入 {len(rows)} 筆")
    return len(rows)


# ── 查詢 ─────────────────────────────────────────────────────────────────────
def get_all_stations() -> list:
    """取得全部有效測站資料（供 Streamlit 地圖使用）。"""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM realtime_weather ORDER BY station_name"
        ).fetchall()
    return [dict(r) for r in rows]


def get_station_count() -> int:
    """回傳資料庫中的測站筆數。"""
    with get_connection() as conn:
        result = conn.execute("SELECT COUNT(*) FROM realtime_weather").fetchone()
    return result[0]


def get_temp_distribution() -> dict:
    """取得溫度分布統計。"""
    with get_connection() as conn:
        row = conn.execute("""
            SELECT
                COUNT(CASE WHEN air_temperature >= 30 THEN 1 END) AS hot,
                COUNT(CASE WHEN air_temperature >= 20 AND air_temperature < 30 THEN 1 END) AS warm,
                COUNT(CASE WHEN air_temperature < 20 THEN 1 END) AS cool,
                MIN(air_temperature)  AS min_temp,
                MAX(air_temperature)  AS max_temp,
                ROUND(AVG(air_temperature), 1) AS avg_temp
            FROM realtime_weather
        """).fetchone()
    return dict(row) if row else {}


# 煥哥課程環節 10, 12, 13, 18 預報查詢服務
def get_forecast_regions() -> list:
    """
    取得所有預報地區清單（排序：6 大主要分區優先，其後為縣市）。
    符合 SQL: SELECT DISTINCT regionName FROM TemperatureForecasts;
    """
    with get_connection() as conn:
        rows = conn.execute("SELECT DISTINCT regionName FROM TemperatureForecasts").fetchall()
    all_regs = [r[0] for r in rows]
    priority = ["北部地區", "中部地區", "南部地區", "東北部地區", "東部地區", "東南部地區", "離島地區"]
    sorted_regs = [p for p in priority if p in all_regs] + [r for r in all_regs if r not in priority]
    return sorted_regs


def get_forecast_dates() -> list:
    """取得預報涵蓋的日期清單 (供 Select Date 使用)。"""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT dataDate FROM TemperatureForecasts ORDER BY dataDate ASC"
        ).fetchall()
    return [r[0] for r in rows]


def get_forecast_by_region(region_name: str) -> list:
    """
    依地區名稱查詢一週氣溫預報（供折線圖與表格使用）。
    符合 SQL: SELECT * FROM TemperatureForecasts WHERE regionName = "中部地區";
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM TemperatureForecasts WHERE regionName = ? ORDER BY dataDate ASC",
            (region_name,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_forecast_by_date(data_date: str) -> list:
    """依日期查詢全台各地區預報（供日期地圖視覺化使用）。"""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM TemperatureForecasts WHERE dataDate = ? ORDER BY regionName ASC",
            (data_date,)
        ).fetchall()
    return [dict(r) for r in rows]


# ── 獨立執行驗證 ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    init_db()
    count = get_station_count()
    dist  = get_temp_distribution()
    print(f"Total stations in DB: {count}")
    print(f"Temperature distribution: {dist}")
    print(f"Forecast regions: {get_forecast_regions()}")
