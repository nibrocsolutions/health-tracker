from pydantic import BaseModel, Field, field_validator, model_validator

FEELINGS = {"", "great", "good", "okay", "low", "rough"}
KINDS = {"cardio", "weights"}


class PersonIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("Enter a name.")
        return cleaned


class DayWrite(BaseModel):
    feeling: str = ""
    notes: str = ""
    weight_lb: float | None = None
    systolic: int | None = None
    diastolic: int | None = None
    pulse: int | None = None
    water_glasses: int | None = None
    sleep_hours: float | None = None

    @field_validator("feeling")
    @classmethod
    def check_feeling(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if cleaned not in FEELINGS:
            raise ValueError("Choose a feeling, or leave it blank.")
        return cleaned

    @field_validator("notes")
    @classmethod
    def clean_notes(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) > 2000:
            raise ValueError("Keep the note under 2,000 characters.")
        return cleaned

    @field_validator("weight_lb")
    @classmethod
    def check_weight(cls, value: float | None) -> float | None:
        if value is None:
            return None
        rounded = round(float(value), 1)
        if not 40 <= rounded <= 800:
            raise ValueError("Weight should be between 40 and 800 pounds.")
        return rounded

    @field_validator("water_glasses")
    @classmethod
    def check_water(cls, value: int | None) -> int | None:
        if value is None:
            return None
        if isinstance(value, bool):
            raise ValueError("Glasses should be a whole number.")
        if not 0 <= value <= 40:
            raise ValueError("Glasses should be between 0 and 40.")
        return None if value == 0 else value

    @field_validator("sleep_hours")
    @classmethod
    def check_sleep(cls, value: float | None) -> float | int | None:
        if value is None:
            return None
        if isinstance(value, bool):
            raise ValueError("Hours should be a number.")
        hours = float(value)
        if not 0 <= hours <= 24:
            raise ValueError("Hours should be between 0 and 24.")
        halves = round(hours * 2)
        if abs(hours * 2 - halves) > 1e-6:
            raise ValueError("Hours should be in half-hour steps.")
        stepped = halves / 2
        if stepped == 0:
            return None
        return int(stepped) if stepped.is_integer() else stepped

    @field_validator("systolic", "diastolic", "pulse")
    @classmethod
    def reject_bool(cls, value: int | None) -> int | None:
        if isinstance(value, bool):
            raise ValueError("Use whole numbers for blood pressure and pulse.")
        return value

    @model_validator(mode="after")
    def check_pressure(self):
        if (self.systolic is None) != (self.diastolic is None):
            raise ValueError("Enter both blood pressure numbers, or leave both blank.")
        if self.systolic is not None and self.diastolic is not None:
            if not 70 <= self.systolic <= 250:
                raise ValueError("The top number should be between 70 and 250.")
            if not 40 <= self.diastolic <= 150:
                raise ValueError("The bottom number should be between 40 and 150.")
            if self.systolic <= self.diastolic:
                raise ValueError("The top number should be higher than the bottom number.")
        if self.pulse is not None and not 30 <= self.pulse <= 220:
            raise ValueError("Pulse should be between 30 and 220.")
        if self.pulse is not None and self.systolic is None:
            raise ValueError("Add the blood pressure numbers along with the pulse.")
        return self


class MealIn(BaseModel):
    slot: int = Field(ge=1, le=6)
    protein: str = ""
    side: str = ""

    @field_validator("protein", "side")
    @classmethod
    def clean_food(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) > 80:
            raise ValueError("Keep each food under 80 characters.")
        return cleaned


class MealsWrite(BaseModel):
    meals: list[MealIn]

    @model_validator(mode="after")
    def six_unique(self):
        slots = [meal.slot for meal in self.meals]
        if sorted(slots) != [1, 2, 3, 4, 5, 6]:
            raise ValueError("Send all six meals, numbered 1 through 6.")
        return self


class WorkoutIn(BaseModel):
    kind: str
    minutes: int = 30
    notes: str = ""

    @field_validator("kind")
    @classmethod
    def check_kind(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if cleaned not in KINDS:
            raise ValueError("Choose cardio or weights.")
        return cleaned

    @field_validator("minutes")
    @classmethod
    def check_minutes(cls, value: int) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("Minutes should be a whole number.")
        if not 5 <= value <= 180:
            raise ValueError("A session should be between 5 and 180 minutes.")
        return value

    @field_validator("notes")
    @classmethod
    def clean_notes(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) > 200:
            raise ValueError("Keep the workout note under 200 characters.")
        return cleaned
