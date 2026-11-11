"""Create and update one person's day.

A day row exists only after something is saved. Clearing the last meal,
workout, reading, and note removes the row so the calendar stays empty.
"""

from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models import DayLog, Meal, Person, Workout, utcnow
from app.queries import get_day, person_or_404, workout_or_404
from app.schemas import DayWrite, MealsWrite, WorkoutIn
from app.serialize import day_out, empty_day, mark_out


def week_containing(today: date) -> tuple[date, date]:
    start = today - timedelta(days=(today.weekday() + 1) % 7)
    return start, start + timedelta(days=6)


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="That was just saved on another phone. Reload it and try again.",
        ) from exc


def _touch(day: DayLog) -> None:
    day.updated_at = utcnow()


def day_is_blank(day: DayLog) -> bool:
    if day.feeling or day.notes.strip():
        return False
    if day.weight_lb is not None or day.systolic is not None or day.diastolic is not None or day.pulse is not None:
        return False
    if day.water_glasses:
        return False
    if any(meal.protein or meal.side for meal in day.meals):
        return False
    if day.workouts:
        return False
    return True


def _finish(db: Session, person_id: int, logged_on: date, day: DayLog | None) -> dict:
    if day is not None and day_is_blank(day):
        db.delete(day)
        day = None
    _commit(db)
    if day is None:
        return empty_day(person_id, logged_on)
    loaded = get_day(db, person_id, logged_on)
    if loaded is None:
        return empty_day(person_id, logged_on)
    return day_out(loaded)


def _ensure_day(db: Session, person: Person, logged_on: date) -> DayLog:
    day = get_day(db, person.id, logged_on)
    if day is not None:
        return day
    day = DayLog(person_id=person.id, logged_on=logged_on)
    db.add(day)
    db.flush()
    return day


def read_day(db: Session, person_id: int, logged_on: date) -> dict:
    person_or_404(db, person_id)
    day = get_day(db, person_id, logged_on)
    if day is None:
        return empty_day(person_id, logged_on)
    return day_out(day)


def save_scalars(db: Session, person_id: int, logged_on: date, payload: DayWrite) -> dict:
    person = person_or_404(db, person_id)
    day = get_day(db, person.id, logged_on)
    blank = (
        not payload.feeling
        and not payload.notes
        and payload.weight_lb is None
        and payload.systolic is None
        and payload.diastolic is None
        and payload.pulse is None
        and not payload.water_glasses
    )
    if day is None and blank:
        return empty_day(person.id, logged_on)
    if day is None:
        day = _ensure_day(db, person, logged_on)
    day.feeling = payload.feeling
    day.notes = payload.notes
    day.weight_lb = payload.weight_lb
    day.systolic = payload.systolic
    day.diastolic = payload.diastolic
    day.pulse = payload.pulse
    day.water_glasses = payload.water_glasses
    _touch(day)
    return _finish(db, person.id, logged_on, day)


def save_meals(db: Session, person_id: int, logged_on: date, payload: MealsWrite) -> dict:
    person = person_or_404(db, person_id)
    any_food = any(meal.protein or meal.side for meal in payload.meals)
    day = get_day(db, person.id, logged_on)
    if day is None and not any_food:
        return empty_day(person.id, logged_on)
    if day is None:
        day = _ensure_day(db, person, logged_on)
    incoming = {meal.slot: meal for meal in payload.meals}
    for meal in list(day.meals):
        row = incoming[meal.slot]
        if row.protein or row.side:
            meal.protein = row.protein
            meal.side = row.side
        else:
            day.meals.remove(meal)
    for slot, row in incoming.items():
        if not row.protein and not row.side:
            continue
        if any(meal.slot == slot for meal in day.meals):
            continue
        day.meals.append(Meal(day_id=day.id, slot=slot, protein=row.protein, side=row.side))
    _touch(day)
    return _finish(db, person.id, logged_on, day)


def add_workout(db: Session, person_id: int, logged_on: date, payload: WorkoutIn) -> dict:
    person = person_or_404(db, person_id)
    day = _ensure_day(db, person, logged_on)
    day.workouts.append(Workout(day_id=day.id, kind=payload.kind, minutes=payload.minutes, notes=payload.notes))
    _touch(day)
    return _finish(db, person.id, logged_on, day)


def remove_workout(db: Session, workout_id: int) -> dict:
    workout = workout_or_404(db, workout_id)
    day = get_day(db, workout.day.person_id, workout.day.logged_on)
    if day is None:
        raise HTTPException(status_code=404, detail="That workout is no longer here.")
    person_id = day.person_id
    logged_on = day.logged_on
    for item in list(day.workouts):
        if item.id == workout.id:
            day.workouts.remove(item)
    _touch(day)
    return _finish(db, person_id, logged_on, day)


def marks_between(db: Session, person_id: int, start: date, end: date) -> list[dict]:
    person_or_404(db, person_id)
    if end < start:
        raise HTTPException(status_code=422, detail="The end date is before the start date.")
    if (end - start).days > 62:
        raise HTTPException(status_code=422, detail="Ask for at most two months at a time.")
    rows = db.scalars(
        select(DayLog)
        .where(DayLog.person_id == person_id, DayLog.logged_on >= start, DayLog.logged_on <= end)
        .options(selectinload(DayLog.meals), selectinload(DayLog.workouts))
        .order_by(DayLog.logged_on)
    ).all()
    return [mark_out(day) for day in rows]


def progress_for(db: Session, person_id: int, today: date) -> dict:
    person_or_404(db, person_id)
    start, end = week_containing(today)
    week_rows = db.scalars(
        select(DayLog)
        .where(DayLog.person_id == person_id, DayLog.logged_on >= start, DayLog.logged_on <= end)
        .options(selectinload(DayLog.meals), selectinload(DayLog.workouts))
        .order_by(DayLog.logged_on)
    ).all()
    by_date = {day.logged_on: day for day in week_rows}
    meals = 0
    cardio_minutes = 0
    weights_minutes = 0
    workouts = 0
    water_glasses = 0
    feelings = []
    for offset in range(7):
        logged_on = start + timedelta(days=offset)
        day = by_date.get(logged_on)
        feelings.append({"date": logged_on.isoformat(), "feeling": day.feeling if day else ""})
        if day is None:
            continue
        meals += sum(1 for meal in day.meals if meal.protein or meal.side)
        workouts += len(day.workouts)
        cardio_minutes += sum(item.minutes for item in day.workouts if item.kind == "cardio")
        weights_minutes += sum(item.minutes for item in day.workouts if item.kind == "weights")
        water_glasses += day.water_glasses or 0
    weights = [
        {"date": day.logged_on.isoformat(), "weight_lb": day.weight_lb}
        for day in db.scalars(
            select(DayLog)
            .where(DayLog.person_id == person_id, DayLog.weight_lb.is_not(None))
            .order_by(DayLog.logged_on.desc())
            .limit(12)
        )
    ]
    pressures = [
        {
            "date": day.logged_on.isoformat(),
            "systolic": day.systolic,
            "diastolic": day.diastolic,
            "pulse": day.pulse,
        }
        for day in db.scalars(
            select(DayLog)
            .where(DayLog.person_id == person_id, DayLog.systolic.is_not(None))
            .order_by(DayLog.logged_on.desc())
            .limit(12)
        )
    ]
    return {
        "week": {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "meals": meals,
            "possible_meals": 42,
            "workouts": workouts,
            "cardio_minutes": cardio_minutes,
            "weights_minutes": weights_minutes,
            "water_glasses": water_glasses,
            "days_logged": len(week_rows),
            "feelings": feelings,
        },
        "weights": weights,
        "pressures": pressures,
    }


def remove_person(db: Session, person: Person) -> None:
    day_ids = list(db.scalars(select(DayLog.id).where(DayLog.person_id == person.id)))
    if day_ids:
        db.execute(delete(Workout).where(Workout.day_id.in_(day_ids)))
        db.execute(delete(Meal).where(Meal.day_id.in_(day_ids)))
        db.execute(delete(DayLog).where(DayLog.id.in_(day_ids)))
    db.delete(person)
    _commit(db)


def person_counts(db: Session) -> dict:
    people = []
    for person in db.scalars(select(Person).order_by(Person.name)).all():
        days = db.scalar(select(func.count()).select_from(DayLog).where(DayLog.person_id == person.id)) or 0
        people.append({"id": person.id, "name": person.name, "days": days})
    return {
        "people": people,
        "days": db.scalar(select(func.count()).select_from(DayLog)) or 0,
        "meals": db.scalar(select(func.count()).select_from(Meal)) or 0,
        "workouts": db.scalar(select(func.count()).select_from(Workout)) or 0,
    }
