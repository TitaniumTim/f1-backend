from fastapi import FastAPI
from fastf1.events import get_event_schedule
import fastf1

app = FastAPI()

# Enable FastF1 cache (VERY important for Render)
fastf1.Cache.enable_cache("/tmp")

# Hard-coded years for dropdown
@app.get("/years")
def years():
    return [2023, 2024, 2025, 2026]


# Get rounds (race weekends) for a given year
@app.get("/rounds")
def rounds(year: int):
    try:
        schedule = get_event_schedule(year)

        rounds_list = []
        for _, row in schedule.iterrows():
            rounds_list.append({
                "round": int(row["RoundNumber"]),
                "round_name": row["EventName"],
                "country": row["Country"],
                "location": row["Location"],
                "event_date": str(row["EventDate"])
            })

        return rounds_list

    except Exception as e:
        return {"error": "Failed to fetch rounds", "details": str(e)}


# Get sessions for a given round
@app.get("/sessions")
def sessions(year: int, round: int):
    try:
        schedule = get_event_schedule(year)

        event = schedule[schedule["RoundNumber"] == round]

        if event.empty:
            return {"error": "Round not found"}

        event = event.iloc[0]

        sessions_list = []

        for session_name in ["Session1", "Session2", "Session3", "Session4", "Session5"]:
            if session_name in event and event[session_name]:
                sessions_list.append({
                    "session_name": event[session_name]
                })

        return sessions_list

    except Exception as e:
        return {"error": "Failed to fetch sessions", "details": str(e)}


# Get results for a specific session
@app.get("/session_results")
def session_results(year: int, round: int, session: str):
    try:
        session_obj = fastf1.get_session(year, round, session)
        session_obj.load()

        results = session_obj.results

        return [
            {
                "position": int(row.Position) if row.Position else None,
                "driver": row.FullName,
                "team": row.TeamName,
                "laps": row.Laps,
                "status": row.Status
            }
            for _, row in results.iterrows()
        ]

    except Exception as e:
        return {"error": "Failed to fetch session results", "details": str(e)}
