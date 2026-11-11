from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Person(Base):
    __tablename__ = "people"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    days: Mapped[list["DayLog"]] = relationship(back_populates="person", cascade="all, delete-orphan")


class DayLog(Base):
    __tablename__ = "days"
    __table_args__ = (UniqueConstraint("person_id", "logged_on"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"))
    logged_on: Mapped[date] = mapped_column(Date)
    feeling: Mapped[str] = mapped_column(String(20), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    weight_lb: Mapped[float | None] = mapped_column(Float, nullable=True)
    systolic: Mapped[int | None] = mapped_column(Integer, nullable=True)
    diastolic: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pulse: Mapped[int | None] = mapped_column(Integer, nullable=True)
    water_glasses: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    person: Mapped[Person] = relationship(back_populates="days")
    meals: Mapped[list["Meal"]] = relationship(
        back_populates="day", cascade="all, delete-orphan", order_by="Meal.slot"
    )
    workouts: Mapped[list["Workout"]] = relationship(
        back_populates="day", cascade="all, delete-orphan", order_by="Workout.id"
    )


class Meal(Base):
    __tablename__ = "meals"
    __table_args__ = (UniqueConstraint("day_id", "slot"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    day_id: Mapped[int] = mapped_column(ForeignKey("days.id", ondelete="CASCADE"))
    slot: Mapped[int] = mapped_column(Integer)
    protein: Mapped[str] = mapped_column(String(80), default="")
    side: Mapped[str] = mapped_column(String(80), default="")

    day: Mapped[DayLog] = relationship(back_populates="meals")


class Workout(Base):
    __tablename__ = "workouts"

    id: Mapped[int] = mapped_column(primary_key=True)
    day_id: Mapped[int] = mapped_column(ForeignKey("days.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(20))
    minutes: Mapped[int] = mapped_column(Integer, default=30)
    notes: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    day: Mapped[DayLog] = relationship(back_populates="workouts")
