from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

import fastf1
from diskcache import Cache
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastf1.events import get_event_schedule

app = FastAPI(title="F1 Top 10 Backend")

CACHE_DIR = Path("/tmp/fastf1_cache")
API_CACHE_DIR = Path("/tmp/f1_api_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
API_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# FastF1 cache avoids repeated API calls and significantly improves warm response times.
fastf1.Cache.enable_cache(str(CACHE_DIR))
api_cache = Cache(str(API_CACHE_DIR))

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@lru_cache(maxsize=16)
def get_schedule(year: int):
    return get_event_schedule(year)


def parse_team_color(team_color: Any) -> str | None:
    if not team_color:
        return None
    team_color = str(team_color).strip().lstrip("#")
    return f"#{team_color}" if team_color else None


def normalize_number(value: Any) -> str | None:
    if value is None:
        return None
    as_text = str(value).strip()
    return as_text if as_text else None


@app.get("/health")
def health():
    return {
        "status": "ok",
        "fastf1_cache": str(CACHE_DIR),
        "api_cache_items": len(api_cache),
        "timestamp_utc": datetime.utcnow().isoformat() + "Z",
    }


@app.get("/years")
def years():
    now = datetime.utcnow().year
    return list(range(2023, now + 1))


@app.get("/rounds")
def rounds(year: int):
    try:
        schedule = get_schedule(year)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail={"error": "Failed to fetch rounds", "details": str(exc)},
        ) from exc

    rounds_list = []
    for _, row in schedule.iterrows():
        rounds_list.append(
            {
                "round": int(row["RoundNumber"]),
                "round_name": row["EventName"],
                "country": row["Country"],
                "location": row["Location"],
                "event_date": str(row["EventDate"]),
            }
        )

    return rounds_list


@app.get("/sessions")
def sessions(year: int, round: int):
    try:
        schedule = get_schedule(year)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail={"error": "Failed to fetch sessions", "details": str(exc)},
        ) from exc

    event = schedule[schedule["RoundNumber"] == round]
    if event.empty:
        raise HTTPException(status_code=404, detail={"error": "Round not found"})

    event = event.iloc[0]
    sessions_list = []
    seen_sessions = set()

    for idx in range(1, 6):
        session_name_key = f"Session{idx}"
        session_date_key = f"Session{idx}Date"
        session_name = event.get(session_name_key)
        session_date = event.get(session_date_key)

        if pd.isna(session_name) or not str(session_name).strip():
            continue

        # Skip sessions that were not scheduled/confirmed in the event data.
        if pd.isna(session_date):
            continue

        normalized_name = str(session_name).strip()
        normalized_date = pd.Timestamp(session_date).isoformat()
        dedupe_key = (normalized_name.lower(), normalized_date)
        if dedupe_key in seen_sessions:
            continue

        seen_sessions.add(dedupe_key)
        sessions_list.append(
            {
                "session_name": normalized_name,
                "session_date": normalized_date,
            }
        )

    return sessions_list


@api_cache.memoize(expire=3600)
def _load_session_results(year: int, round: int, session: str):
    session_obj = fastf1.get_session(year, round, session)
    # Keep this lightweight; we only need timing/results table for the game setup.
    session_obj.load(laps=False, telemetry=False, weather=False, messages=False)

    results = session_obj.results
    return [
        {
            "position": int(row.Position) if row.Position else None,
            "driver": row.FullName,
            "driver_number": normalize_number(row.get("DriverNumber")),
            "driver_code": row.get("Abbreviation"),
            "team": row.TeamName,
            "team_color": parse_team_color(row.get("TeamColor")),
            "laps": int(row.Laps) if row.Laps else None,
            "status": row.Status,
            "grid_position": int(row.GridPosition) if row.GridPosition else None,
            "points": float(row.Points) if row.Points is not None else None,
        }
        for _, row in results.iterrows()
    ]


@app.get("/session_results")
def session_results(year: int, round: int, session: str):
    try:
        return _load_session_results(year, round, session)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail={"error": "Failed to fetch session results", "details": str(exc)},
        ) from exc


@api_cache.memoize(expire=86400)
def _load_circuit_map(year: int, round: int, session: str):
    session_obj = fastf1.get_session(year, round, session)
    session_obj.load(laps=True, telemetry=False, weather=False, messages=False)

    lap = session_obj.laps.pick_fastest()
    if lap is None:
        raise ValueError("No lap data found for this session")

    pos_data = lap.get_pos_data()[["X", "Y"]]
    track_points = [
        {"x": float(point.X), "y": float(point.Y)} for _, point in pos_data.iterrows()
    ]

    circuit_info = session_obj.get_circuit_info()
    corners_df = circuit_info.corners
    corners = []
    if corners_df is not None and not corners_df.empty:
        corners = [
            {
                "number": normalize_number(corner.get("Number")),
                "letter": corner.get("Letter"),
                "angle": float(corner.get("Angle")) if corner.get("Angle") else None,
                "x": float(corner.get("X")),
                "y": float(corner.get("Y")),
            }
            for _, corner in corners_df.iterrows()
        ]

    return {
        "event_name": session_obj.event["EventName"],
        "session_name": session_obj.name,
        "rotation": float(circuit_info.rotation),
        "track_points": track_points,
        "corners": corners,
    }


@app.get("/circuit_map")
def circuit_map(year: int, round: int, session: str = "R"):
    try:
        return _load_circuit_map(year, round, session)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail={"error": "Failed to fetch circuit map", "details": str(exc)},
        ) from exc
