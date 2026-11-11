from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Person
from app.queries import person_or_404
from app.schemas import DayWrite, MealsWrite, PersonIn, WorkoutIn
from app.serialize import person_out
from app.service import (
    add_workout,
    marks_between,
    progress_for,
    read_day,
    remove_person,
    remove_workout,
    save_meals,
    save_scalars,
)

router = APIRouter()


def _name_taken(db: Session, name: str, ignore_id: int | None = None) -> bool:
    stmt = select(Person).where(func.lower(Person.name) == name.lower())
    if ignore_id is not None:
        stmt = stmt.where(Person.id != ignore_id)
    return db.scalar(stmt) is not None


@router.get("/api/health")
def health() -> dict:
    return {"status": "ok", "app": "Daily"}


@router.get("/api/people")
def list_people(db: Session = Depends(get_db)) -> list[dict]:
    people = db.scalars(select(Person).order_by(Person.name)).all()
    return [person_out(person) for person in people]


@router.post("/api/people", status_code=201)
def create_person(payload: PersonIn, db: Session = Depends(get_db)) -> dict:
    if _name_taken(db, payload.name):
        raise HTTPException(status_code=409, detail="Someone with that name is already on this tracker.")
    person = Person(name=payload.name)
    db.add(person)
    db.commit()
    db.refresh(person)
    return person_out(person)


@router.patch("/api/people/{person_id}")
def rename_person(person_id: int, payload: PersonIn, db: Session = Depends(get_db)) -> dict:
    person = person_or_404(db, person_id)
    if _name_taken(db, payload.name, ignore_id=person.id):
        raise HTTPException(status_code=409, detail="Someone with that name is already on this tracker.")
    person.name = payload.name
    db.commit()
    db.refresh(person)
    return person_out(person)


@router.delete("/api/people/{person_id}", status_code=204)
def delete_person(person_id: int, db: Session = Depends(get_db)) -> Response:
    person = person_or_404(db, person_id)
    remove_person(db, person)
    return Response(status_code=204)


@router.get("/api/days")
def list_marks(
    person_id: int,
    start: date,
    end: date,
    db: Session = Depends(get_db),
) -> dict:
    return {"days": marks_between(db, person_id, start, end)}


@router.get("/api/days/{person_id}/{logged_on}")
def get_logged_day(person_id: int, logged_on: date, db: Session = Depends(get_db)) -> dict:
    return read_day(db, person_id, logged_on)


@router.put("/api/days/{person_id}/{logged_on}")
def put_logged_day(
    person_id: int,
    logged_on: date,
    payload: DayWrite,
    db: Session = Depends(get_db),
) -> dict:
    return save_scalars(db, person_id, logged_on, payload)


@router.put("/api/days/{person_id}/{logged_on}/meals")
def put_meals(
    person_id: int,
    logged_on: date,
    payload: MealsWrite,
    db: Session = Depends(get_db),
) -> dict:
    return save_meals(db, person_id, logged_on, payload)


@router.post("/api/days/{person_id}/{logged_on}/workouts", status_code=201)
def post_workout(
    person_id: int,
    logged_on: date,
    payload: WorkoutIn,
    db: Session = Depends(get_db),
) -> dict:
    return add_workout(db, person_id, logged_on, payload)


@router.delete("/api/workouts/{workout_id}")
def delete_workout(workout_id: int, db: Session = Depends(get_db)) -> dict:
    return remove_workout(db, workout_id)


@router.get("/api/progress")
def progress(person_id: int, today: date | None = None, db: Session = Depends(get_db)) -> dict:
    return progress_for(db, person_id, today or date.today())
