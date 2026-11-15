"""Run these from backend/: python -m pytest -q"""
import asyncio
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from app.database import Base
from app import service
from app.models import Vehicle, Complaint, Recall


def test_component_normalization():
    assert service.component_names("STEERING, POWER TRAIN, STEERING") == ["POWER TRAIN", "STEERING"]
    assert service.component_names("") == ["UNKNOWN"]
    assert service.normalize_name("  bmw   ") == "BMW"


def test_sync_is_idempotent(monkeypatch):
    async def fake_fetch(make, model, year):
        assert (make, model, year) == ("ACURA", "RDX", 2012)
        return (
            [{"odiNumber": 123, "components": "STEERING, POWER TRAIN", "summary": "Vibration", "dateComplaintFiled": "01/02/2020"}],
            [{"NHTSACampaignNumber": "20V123000", "Component": "AIR BAGS", "Summary": "Recall details", "Consequence": "Risk", "Remedy": "Repair"}],
        )

    monkeypatch.setattr(service, "fetch_vehicle_data", fake_fetch)
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        asyncio.run(service.sync_vehicle(db, " acura ", "rdx", 2012))
        asyncio.run(service.sync_vehicle(db, "ACURA", "RDX", 2012))
        assert len(db.scalars(select(Vehicle)).all()) == 1
        assert len(db.scalars(select(Complaint)).all()) == 1
        assert len(db.scalars(select(Recall)).all()) == 1
        result = service.vehicle_details(db, db.scalar(select(Vehicle)))
        assert result["top_components"] == [
            {"name": "POWER TRAIN", "count": 1},
            {"name": "STEERING", "count": 1},
        ]
