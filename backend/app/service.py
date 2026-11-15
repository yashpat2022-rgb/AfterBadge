"""Transform NHTSA payloads and load them idempotently into SQL."""
from collections import Counter
from datetime import datetime, timezone
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from .models import Vehicle, Complaint, Recall
from .nhtsa import fetch_vehicle_data
from .patterns import group_complaints


def normalize_name(value: str) -> str:
    return " ".join(value.upper().split())


def component_names(raw: str | None) -> list[str]:
    """A complaint can mention multiple NHTSA components (e.g. 'STEERING,POWER TRAIN')."""
    if not raw or not raw.strip():
        return ["UNKNOWN"]
    return sorted(set(piece.strip().upper() for piece in raw.split(",") if piece.strip())) or ["UNKNOWN"]


async def sync_vehicle(db: Session, make: str, model: str, year: int) -> Vehicle:
    make, model = normalize_name(make), normalize_name(model)
    # Fetch both first. If either request fails, the database remains unchanged.
    complaints_raw, recalls_raw = await fetch_vehicle_data(make, model, year)
    vehicle = db.scalar(select(Vehicle).where(Vehicle.make == make, Vehicle.model == model, Vehicle.year == year))
    if vehicle is None:
        vehicle = Vehicle(make=make, model=model, year=year)
        db.add(vehicle)
        db.flush()

    complaints_by_id = {item.odi_number: item for item in db.scalars(select(Complaint).where(Complaint.vehicle_id == vehicle.id))}
    recalls_by_id = {item.campaign_number: item for item in db.scalars(select(Recall).where(Recall.vehicle_id == vehicle.id))}

    for record in complaints_raw:
        odi = record.get("odiNumber")
        if odi is None:
            continue  # no stable identifier -> don't invent one
        odi = str(odi)
        item = complaints_by_id.get(odi)
        if item is None:
            item = Complaint(vehicle_id=vehicle.id, odi_number=odi)
            db.add(item)
            complaints_by_id[odi] = item
        item.components = ",".join(component_names(record.get("components")))
        item.summary = str(record.get("summary") or "")
        item.date_filed = str(record.get("dateComplaintFiled") or "")

    for record in recalls_raw:
        campaign = record.get("NHTSACampaignNumber")
        if not campaign:
            continue
        campaign = str(campaign)
        item = recalls_by_id.get(campaign)
        if item is None:
            item = Recall(vehicle_id=vehicle.id, campaign_number=campaign)
            db.add(item)
            recalls_by_id[campaign] = item
        item.component = str(record.get("Component") or "")
        item.summary = str(record.get("Summary") or "")
        item.consequence = str(record.get("Consequence") or "")
        item.remedy = str(record.get("Remedy") or "")

    vehicle.last_synced_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(vehicle)
    return vehicle


def vehicle_details(db: Session, vehicle: Vehicle) -> dict:
    complaints = list(db.scalars(select(Complaint).where(Complaint.vehicle_id == vehicle.id).order_by(Complaint.id.desc())))
    recalls = list(db.scalars(select(Recall).where(Recall.vehicle_id == vehicle.id).order_by(Recall.id.desc())))
    count = Counter(component for complaint in complaints for component in component_names(complaint.components))
    return {
        "id": vehicle.id,
        "make": vehicle.make,
        "model": vehicle.model,
        "year": vehicle.year,
        "last_synced_at": vehicle.last_synced_at.isoformat() if vehicle.last_synced_at else None,
        "complaint_count": len(complaints),
        "recall_count": len(recalls),
        "top_components": [{"name": name, "count": total} for name, total in count.most_common()],
        "problem_patterns": group_complaints(complaints),
        "complaints": [
            {
                "odi_number": item.odi_number,
                "components": component_names(item.components),
                "summary": item.summary,
                "date_filed": item.date_filed,
                "source_url": f"https://api.nhtsa.gov/complaints/odinumber?odinumber={item.odi_number}",
            }
            for item in complaints
        ],
        "recalls": [
            {
                "campaign_number": item.campaign_number,
                "component": item.component,
                "summary": item.summary,
                "consequence": item.consequence,
                "remedy": item.remedy,
                "source_url": f"https://api.nhtsa.gov/recalls/campaignNumber?campaignNumber={item.campaign_number}",
            }
            for item in recalls
        ],
    }


def compare_vehicles(db: Session, left: Vehicle, right: Vehicle) -> dict:
    """Build a lightweight, source-backed comparison from data already stored in SQL.

    Component counts are mentions in submitted complaints, NOT failure rates.
    Each complaint counts once per component, even if it lists several components.
    """
    ids = (left.id, right.id)
    complaint_rows = db.execute(
        select(Complaint.vehicle_id, Complaint.components).where(Complaint.vehicle_id.in_(ids))
    ).all()
    recall_rows = db.execute(
        select(Recall.vehicle_id, func.count(Recall.id))
        .where(Recall.vehicle_id.in_(ids))
        .group_by(Recall.vehicle_id)
    ).all()

    complaint_totals = Counter()
    component_counts = {left.id: Counter(), right.id: Counter()}
    recall_totals = dict(recall_rows)
    for vehicle_id, components in complaint_rows:
        complaint_totals[vehicle_id] += 1
        component_counts[vehicle_id].update(component_names(components))

    all_components = component_counts[left.id].keys() | component_counts[right.id].keys()
    component_comparison = [
        {
            "name": name,
            "left_count": component_counts[left.id][name],
            "right_count": component_counts[right.id][name],
        }
        for name in sorted(
            all_components,
            key=lambda name: (
                -(component_counts[left.id][name] + component_counts[right.id][name]), name
            ),
        )
    ]

    def summary(vehicle: Vehicle) -> dict:
        return {
            "id": vehicle.id,
            "make": vehicle.make,
            "model": vehicle.model,
            "year": vehicle.year,
            "complaint_count": complaint_totals[vehicle.id],
            "recall_count": recall_totals.get(vehicle.id, 0),
            "last_synced_at": vehicle.last_synced_at.isoformat() if vehicle.last_synced_at else None,
        }

    return {
        "left": summary(left),
        "right": summary(right),
        "component_comparison": component_comparison,
    }
