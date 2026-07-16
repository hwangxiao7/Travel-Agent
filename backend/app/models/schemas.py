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
    trending: bool = False  # surfaced from social media (TikTok travel guides)
    # Experience layer (open-vocab): what kind of experience this is, for
    # persona matching (e.g. ["outdoor", "foraging", "hands-on", "water"]).
    experience_tags: list[str] = Field(default_factory=list)
    blurb: str = ""  # short neutral experience descriptor (derived, not copied)


class Event(BaseModel):
    name: str
    date: str = ""
    venue: str = ""
    category: str = ""
    url: str = ""


class SocialPost(BaseModel):
    title: str
    author: str = ""
    url: str = ""
    likes: int = 0
    views: int = 0
    thumbnail: str = ""
    platform: str = "tiktok"


class SocialEmbed(BaseModel):
    """Official oEmbed payload — for live display only, never persisted."""

    platform: str = "tiktok"
    url: str = ""
    title: str = ""
    author: str = ""
    thumbnail: str = ""
    html: str = ""  # official embed iframe/blockquote markup


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
    viral: list[Place] = Field(default_factory=list)  # 🔥 spots pulled from social guides
    guides: list[SocialPost] = Field(default_factory=list)  # TikTok travel-guide posts


class PlanResponse(BaseModel):
    itinerary: Itinerary
    candidates: list[dict]


class SearchRequest(BaseModel):
    origin: Location
    query: str
    trip_type: Literal["day-trip", "weekend"] = "day-trip"
    start_date: str
    end_date: str | None = None
    max_drive_hours: float = Field(default=3.0, ge=0.5, le=12.0)
    max_flight_hours: float = Field(default=4.0, ge=0.5, le=12.0)
    preferences: list[Preference] = Field(default_factory=list)
    allow_flight: bool = False
    language: str = "en"


class SearchResponse(BaseModel):
    itinerary: Itinerary
    candidates: list[dict]
    semantic: bool = False  # True when embedding-based retrieval was used
    intent: dict | None = None
    validation: dict | None = None
    latency_ms: float | None = None
    context_blocks: list[str] = Field(default_factory=list)
    memory: dict | None = None
    fusion_weights: dict | None = None
    search_path: str | None = None  # "corpus" | "poi"


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


class SocialImportRequest(BaseModel):
    """User-submitted social links (compliant path — no scraping)."""

    urls: list[str] = Field(default_factory=list)
    lat: float
    lng: float
    dest_name: str = ""  # attach extracted spots to this destination (optional)
    language: str = "en"
    persist: bool = True  # store distilled facts into the trending catalog


class SocialImportResponse(BaseModel):
    imported_links: int = 0
    spots: list[Place] = Field(default_factory=list)  # verified facts
    embeds: list[SocialEmbed] = Field(default_factory=list)  # official display only
    created: int = 0
    updated: int = 0


class SocialTextImportRequest(BaseModel):
    """User-pasted note text (compliant path for platforms without oEmbed, e.g. RED)."""

    texts: list[str] = Field(default_factory=list)
    lat: float
    lng: float
    dest_name: str = ""
    language: str = "en"
    platform: str = "xiaohongshu"
    persist: bool = True


class DiscoverRequest(BaseModel):
    """Proactive experience push: match fresh trending spots to the user's taste."""

    origin: Location
    preferences: list[Preference] = Field(default_factory=list)
    interests: str = ""  # free-text persona hint, e.g. "outdoor, foraging, hands-on"
    radius_miles: int = 40
    language: str = "en"
    k: int = 8


class ExperiencePush(BaseModel):
    name: str
    lat: float
    lng: float
    kind: Literal["food", "fun"] = "fun"
    blurb: str = ""
    experience_tags: list[str] = Field(default_factory=list)
    platforms: list[str] = Field(default_factory=list)
    distance_miles: float = 0.0
    freshness_days: int = 0
    match_score: float = 0.0
    reason: str = ""


class DiscoverResponse(BaseModel):
    pushes: list[ExperiencePush] = Field(default_factory=list)
    persona_tags: list[str] = Field(default_factory=list)  # transparency


class ActivitySuggestion(BaseModel):
    key: str
    name: str
    name_en: str = ""
    name_zh: str = ""
    tags: list[str] = Field(default_factory=list)
    duration_h: float = 0.0
    energy: str = ""
    cost: str = ""
    companion: list[str] = Field(default_factory=list)
    indoor: bool = False
    in_season: bool = True
    match_score: float = 0.0
    blurb: str = ""
    reason: str = ""
    # Shared vibe sticker key (e.g. vibe-water) — not one image per activity.
    icon_key: str = ""


class ActivitiesRequest(BaseModel):
    """Shop-independent activity push for 'don't know what to do today'."""

    interests: str = ""  # optional free-text mood/idea; empty = taste-driven
    companion: str = ""  # solo / date / family / friends / group
    energy: str = ""  # low / medium / high
    budget: str = ""  # $ / $$ / $$$ (max)
    weather: str = ""  # optional context hint
    language: str = "en"
    k: int = 8


class ActivitiesResponse(BaseModel):
    activities: list[ActivitySuggestion] = Field(default_factory=list)


class ActivityVenueOut(BaseModel):
    name: str
    lat: float
    lng: float
    distance_miles: float
    drive_time: str = ""
    source: str = ""  # trending | nominatim
    query: str = ""
    blurb: str = ""


class ActivityVenuesRequest(BaseModel):
    """Resolve nearby places for a picked activity type."""

    activity_key: str
    origin: Location
    radius_miles: float = 40.0
    k: int = 6
    language: str = "en"


class ActivityVenuesResponse(BaseModel):
    activity_key: str
    activity_name: str
    venues: list[ActivityVenueOut] = Field(default_factory=list)


class TasteSnippetOut(BaseModel):
    id: int
    text: str
    source: str = ""
    polarity: float = 1.0


class TasteProfileOut(BaseModel):
    likes: list[str] = Field(default_factory=list)  # what we think you enjoy
    dislikes: list[str] = Field(default_factory=list)
    n_signals: int = 0
    snippets: list[TasteSnippetOut] = Field(default_factory=list)  # editable, stored ones


class TasteAddRequest(BaseModel):
    text: str
    polarity: float = 1.0  # +1 like / -1 dislike


class ExperienceFeedbackRequest(BaseModel):
    name: str
    verdict: str  # like | dislike | crowded | again
    destination: str = ""


class OkResponse(BaseModel):
    ok: bool = True


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


# --- Account / social ---


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=6, max_length=72)
    display_name: str = ""


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=1, max_length=72)


class UserOut(BaseModel):
    id: int
    email: str
    display_name: str
    contact: str = ""
    home_label: str = ""
    home_lat: float = 0.0
    home_lng: float = 0.0
    default_prefs: list[Preference] = Field(default_factory=list)
    crowd_opt_out: bool = False
    phone: str = ""  # masked when present, e.g. 138****8000
    has_password: bool = True
    auth_providers: list[str] = Field(default_factory=list)  # email | phone | wechat


class PhoneSendRequest(BaseModel):
    phone: str


class PhoneVerifyRequest(BaseModel):
    phone: str
    code: str = Field(min_length=4, max_length=8)
    display_name: str = ""


class WeChatExchangeRequest(BaseModel):
    ticket: str


class AuthMethodsOut(BaseModel):
    email: bool = True
    phone: bool = False
    wechat: bool = False


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class SaveTripRequest(BaseModel):
    destination: str
    destination_lat: float = 0.0
    destination_lng: float = 0.0
    travel_mode: Literal["drive", "fly"] = "drive"
    start_date: str = ""
    end_date: str = ""
    summary: str = ""
    places: list[str] = Field(default_factory=list)


class TripOut(BaseModel):
    id: int
    destination: str
    destination_lat: float
    destination_lng: float
    travel_mode: str
    start_date: str
    end_date: str
    summary: str
    places: list[str]
    created_at: str


class ReviewCreate(BaseModel):
    place_name: str
    destination: str = ""
    rating: int = Field(ge=1, le=5)
    comment: str = ""


class ReviewOut(BaseModel):
    id: int
    place_name: str
    destination: str
    rating: int
    comment: str
    author: str
    created_at: str
    updated_at: str


class PlaceReviewsResponse(BaseModel):
    place_name: str
    average_rating: float
    review_count: int
    reviews: list[ReviewOut]


class ProfileOut(BaseModel):
    user: UserOut
    profile_text: str
    trip_count: int
    review_count: int


class FeedbackCreate(BaseModel):
    event_type: Literal["click", "save", "skip", "visit", "rate", "share"]
    destination: str = ""
    place_name: str = ""
    value: float = 0.0  # e.g. rating 1-5 when event_type == "rate"


class FeedbackOut(BaseModel):
    ok: bool
    event_type: str
    destination: str


# --- Account management + persona ---


class ProfileUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    contact: str | None = Field(default=None, max_length=120)
    home_label: str | None = Field(default=None, max_length=200)
    home_lat: float | None = None
    home_lng: float | None = None
    default_prefs: list[Preference] | None = None
    # Opt out of contributing behavior to the anonymized crowd/collective signals.
    crowd_opt_out: bool | None = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6, max_length=72)


class DeleteAccountRequest(BaseModel):
    password: str


class MyReviewsResponse(BaseModel):
    reviews: list[ReviewOut]


class PersonaAxisOut(BaseModel):
    key: str
    low: str
    high: str
    score: float


class PersonaOut(BaseModel):
    scores: dict[str, float]
    axes: list[PersonaAxisOut]
    confidence: float
    type_code: str
    title: str
    blurb: str
    has_quiz: bool


class PersonaQuizOption(BaseModel):
    id: str
    label: str


class PersonaQuizQuestion(BaseModel):
    id: str
    q: str
    options: list[PersonaQuizOption]


class PersonaQuizResponse(BaseModel):
    questions: list[PersonaQuizQuestion]


class PersonaQuizSubmit(BaseModel):
    answers: dict[str, str]  # {question_id: option_id}


class PersonaUpdate(BaseModel):
    scores: dict[str, float]  # {axis_key: 0-100} — manual slider tuning
