from fastapi import FastAPI
from fastf1.events import get_event_schedule
from fastf1.events import get_session

app = FastAPI()

# Hard-coded years for dropdown
@app.get("/years")
def years():
    return [2023, 2024, 2025, 2026]

# Get rounds (meetings) for a given year
@app.get("/rounds")
def rounds(year: int):
    try:
        schedule = get_event_schedule(year)
        return [{"round_name": e.name, "round_date": str(e.date)} for e in schedule]
    except Exception as e:
        return {"error": "Failed to fetch rounds", "details": str(e)}

# Get sessions for a given round in a year
@app.get("/sessions")
def sessions(year: int, round_name: str):
    try:
        schedule = get_event_schedule(year)
        meeting = next((e for e in schedule if e.name == round_name), None)
        if not meeting:
            return {"error": "Round not found"}
        return [{"session_name": s.name, "session_datetime": str(s.date)} for s in meeting.sessions]
    except Exception as e:
        return {"error": "Failed to fetch sessions", "details": str(e)}

# Get results for a specific session
@app.get("/session_results")
def session_results(year: int, round_name: str, session_name: str):
    try:
        schedule = get_event_schedule(year)
        meeting = next((e for e in schedule if e.name == round_name), None)
        if not meeting:
            return {"error": "Round not found"}

        session_obj = next((s for s in meeting.sessions if s.name == session_name), None)
        if not session_obj:
            return {"error": "Session not found"}

        # Load the session results
        session = get_session(year, meeting.name, session_obj.name)
        session.load()  # Downloads timing/results if needed
        results = session.results
        return [
            {
                "position": r.Position,
                "driver": r['Driver'],
                "team": r['Team'],
                "laps": r['Laps'],
                "time": str(r['Time']),
                "status": r['Status']
            } for r in results.itertuples()
        ]
    except Exception as e:
        return {"error": "Failed to fetch session results", "details": str(e)}
