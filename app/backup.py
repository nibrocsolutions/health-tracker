"""Full-database export and import for the admin page.

The file is JSON so it can be opened, copied, and restored on another Pi.
"""

from datetime import date, datetime, timezone

from pydantic import ValidationError
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import DayLog, Meal, Person, Workout, utcnow
from app.schemas import DayWrite, MealIn, PersonIn, WorkoutIn
from app.serialize import isoformat_utc

FORMAT = "health-backup"
VERSION = 1


class BackupError(ValueError):
    """The file is not a Daily backup we can restore."""


def _message(exc: ValidationError) -> str:
    msg = exc.errors()[0].get("msg", "Check that entry.")
    if msg.startswith("Value error, "):
        return msg[len("Value error, ") :]
    return msg


def _parse_dt(value: object, label: str) -> datetime:
    if not isinstance(value, str) or not value:
        return utcnow()
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BackupError(f"{label} has a bad time.") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _parse_day(value: object, label: str) -> date:
    if not isinstance(value, str):
        raise BackupError(f"{label} has a bad date.")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise BackupError(f"{label} has a bad date.") from exc


def _ident(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise BackupError(f"{label} needs a real id.")
    return value


def _require_list(payload: dict, key: str) -> list:
    rows = payload.get(key)
    if not isinstance(rows, list):
        raise BackupError(f"The backup is missing {key}.")
    return rows


def export_backup(db: Session) -> dict:
    people = db.scalars(select(Person).order_by(Person.id)).all()
    days = db.scalars(select(DayLog).order_by(DayLog.id)).all()
    meals = db.scalars(select(Meal).order_by(Meal.id)).all()
    workouts = db.scalars(select(Workout).order_by(Workout.id)).all()
    return {
        "format": FORMAT,
        "version": VERSION,
        "exported_at": isoformat_utc(datetime.now(timezone.utc)),
        "people": [
            {"id": person.id, "name": person.name, "created_at": isoformat_utc(person.created_at)}
            for person in people
        ],
        "days": [
            {
                "id": day.id,
                "person_id": day.person_id,
                "date": day.logged_on.isoformat(),
                "feeling": day.feeling,
                "notes": day.notes,
                "weight_lb": day.weight_lb,
                "systolic": day.systolic,
                "diastolic": day.diastolic,
                "pulse": day.pulse,
                "water_glasses": day.water_glasses,
                "sleep_hours": day.sleep_hours,
                "created_at": isoformat_utc(day.created_at),
                "updated_at": isoformat_utc(day.updated_at),
            }
            for day in days
        ],
        "meals": [
            {"id": meal.id, "day_id": meal.day_id, "slot": meal.slot, "protein": meal.protein, "side": meal.side}
            for meal in meals
        ],
        "workouts": [
            {
                "id": workout.id,
                "day_id": workout.day_id,
                "kind": workout.kind,
                "minutes": workout.minutes,
                "notes": workout.notes,
                "created_at": isoformat_utc(workout.created_at),
            }
            for workout in workouts
        ],
    }


def _validate(payload: object) -> dict:
    if not isinstance(payload, dict) or payload.get("format") != FORMAT or payload.get("version") != VERSION:
        raise BackupError("That file is not a Daily backup.")
    people = []
    seen_people: set[int] = set()
    for index, row in enumerate(_require_list(payload, "people"), start=1):
        if not isinstance(row, dict):
            raise BackupError(f"Person {index} is not a record.")
        person_id = _ident(row.get("id"), f"Person {index}")
        if person_id in seen_people:
            raise BackupError(f"Person {index} repeats an id.")
        seen_people.add(person_id)
        try:
            name = PersonIn(name=str(row.get("name", ""))).name
        except ValidationError as exc:
            raise BackupError(f"Person {index}: {_message(exc)}") from exc
        people.append({"id": person_id, "name": name, "created_at": _parse_dt(row.get("created_at"), f"Person {index}")})

    days = []
    seen_days: set[int] = set()
    seen_dates: set[tuple[int, date]] = set()
    for index, row in enumerate(_require_list(payload, "days"), start=1):
        if not isinstance(row, dict):
            raise BackupError(f"Day {index} is not a record.")
        day_id = _ident(row.get("id"), f"Day {index}")
        person_id = _ident(row.get("person_id"), f"Day {index}")
        if person_id not in seen_people:
            raise BackupError(f"Day {index} belongs to a person who is not in the file.")
        if day_id in seen_days:
            raise BackupError(f"Day {index} repeats an id.")
        seen_days.add(day_id)
        logged_on = _parse_day(row.get("date"), f"Day {index}")
        if (person_id, logged_on) in seen_dates:
            raise BackupError(f"Day {index} repeats a date for that person.")
        seen_dates.add((person_id, logged_on))
        try:
            body = DayWrite(
                feeling=row.get("feeling") or "",
                notes=row.get("notes") or "",
                weight_lb=row.get("weight_lb"),
                systolic=row.get("systolic"),
                diastolic=row.get("diastolic"),
                pulse=row.get("pulse"),
                water_glasses=row.get("water_glasses"),
                sleep_hours=row.get("sleep_hours"),
            )
        except ValidationError as exc:
            raise BackupError(f"Day {index}: {_message(exc)}") from exc
        days.append(
            {
                "id": day_id,
                "person_id": person_id,
                "logged_on": logged_on,
                "feeling": body.feeling,
                "notes": body.notes,
                "weight_lb": body.weight_lb,
                "systolic": body.systolic,
                "diastolic": body.diastolic,
                "pulse": body.pulse,
                "water_glasses": body.water_glasses,
                "sleep_hours": body.sleep_hours,
                "created_at": _parse_dt(row.get("created_at"), f"Day {index}"),
                "updated_at": _parse_dt(row.get("updated_at"), f"Day {index}"),
            }
        )

    meals = []
    seen_meals: set[int] = set()
    seen_slots: set[tuple[int, int]] = set()
    for index, row in enumerate(_require_list(payload, "meals"), start=1):
        if not isinstance(row, dict):
            raise BackupError(f"Meal {index} is not a record.")
        meal_id = _ident(row.get("id"), f"Meal {index}")
        day_id = _ident(row.get("day_id"), f"Meal {index}")
        if day_id not in seen_days:
            raise BackupError(f"Meal {index} belongs to a day that is not in the file.")
        if meal_id in seen_meals:
            raise BackupError(f"Meal {index} repeats an id.")
        seen_meals.add(meal_id)
        try:
            body = MealIn(slot=row.get("slot"), protein=row.get("protein") or "", side=row.get("side") or "")
        except ValidationError as exc:
            raise BackupError(f"Meal {index}: {_message(exc)}") from exc
        if not body.protein and not body.side:
            raise BackupError(f"Meal {index} is empty.")
        if (day_id, body.slot) in seen_slots:
            raise BackupError(f"Meal {index} repeats a meal number.")
        seen_slots.add((day_id, body.slot))
        meals.append({"id": meal_id, "day_id": day_id, "slot": body.slot, "protein": body.protein, "side": body.side})

    workouts = []
    seen_workouts: set[int] = set()
    for index, row in enumerate(_require_list(payload, "workouts"), start=1):
        if not isinstance(row, dict):
            raise BackupError(f"Workout {index} is not a record.")
        workout_id = _ident(row.get("id"), f"Workout {index}")
        day_id = _ident(row.get("day_id"), f"Workout {index}")
        if day_id not in seen_days:
            raise BackupError(f"Workout {index} belongs to a day that is not in the file.")
        if workout_id in seen_workouts:
            raise BackupError(f"Workout {index} repeats an id.")
        seen_workouts.add(workout_id)
        try:
            body = WorkoutIn(
                kind=str(row.get("kind", "")),
                minutes=row.get("minutes", 30),
                notes=row.get("notes") or "",
            )
        except ValidationError as exc:
            raise BackupError(f"Workout {index}: {_message(exc)}") from exc
        workouts.append(
            {
                "id": workout_id,
                "day_id": day_id,
                "kind": body.kind,
                "minutes": body.minutes,
                "notes": body.notes,
                "created_at": _parse_dt(row.get("created_at"), f"Workout {index}"),
            }
        )
    return {"people": people, "days": days, "meals": meals, "workouts": workouts}


def restore_backup(db: Session, payload: object) -> dict:
    data = _validate(payload)
    db.execute(delete(Workout))
    db.execute(delete(Meal))
    db.execute(delete(DayLog))
    db.execute(delete(Person))
    db.flush()
    for row in data["people"]:
        db.add(Person(id=row["id"], name=row["name"], created_at=row["created_at"]))
    db.flush()
    for row in data["days"]:
        db.add(DayLog(**row))
    db.flush()
    for row in data["meals"]:
        db.add(Meal(**row))
    for row in data["workouts"]:
        db.add(Workout(**row))
    db.commit()
    return {
        "people": len(data["people"]),
        "days": len(data["days"]),
        "meals": len(data["meals"]),
        "workouts": len(data["workouts"]),
    }
