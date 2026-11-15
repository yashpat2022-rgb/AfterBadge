"""AfterBadge API. Run with uvicorn app.main:app --reload."""
import os
from contextlib import asynccontextmanager
import httpx
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session
from .database import get_db, init_database
from .models import Vehicle
from .service import sync_vehicle, vehicle_details, compare_vehicles

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_database()
    yield

app = FastAPI(title="AfterBadge API", version="0.3.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health():
    return {"status": "ok"}

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
    year: int = Query(ge=1950, le=2035),
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
