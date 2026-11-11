from datetime import datetime, timezone

from app.models import DayLog, Person


def isoformat_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def person_out(person: Person) -> dict:
    return {"id": person.id, "name": person.name}


def empty_day(person_id: int, logged_on) -> dict:
    return {
        "id": None,
        "person_id": person_id,
        "date": logged_on.isoformat(),
        "feeling": "",
        "notes": "",
        "weight_lb": None,
        "systolic": None,
        "diastolic": None,
        "pulse": None,
        "water_glasses": None,
        "meals": [{"id": None, "slot": slot, "protein": "", "side": ""} for slot in range(1, 7)],
        "workouts": [],
    }


def day_out(day: DayLog) -> dict:
    by_slot = {meal.slot: meal for meal in day.meals}
    meals = []
    for slot in range(1, 7):
        meal = by_slot.get(slot)
        meals.append(
            {
                "id": meal.id if meal else None,
                "slot": slot,
                "protein": meal.protein if meal else "",
                "side": meal.side if meal else "",
            }
        )
    workouts = [
        {
            "id": workout.id,
            "kind": workout.kind,
            "minutes": workout.minutes,
            "notes": workout.notes,
        }
        for workout in day.workouts
    ]
    return {
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
        "meals": meals,
        "workouts": workouts,
    }


def mark_out(day: DayLog) -> dict:
    meals = sum(1 for meal in day.meals if meal.protein or meal.side)
    cardio = sum(workout.minutes for workout in day.workouts if workout.kind == "cardio")
    weights = sum(workout.minutes for workout in day.workouts if workout.kind == "weights")
    return {
        "date": day.logged_on.isoformat(),
        "meals": meals,
        "workouts": len(day.workouts),
        "cardio_minutes": cardio,
        "weights_minutes": weights,
        "weight_lb": day.weight_lb,
        "systolic": day.systolic,
        "diastolic": day.diastolic,
        "feeling": day.feeling,
        "has_notes": bool(day.notes.strip()),
        "water_glasses": day.water_glasses,
    }
