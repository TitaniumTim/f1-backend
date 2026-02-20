from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import fastf1
from fastf1.core import get_event_schedule
import pandas as pd

app = FastAPI()

# Allow CORS for your Vercel frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cache FastF1 data to speed up repeated requests
fastf1.Cache.enable_cache('f1_cache')

# 1. Years endpoint
@app.get("/years")
def get_years():
    return {"years": [2023, 2024, 2025, 2026]}

# 2. Rounds endpoint
@app.get("/rounds")
def get_rounds(year: int):
    try:
        schedule = fastf1.get_event_schedule(year)
        rounds = []
        for _, row in schedule.iterrows():
            rounds.append({
                "round": int(row['RoundNumber']),
                "name": row['EventName'],
                "meeting_key": row['EventName'].replace(" ", "_").lower()  # simple key
            })
        return {"rounds": rounds}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 3. Sessions endpoint
@app.get("/sessions")
def get_sessions(year: int, round_number: int):
    try:
        schedule = fastf1.get_event_schedule(year)
        event_row = schedule[schedule['RoundNumber'] == round_number]
        if event_row.empty:
            raise HTTPException(status_code=404, detail="Round not found")
        event = fastf1.get_event(year, round_number)
        sessions = []
        for session in ['FP1', 'FP2', 'FP3', 'Qualifying', 'Race']:
            if session in event.sessions:
                sess = event.get_session(session)
                sessions.append({
                    "name": session,
                    "session_key": f"{year}_{round_number}_{session.lower()}"
                })
        return {"sessions": sessions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 4. Session results endpoint
@app.get("/session_results")
def get_session_results(year: int, round_number: int, session_name: str):
    try:
        event = fastf1.get_event(year, round_number)
        session = event.get_session(session_name)
        session.load()  # Load session telemetry + results
        results = session.results
        participants = []
        for idx, row in results.iterrows():
            participants.append({
                "position": int(row['Position']) if not pd.isna(row['Position']) else None,
                "driver": str(row['Driver']),
                "team": str(row['Team']),
                "laps": int(row['Laps']) if not pd.isna(row['Laps']) else None,
                "time": str(row['Time']) if 'Time' in row else None
            })
        return {"participants": participants}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
