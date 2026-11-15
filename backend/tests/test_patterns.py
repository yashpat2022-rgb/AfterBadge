"""Tests are deterministic and do not require network access."""
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Complaint, Vehicle
from app.patterns import group_complaints, matched_phrases
from app.service import vehicle_details


def test_detects_specific_phrases_not_just_component():
    found = matched_phrases("While driving, the engine stalled and the brake pedal went to the floor.")
    assert found["engine_stall"].lower() == "engine stalled"
    assert "braking" in found
    assert "steering" not in found
    assert matched_phrases("Routine inspection of engine, steering and brakes") == {}
    assert matched_phrases(None) == {}


def test_case_insensitive_and_no_substring_false_match():
    assert "airbag" in matched_phrases("The AIRBAG FAILED TO DEPLOY during a crash.")
    assert "transmission" in matched_phrases("Experienced a HARD SHIFT on the highway")
    assert matched_phrases("engineering review and shifting schedule") == {}


def test_groups_one_complaint_once_per_pattern_and_links_source():
    complaints = [
        Complaint(odi_number="1001", summary="Engine stalled. Engine stalled again.", components="ENGINE"),
        Complaint(odi_number="1002", summary="engine stalled while driving; power steering failed", components="ENGINE,STEERING"),
        Complaint(odi_number="1003", summary="Unrelated trim issue", components="UNKNOWN"),
    ]
    groups = group_complaints(complaints)
    engine = next(p for p in groups if p["key"] == "engine_stall")
    assert engine["count"] == 2
    assert engine["odi_numbers"] == ["1001", "1002"]
    assert "odinumber=1001" in engine["examples"][0]["source_url"]
    assert engine["examples"][0]["matched_phrase"] == "Engine stalled"
    assert next(p for p in groups if p["key"] == "steering")["count"] == 1


def test_vehicle_details_includes_patterns_from_saved_records():
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            car = Vehicle(make="ACURA", model="RDX", year=2012)
            db.add(car)
            db.flush()
            db.add(Complaint(vehicle_id=car.id, odi_number="101", summary="The engine stalled while merging", components="ENGINE"))
            db.commit()
            result = vehicle_details(db, car)
        assert result["problem_patterns"][0]["key"] == "engine_stall"
        assert result["problem_patterns"][0]["odi_numbers"] == ["101"]
    finally:
        engine.dispose()


def test_api_returns_pattern_evidence_from_existing_database():
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        car = Vehicle(make="BMW", model="330I", year=2022)
        db.add(car)
        db.flush()
        car_id = car.id
        db.add(Complaint(vehicle_id=car_id, odi_number="54321", summary="The airbag did not deploy", components="AIR BAGS"))
        db.commit()

    def test_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = test_db
    try:
        result = TestClient(app).get(f"/api/vehicles/{car_id}")
        assert result.status_code == 200
        body = result.json()
        assert body["problem_patterns"][0]["key"] == "airbag"
        assert body["problem_patterns"][0]["count"] == 1
        assert body["problem_patterns"][0]["examples"][0]["odi_number"] == "54321"
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
