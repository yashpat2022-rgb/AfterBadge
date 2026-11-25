"""AfterBadge API. Run with uvicorn app.main:app --reload."""
import os
from contextlib import asynccontextmanager
from datetime import date
import httpx
from threading import Lock
from fastapi import Depends, FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session
from .database import get_db, init_database
from .models import Vehicle, Complaint
from .service import sync_vehicle, vehicle_details, compare_vehicles
from .nhtsa import fetch_vehicle_options
from app.ai_classifier import classify_complaint

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_database()
    yield

app = FastAPI(title="AfterBadge API", version="0.3.0", lifespan=lifespan)

# Limit Gemini requests during local development
AI_REQUEST_LIMIT = 10
MIN_MODEL_YEAR = 1949
MAX_MODEL_YEAR = 2035
ai_request_count = {"used": 0}
ai_request_lock = Lock()
# Store previous AI analysis results
ai_result_cache = {}


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.get("/api/vehicle-options")
async def vehicle_options(
    response: Response,
    year: int | None = Query(default=None, ge=MIN_MODEL_YEAR, le=MAX_MODEL_YEAR),
    make: str | None = Query(default=None, min_length=1, max_length=80),
):
    if year is None:
        if make is not None:
            raise HTTPException(422, "Choose a model year first.")
        # NHTSA's model-years endpoint can return a short list of older years.
        latest = min(date.today().year + 1, MAX_MODEL_YEAR)
        return {"options": [str(value) for value in range(latest, MIN_MODEL_YEAR - 1, -1)]}

    try:
        options, incomplete = await fetch_vehicle_options(year, make)
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(502, "Could not load vehicle options. Try again.") from exc
    if not incomplete:
        response.headers["Cache-Control"] = "private, max-age=300"
    return {"options": options, "incomplete": incomplete}


@app.get("/api/vehicles")
def vehicles(db: Session = Depends(get_db)):
    rows = db.scalars(select(Vehicle).order_by(Vehicle.year.desc(), Vehicle.make, Vehicle.model)).all()
    return [{"id": v.id, "make": v.make, "model": v.model, "year": v.year} for v in rows]

@app.get("/api/vehicles/{vehicle_id}")
def details(vehicle_id: int, db: Session = Depends(get_db)):
    vehicle = db.get(Vehicle, vehicle_id)
    if vehicle is None:
        raise HTTPException(404, "Vehicle not found. Sync it first.")
    return vehicle_details(db, vehicle)

@app.get("/api/compare")
def compare(
    left_id: int = Query(ge=1),
    right_id: int = Query(ge=1),
    db: Session = Depends(get_db),
):
    """Compare two previously imported vehicles without refetching NHTSA data."""
    if left_id == right_id:
        raise HTTPException(400, "Choose two different vehicles to compare.")
    left, right = db.get(Vehicle, left_id), db.get(Vehicle, right_id)
    if left is None or right is None:
        raise HTTPException(404, "One or both vehicles were not found. Import them first.")
    return compare_vehicles(db, left, right)


@app.post("/api/vehicles/sync")
async def sync(
    make: str = Query(min_length=1, max_length=80),
    model: str = Query(min_length=1, max_length=100),
    year: int = Query(ge=MIN_MODEL_YEAR, le=MAX_MODEL_YEAR),
    db: Session = Depends(get_db),
):
    # This endpoint is intended for localhost development only, NOT a public deployment.
    if os.getenv("AUTOINSIGHT_ENABLE_SYNC", "true").lower() != "true":
        raise HTTPException(403, "Interactive data syncing is disabled")
    try:
        vehicle = await sync_vehicle(db, make, model, year)
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(502, "NHTSA data could not be retrieved. Try again later.") from exc
    return vehicle_details(db, vehicle)



@app.post("/api/complaints/{odi_number}/analyze")
def analyze_complaint(
    odi_number: str,
    db: Session = Depends(get_db),
):
    # AI requests must be explicitly enabled
    if os.getenv("AFTERBADGE_ENABLE_AI", "false").lower() != "true":
        raise HTTPException(403, "AI analysis is disabled.")

    # Find the complaint in our database
    complaint = db.scalar(
        select(Complaint).where(Complaint.odi_number == odi_number)
    )

    if complaint is None:
        raise HTTPException(404, "Complaint not found.")

    # Don't send empty complaints to Gemini
    if not complaint.summary or not complaint.summary.strip():
        return {"odi_number": odi_number, "issues": []}

    # Check whether this complaint was already analyzed
    with ai_request_lock:
        cached_issues = ai_result_cache.get(odi_number)

    if cached_issues is not None:
        return {
            "odi_number": odi_number,
            "issues": cached_issues
        }

    # Limit Gemini API requests
    with ai_request_lock:
        if ai_request_count["used"] >= AI_REQUEST_LIMIT:
            raise HTTPException(
                status_code=429,
                detail="AI request limit reached. Restart the backend to reset."
            )

        ai_request_count["used"] += 1

    # Ask Gemini to analyze the complaint
    try:
        result = classify_complaint(complaint.summary)
    except Exception as exc:
        raise HTTPException(
            502, "AI classification failed. Please try again later."
        ) from exc

    # Save successful Gemini results for future requests
    with ai_request_lock:
        ai_result_cache[odi_number] = result["issues"]

    return {
        "odi_number": odi_number,
        "issues": result["issues"],
    }
