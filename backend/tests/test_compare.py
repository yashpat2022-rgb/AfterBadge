"""Tests for side-by-side comparisons using a temporary in-memory database."""
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Complaint, Recall, Vehicle
from app.service import compare_vehicles


def build_test_database():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        left = Vehicle(make="ACURA", model="RDX", year=2012)
        right = Vehicle(make="ACURA", model="RDX", year=2021)
        db.add_all((left, right))
        db.flush()
        db.add_all([
            Complaint(vehicle_id=left.id, odi_number="1", components="STEERING,POWER TRAIN", summary="Sample A"),
            Complaint(vehicle_id=left.id, odi_number="2", components="STEERING", summary="Sample B"),
            Complaint(vehicle_id=right.id, odi_number="3", components="POWER TRAIN,ELECTRICAL SYSTEM", summary="Sample C"),
            Recall(vehicle_id=left.id, campaign_number="24V111000", component="AIR BAGS"),
        ])
        db.commit()
        return engine, left.id, right.id


def test_comparison_counts_and_category_order():
    engine, left_id, right_id = build_test_database()
    try:
        with Session(engine) as db:
            result = compare_vehicles(db, db.get(Vehicle, left_id), db.get(Vehicle, right_id))
        assert result["left"]["complaint_count"] == 2
        assert result["right"]["complaint_count"] == 1
        assert result["left"]["recall_count"] == 1
        assert result["right"]["recall_count"] == 0
        assert result["component_comparison"] == [
            {"name": "POWER TRAIN", "left_count": 1, "right_count": 1},
            {"name": "STEERING", "left_count": 2, "right_count": 0},
            {"name": "ELECTRICAL SYSTEM", "left_count": 0, "right_count": 1},
        ]
    finally:
        engine.dispose()


def test_compare_api_success_and_errors():
    engine, left_id, right_id = build_test_database()

    def test_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = test_db
    try:
        client = TestClient(app)
        response = client.get("/api/compare", params={"left_id": left_id, "right_id": right_id})
        assert response.status_code == 200
        assert response.json()["right"]["year"] == 2021

        same = client.get("/api/compare", params={"left_id": left_id, "right_id": left_id})
        assert same.status_code == 400

        missing = client.get("/api/compare", params={"left_id": left_id, "right_id": 9999})
        assert missing.status_code == 404
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
