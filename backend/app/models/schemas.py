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
    language: str = "en"


class Activity(BaseModel):
    time: str
    place: str
    duration: str
    note: str = ""


class DayPlan(BaseModel):
    date: str
    activities: list[Activity]


class Place(BaseModel):
    name: str
    category: str = ""  # machine key: restaurant/cafe/bar/museum/viewpoint/park/attraction...
    kind: Literal["food", "fun"] = "fun"
    lat: float
    lng: float
    note: str = ""  # cuisine or short descriptor
    recommended: bool = False  # notable (has wikidata/wikipedia tag)


class Event(BaseModel):
    name: str
    date: str = ""
    venue: str = ""
    category: str = ""
    url: str = ""


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
    travel_mode: Literal["drive", "fly"] = "drive"
    origin_airport: str = ""
    destination_airport: str = ""
    nearby_food: list[Place] = Field(default_factory=list)
    nearby_fun: list[Place] = Field(default_factory=list)
    events: list[Event] = Field(default_factory=list)


class PlanResponse(BaseModel):
    itinerary: Itinerary
    candidates: list[dict]


class SelectRequest(BaseModel):
    origin: Location
    destination_name: str
    trip_type: Literal["day-trip", "weekend"] = "day-trip"
    start_date: str
    end_date: str | None = None
    preferences: list[Preference] = Field(default_factory=list)
    language: str = "en"


class SelectResponse(BaseModel):
    itinerary: Itinerary


class FlyDestinationsRequest(BaseModel):
    origin: Location
    max_flight_hours: float = Field(default=4.0, ge=0.5, le=12.0)
    preferences: list[Preference] = Field(default_factory=list)


class FlyDestinationItem(BaseModel):
    name: str
    lat: float
    lng: float
    region: str
    airport: str
    highlight: str
    flight_time: str
    flight_hours: float
    distance_miles: int


class FlyDestinationsResponse(BaseModel):
    origin_airport: str
    destinations: list[FlyDestinationItem]


class FlyPlanRequest(BaseModel):
    origin: Location
    destination_name: str
    trip_type: Literal["day-trip", "weekend"] = "weekend"
    start_date: str
    end_date: str | None = None
    preferences: list[Preference] = Field(default_factory=list)
    language: str = "en"


class FlightsRequest(BaseModel):
    origin: Location
    destination_name: str
    departure_date: str
    adults: int = Field(default=1, ge=1, le=9)


class FlightOffer(BaseModel):
    price: str
    currency: str
    duration: str
    stops: int
    carrier: str
    depart_airport: str
    depart_at: str
    arrive_airport: str
    arrive_at: str


class FlightsResponse(BaseModel):
    origin_airport: str
    arrival_airport: str
    estimate: dict
    offers: list[FlightOffer]
    has_live_data: bool


class PriceSummary(BaseModel):
    starting_price: int
    cheapest_day: str
    currency: str = "USD"


class FlyPricesRequest(BaseModel):
    origin: Location
    destinations: list[str] = Field(default_factory=list)
    depart_date: str


class FlyPricesResponse(BaseModel):
    origin_airport: str
    prices: dict[str, PriceSummary]


class CalendarDay(BaseModel):
    day: str
    price: int
    group: str = ""


class CalendarRequest(BaseModel):
    origin: Location
    destination_name: str
    depart_date: str


class CalendarResponse(BaseModel):
    origin_airport: str
    arrival_airport: str
    currency: str = "USD"
    starting_price: int | None = None
    cheapest_day: str | None = None
    days: list[CalendarDay] = Field(default_factory=list)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    current_itinerary: Itinerary | None = None
    origin: Location | None = None
    preferences: list[Preference] = Field(default_factory=list)
    language: str = "en"


class ChatResponse(BaseModel):
    reply: str
    itinerary: Itinerary | None = None
