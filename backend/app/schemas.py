"""Pydantic request/response models (input validation lives here)."""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Role = Literal["elder", "caretaker", "family"]
HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{2,}$")


class Strict(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


def normalize_times(values: list[str]) -> list[str]:
    for v in values:
        if not HHMM.match(v):
            raise ValueError(f"'{v}' is not a valid HH:MM time")
    return sorted(set(values))


class ContactIn(Strict):
    name: str = Field(min_length=1, max_length=80)
    email: str = Field(max_length=320)
    role: Role

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        if not EMAIL.match(v):
            raise ValueError("invalid email address")
        return v.lower()


class ProfileCreate(Strict):
    name: str = Field(min_length=1, max_length=80)
    timezone: str = Field(default="Asia/Kolkata", max_length=64)
    contacts: list[ContactIn] = Field(default_factory=list, max_length=20)


class LoginIn(Strict):
    passcode: str = Field(min_length=4, max_length=64)


class MedicationIn(Strict):
    name: str = Field(min_length=1, max_length=100)
    dose: str = Field(min_length=1, max_length=100)
    times: list[str] = Field(min_length=1, max_length=8)
    start_date: date
    end_date: date | None = None
    instructions: str = Field(default="", max_length=300)
    stock: int = Field(default=0, ge=0, le=10000)
    low_stock_threshold: int = Field(default=5, ge=0, le=1000)

    @field_validator("times")
    @classmethod
    def _times(cls, v: list[str]) -> list[str]:
        return normalize_times(v)

    @model_validator(mode="after")
    def _dates(self) -> MedicationIn:
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("end_date must not be before start_date")
        return self


class AppointmentIn(Strict):
    doctor: str = Field(min_length=1, max_length=100)
    place: str = Field(min_length=1, max_length=200)
    starts_at: datetime
    notes: str = Field(default="", max_length=500)

    @field_validator("starts_at")
    @classmethod
    def _naive(cls, v: datetime) -> datetime:
        # Stored as local time of the elder; drop any offset the client sent.
        return v.replace(tzinfo=None, second=0, microsecond=0)


class DoseAction(Strict):
    medication_id: int
    scheduled_at: str
    action: Literal["taken", "skipped"]


class CommentIn(Strict):
    text: str = Field(min_length=1, max_length=500)


class SettingsIn(Strict):
    require_approval: bool


class DraftMedicine(BaseModel):
    """Validated shape of one medicine extracted by AI. Always a draft."""

    name: str = Field(min_length=1, max_length=100)
    dose: str = Field(default="", max_length=100)
    times_per_day: int = Field(default=1, ge=1, le=6)
    instructions: str = Field(default="", max_length=300)


class DraftPrescription(BaseModel):
    medicines: list[DraftMedicine] = Field(max_length=20)


class WeeklySummaryAI(BaseModel):
    summary: str = Field(min_length=1, max_length=1200)
