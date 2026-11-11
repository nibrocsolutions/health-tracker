def test_backup_round_trip(client):
    person = client.post("/api/people", json={"name": "Alex"}).json()
    day = f"/api/days/{person['id']}/2026-11-11"
    client.put(day, json={"feeling": "good", "notes": "Steady", "weight_lb": 180.5, "systolic": 118, "diastolic": 74, "water_glasses": 8})
    client.put(day + "/meals", json={"meals": [
        {"slot": 1, "protein": "Eggs", "side": "Fruit"},
        {"slot": 2, "protein": "", "side": ""},
        {"slot": 3, "protein": "", "side": ""},
        {"slot": 4, "protein": "", "side": ""},
        {"slot": 5, "protein": "", "side": ""},
        {"slot": 6, "protein": "Fish", "side": "Greens"},
    ]})
    client.post(day + "/workouts", json={"kind": "cardio", "minutes": 30, "notes": "Walk"})

    exported = client.get("/api/admin/export")
    assert exported.status_code == 200
    payload = exported.json()
    assert payload["format"] == "health-backup"
    assert payload["people"][0]["name"] == "Alex"
    assert len(payload["meals"]) == 2
    assert len(payload["workouts"]) == 1

    client.post("/api/people", json={"name": "Blake"})
    restored = client.post("/api/admin/import", json=payload)
    assert restored.status_code == 200, restored.text
    assert restored.json() == {"people": 1, "days": 1, "meals": 2, "workouts": 1}
    people = client.get("/api/people").json()
    assert [person["name"] for person in people] == ["Alex"]
    loaded = client.get(f"/api/days/{people[0]['id']}/2026-11-11").json()
    assert loaded["notes"] == "Steady"
    assert loaded["weight_lb"] == 180.5
    assert loaded["water_glasses"] == 8
    assert exported.json()["days"][0]["water_glasses"] == 8
    assert loaded["meals"][0]["protein"] == "Eggs"
    assert loaded["meals"][5]["side"] == "Greens"
    assert loaded["workouts"][0]["notes"] == "Walk"

    added = client.post("/api/people", json={"name": "Casey"})
    assert added.status_code == 201

    older = {
        "format": "health-backup",
        "version": 1,
        "people": [{"id": 1, "name": "Alex"}],
        "days": [{"id": 1, "person_id": 1, "date": "2026-11-12", "feeling": "okay", "notes": "Before water"}],
        "meals": [],
        "workouts": [],
    }
    restored_old = client.post("/api/admin/import", json=older)
    assert restored_old.status_code == 200, restored_old.text
    person = client.get("/api/people").json()[0]
    loaded_old = client.get(f"/api/days/{person['id']}/2026-11-12").json()
    assert loaded_old["notes"] == "Before water"
    assert loaded_old["water_glasses"] is None


def test_bad_backup_is_refused(client):
    client.post("/api/people", json={"name": "Alex"})
    refused = client.post("/api/admin/import", json={"format": "other", "version": 1})
    assert refused.status_code == 422
    assert "not a Daily backup" in refused.json()["detail"]
    assert client.get("/api/people").json()[0]["name"] == "Alex"

    broken = {
        "format": "health-backup",
        "version": 1,
        "people": [{"id": 1, "name": "Alex"}],
        "days": [{"id": 1, "person_id": 1, "date": "2026-11-11", "weight_lb": 10}],
        "meals": [],
        "workouts": [],
    }
    refused = client.post("/api/admin/import", json=broken)
    assert refused.status_code == 422
    assert "40 and 800" in refused.json()["detail"]
    assert client.get("/api/people").json()[0]["name"] == "Alex"
