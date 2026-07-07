from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Preference(str, Enum):
    NATIONAL_PARK = "national-park"
    HIKING = "hiking"
    CITY_WALK = "city-walk"
    FOREST = "forest"
    BEACH = "beach"


class Location(BaseModel):
    lat: float
    lng: float
    label: str = ""


class PlanRequest(BaseModel):
    origin: Location
    trip_type: Literal["day-trip", "weekend"] = "day-trip"
    start_date: str
    end_date: str | None = None
    max_drive_hours: float = Field(default=3.0, ge=0.5, le=12.0)
    max_flight_hours: float = Field(default=2.0, ge=0.5, le=8.0)
    preferences: list[Preference] = Field(default_factory=list)
    allow_flight: bool = False


class Activity(BaseModel):
    time: str
    place: str
    duration: str
    note: str = ""


class DayPlan(BaseModel):
    date: str
    activities: list[Activity]


class Itinerary(BaseModel):
    destination: str
    destination_lat: float
    destination_lng: float
    drive_time: str
    drive_hours: float
    days: list[DayPlan]
    alternatives: list[str] = Field(default_factory=list)
    packing_tips: list[str] = Field(default_factory=list)
    weather_note: str = ""
    summary: str = ""


class PlanResponse(BaseModel):
    itinerary: Itinerary
    candidates: list[dict]


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    current_itinerary: Itinerary | None = None
    origin: Location | None = None
    preferences: list[Preference] = Field(default_factory=list)


class ChatResponse(BaseModel):
    reply: str
    itinerary: Itinerary | None = None
