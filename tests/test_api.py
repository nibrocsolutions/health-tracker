def _person(client, name="Alex"):
    created = client.post("/api/people", json={"name": name})
    assert created.status_code == 201, created.text
    return created.json()


def _meals(filled=None):
    filled = filled or {}
    meals = []
    for slot in range(1, 7):
        protein, side = filled.get(slot, ("", ""))
        meals.append({"slot": slot, "protein": protein, "side": side})
    return {"meals": meals}


def test_health_and_home_page(client):
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok", "app": "Daily"}
    page = client.get("/")
    assert page.status_code == 200
    assert "viewport" in page.text
    assert "Daily" in page.text
    assert 'name="apple-mobile-web-app-capable"' in page.text
    assert 'data-tab="calendar"' in page.text
    assert page.text.index('data-tab="calendar"') < page.text.index('data-tab="today"')
    assert 'data-tab="today"' in page.text
    assert 'data-tab="progress"' in page.text
    script = client.get("/static/js/app.js")
    assert script.status_code == 200
    assert 'tab: "calendar"' in script.text
    admin = client.get("/admin")
    assert admin.status_code == 200
    assert "/static/js/app.js?v=" in admin.text


def test_people_are_separate_logs(client):
    alex = _person(client, "Alex")
    blake = _person(client, "  Blake  ")
    assert blake["name"] == "Blake"
    again = client.post("/api/people", json={"name": "alex"})
    assert again.status_code == 409
    renamed = client.patch(f"/api/people/{alex['id']}", json={"name": "Alexis"})
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Alexis"
    listed = client.get("/api/people")
    assert [person["name"] for person in listed.json()] == ["Alexis", "Blake"]


def test_day_meals_movement_and_readings(client):
    person = _person(client)
    day = "2026-11-11"
    path = f"/api/days/{person['id']}/{day}"
    empty = client.get(path)
    assert empty.status_code == 200
    assert empty.json()["id"] is None
    assert len(empty.json()["meals"]) == 6

    saved = client.put(path, json={"feeling": "Good", "notes": "  Slept well.  "})
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["feeling"] == "good"
    assert body["notes"] == "Slept well."
    assert body["id"] is not None

    meals = client.put(
        f"{path}/meals",
        json=_meals({1: ("Egg and cheese", "Berries"), 4: ("Chicken", "Broccoli")}),
    )
    assert meals.status_code == 200, meals.text
    filled = [meal for meal in meals.json()["meals"] if meal["protein"] or meal["side"]]
    assert [(meal["slot"], meal["protein"], meal["side"]) for meal in filled] == [
        (1, "Egg and cheese", "Berries"),
        (4, "Chicken", "Broccoli"),
    ]

    moved = client.post(f"{path}/workouts", json={"kind": "Cardio", "minutes": 30, "notes": "Easy walk"})
    assert moved.status_code == 201, moved.text
    lifted = client.post(f"{path}/workouts", json={"kind": "weights", "minutes": 30})
    assert lifted.status_code == 201, lifted.text
    assert [item["kind"] for item in lifted.json()["workouts"]] == ["cardio", "weights"]

    readings = client.put(
        path,
        json={"feeling": "good", "notes": "Slept well.", "weight_lb": 180.44, "systolic": 118, "diastolic": 76, "pulse": 64},
    )
    assert readings.status_code == 200, readings.text
    assert readings.json()["weight_lb"] == 180.4
    assert readings.json()["systolic"] == 118
    assert readings.json()["pulse"] == 64
    assert readings.json()["meals"][0]["protein"] == "Egg and cheese"

    other = _person(client, "Blake")
    hidden = client.get(f"/api/days/{other['id']}/{day}")
    assert hidden.json()["id"] is None


def test_readings_are_optional_and_checked(client):
    person = _person(client)
    path = f"/api/days/{person['id']}/2026-11-12"
    light = client.put(path, json={"weight_lb": 10})
    assert light.status_code == 422
    assert "40 and 800" in light.json()["detail"]
    upside = client.put(path, json={"systolic": 70, "diastolic": 90})
    assert upside.status_code == 422
    assert "higher than the bottom" in upside.json()["detail"]
    half = client.put(path, json={"systolic": 120})
    assert half.status_code == 422
    assert "both" in half.json()["detail"].lower()
    pulse = client.put(path, json={"pulse": 60})
    assert pulse.status_code == 422
    short = client.post(f"{path}/workouts", json={"kind": "cardio", "minutes": 2})
    assert short.status_code == 422
    assert "5 and 180" in short.json()["detail"]
    missing = client.get("/api/days/999/2026-11-12")
    assert missing.status_code == 404


def test_calendar_marks_and_clearing_a_day(client):
    person = _person(client)
    day = "2026-11-11"
    path = f"/api/days/{person['id']}/{day}"
    client.put(f"{path}/meals", json=_meals({2: ("Yogurt", "Apple")}))
    client.post(f"{path}/workouts", json={"kind": "weights", "minutes": 30, "notes": "Squat"})
    client.put(path, json={"feeling": "okay", "notes": "Steady", "weight_lb": 181.2, "systolic": 122, "diastolic": 78})
    marks = client.get("/api/days", params={"person_id": person["id"], "start": "2026-11-01", "end": "2026-11-30"})
    assert marks.status_code == 200, marks.text
    assert len(marks.json()["days"]) == 1
    mark = marks.json()["days"][0]
    assert mark["date"] == day
    assert mark["meals"] == 1
    assert mark["workouts"] == 1
    assert mark["weights_minutes"] == 30
    assert mark["weight_lb"] == 181.2
    assert mark["feeling"] == "okay"
    assert mark["has_notes"] is True

    outside = client.get("/api/days", params={"person_id": person["id"], "start": "2026-10-01", "end": "2026-10-31"})
    assert outside.json()["days"] == []
    backwards = client.get("/api/days", params={"person_id": person["id"], "start": "2026-12-02", "end": "2026-11-01"})
    assert backwards.status_code == 422

    cleared = client.put(f"{path}/meals", json=_meals())
    assert cleared.json()["id"] is not None
    workout_id = cleared.json()["workouts"][0]["id"]
    removed = client.delete(f"/api/workouts/{workout_id}")
    assert removed.status_code == 200, removed.text
    assert removed.json()["workouts"] == []
    blank = client.put(path, json={"feeling": "", "notes": "", "weight_lb": None, "systolic": None, "diastolic": None, "pulse": None})
    assert blank.json()["id"] is None
    quiet = client.get("/api/days", params={"person_id": person["id"], "start": "2026-11-01", "end": "2026-11-30"})
    assert quiet.json()["days"] == []


def test_week_progress_starts_on_sunday(client):
    person = _person(client)
    client.put(
        f"/api/days/{person['id']}/2026-11-11/meals",
        json=_meals({1: ("Eggs", "Spinach"), 2: ("Tuna", "Carrots")}),
    )
    client.post(f"/api/days/{person['id']}/2026-11-11/workouts", json={"kind": "cardio", "minutes": 30})
    client.post(f"/api/days/{person['id']}/2026-11-12/workouts", json={"kind": "weights", "minutes": 25})
    client.put(f"/api/days/{person['id']}/2026-11-08", json={"feeling": "great", "weight_lb": 180})
    client.put(f"/api/days/{person['id']}/2026-11-14", json={"systolic": 118, "diastolic": 76, "pulse": 62})
    client.put(f"/api/days/{person['id']}/2026-11-07", json={"feeling": "low"})
    progress = client.get("/api/progress", params={"person_id": person["id"], "today": "2026-11-11"})
    assert progress.status_code == 200, progress.text
    week = progress.json()["week"]
    assert week["start"] == "2026-11-08"
    assert week["end"] == "2026-11-14"
    assert week["meals"] == 2
    assert week["possible_meals"] == 42
    assert week["workouts"] == 2
    assert week["cardio_minutes"] == 30
    assert week["weights_minutes"] == 25
    assert week["days_logged"] == 4
    assert week["feelings"][0] == {"date": "2026-11-08", "feeling": "great"}
    assert week["feelings"][3]["date"] == "2026-11-11"
    assert week["feelings"][-1]["date"] == "2026-11-14"
    assert [row["date"] for row in progress.json()["weights"]] == ["2026-11-08"]
    assert progress.json()["pressures"][0]["systolic"] == 118
    saturday = client.get("/api/progress", params={"person_id": person["id"], "today": "2026-11-07"})
    assert saturday.json()["week"]["start"] == "2026-11-01"
    assert saturday.json()["week"]["days_logged"] == 1


def test_removing_a_person_removes_their_days(client):
    person = _person(client)
    client.put(f"/api/days/{person['id']}/2026-11-11", json={"notes": "Keep"})
    removed = client.delete(f"/api/people/{person['id']}")
    assert removed.status_code == 204
    assert client.get("/api/people").json() == []
    missing = client.get(f"/api/days/{person['id']}/2026-11-11")
    assert missing.status_code == 404
    summary = client.get("/api/admin/summary")
    assert summary.json()["days"] == 0
    assert summary.json()["people"] == []
