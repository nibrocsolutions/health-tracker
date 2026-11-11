from datetime import date

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import DayLog, Person, Workout


def person_or_404(db: Session, person_id: int) -> Person:
    person = db.get(Person, person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="That person is not on this tracker.")
    return person


def get_day(db: Session, person_id: int, logged_on: date) -> DayLog | None:
    return db.scalar(
        select(DayLog)
        .where(DayLog.person_id == person_id, DayLog.logged_on == logged_on)
        .options(selectinload(DayLog.meals), selectinload(DayLog.workouts))
    )


def workout_or_404(db: Session, workout_id: int) -> Workout:
    workout = db.get(Workout, workout_id)
    if workout is None:
        raise HTTPException(status_code=404, detail="That workout is no longer here.")
    return workout
