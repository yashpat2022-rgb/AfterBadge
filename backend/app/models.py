"""Relational tables for vehicles and source-backed records."""
from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base

class Vehicle(Base):
    __tablename__ = "vehicles"
    __table_args__ = (UniqueConstraint("make", "model", "year"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    make: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    complaints: Mapped[list["Complaint"]] = relationship(back_populates="vehicle", cascade="all, delete-orphan")
    recalls: Mapped[list["Recall"]] = relationship(back_populates="vehicle", cascade="all, delete-orphan")

class Complaint(Base):
    __tablename__ = "complaints"
    __table_args__ = (UniqueConstraint("vehicle_id", "odi_number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), nullable=False, index=True)
    odi_number: Mapped[str] = mapped_column(String(30), nullable=False)
    components: Mapped[str] = mapped_column(Text, nullable=False, default="UNKNOWN")
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    date_filed: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    vehicle: Mapped[Vehicle] = relationship(back_populates="complaints")

class Recall(Base):
    __tablename__ = "recalls"
    __table_args__ = (UniqueConstraint("vehicle_id", "campaign_number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), nullable=False, index=True)
    campaign_number: Mapped[str] = mapped_column(String(30), nullable=False)
    component: Mapped[str] = mapped_column(Text, nullable=False, default="")
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    consequence: Mapped[str] = mapped_column(Text, nullable=False, default="")
    remedy: Mapped[str] = mapped_column(Text, nullable=False, default="")
    vehicle: Mapped[Vehicle] = relationship(back_populates="recalls")
