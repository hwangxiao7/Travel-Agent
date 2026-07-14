from __future__ import annotations

from datetime import datetime
from pathlib import Path

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from app.config import settings

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_DEFAULT_DB = f"sqlite:///{_DATA_DIR / 'travel.db'}"


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120), default="")
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # Profile / account management.
    contact: Mapped[str] = mapped_column(String(120), default="")  # phone / handle (optional)
    home_label: Mapped[str] = mapped_column(String(200), default="")
    home_lat: Mapped[float] = mapped_column(Float, default=0.0)
    home_lng: Mapped[float] = mapped_column(Float, default=0.0)
    default_prefs: Mapped[str] = mapped_column(Text, default="[]")  # JSON list of Preference values
    # Bumped on password change / logout-all → invalidates older JWTs.
    token_version: Mapped[int] = mapped_column(Integer, default=0)

    trips: Mapped[list[Trip]] = relationship(back_populates="user", cascade="all, delete-orphan")
    reviews: Mapped[list[PlaceReview]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Trip(Base):
    __tablename__ = "trips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    destination: Mapped[str] = mapped_column(String(200))
    destination_lat: Mapped[float] = mapped_column(Float, default=0.0)
    destination_lng: Mapped[float] = mapped_column(Float, default=0.0)
    travel_mode: Mapped[str] = mapped_column(String(16), default="drive")
    start_date: Mapped[str] = mapped_column(String(32), default="")
    end_date: Mapped[str] = mapped_column(String(32), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    places_json: Mapped[str] = mapped_column(Text, default="[]")  # visited place names
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped[User] = relationship(back_populates="trips")


class PlaceReview(Base):
    __tablename__ = "place_reviews"
    __table_args__ = (UniqueConstraint("user_id", "place_key", name="uq_user_place"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    place_key: Mapped[str] = mapped_column(String(220), index=True)  # normalized name
    place_name: Mapped[str] = mapped_column(String(200))
    destination: Mapped[str] = mapped_column(String(200), default="")
    rating: Mapped[int] = mapped_column(Integer)  # 1–5
    comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped[User] = relationship(back_populates="reviews")


class FeedbackEvent(Base):
    """Implicit + explicit user behavior (design doc §14).

    Events: CLICK / SAVE / SKIP / VISIT / RATE / SHARE. Aggregated into a
    per-destination affinity that feeds the 推 (push) ranking signal.
    """

    __tablename__ = "feedback_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(16), index=True)  # click/save/skip/visit/rate/share
    place_key: Mapped[str] = mapped_column(String(220), index=True, default="")
    place_name: Mapped[str] = mapped_column(String(200), default="")
    destination: Mapped[str] = mapped_column(String(200), default="", index=True)
    value: Mapped[float] = mapped_column(Float, default=0.0)  # e.g. rating 1-5 for RATE
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TrendingSpot(Base):
    """A real place distilled from social media, verified against OSM.

    LEGAL FIREWALL: stores only facts (name, coords, category) + provenance
    (which platforms mentioned it) + freshness timestamps. It deliberately does
    NOT store post text, images, captions, thumbnails, or author handles — those
    are copyrighted expression / personal data. Original posts, if shown at all,
    are rendered live via official oEmbed, never persisted here.
    """

    __tablename__ = "trending_spots"
    __table_args__ = (UniqueConstraint("dest_key", "place_key", name="uq_dest_place"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dest_key: Mapped[str] = mapped_column(String(220), index=True)  # normalized destination
    dest_name: Mapped[str] = mapped_column(String(200), default="")
    place_key: Mapped[str] = mapped_column(String(220), index=True)  # normalized spot name
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(40), default="viral")
    kind: Mapped[str] = mapped_column(String(8), default="fun")  # food | fun
    lat: Mapped[float] = mapped_column(Float, default=0.0)
    lng: Mapped[float] = mapped_column(Float, default=0.0)
    # Provenance only — the platform names, not their content.
    platforms: Mapped[str] = mapped_column(String(120), default="")  # csv: tiktok,instagram
    mention_count: Mapped[int] = mapped_column(Integer, default=1)
    # Experience layer for persona matching (open-vocab, derived facts).
    experience_tags: Mapped[str] = mapped_column(String(240), default="")  # csv
    blurb: Mapped[str] = mapped_column(String(280), default="")  # neutral descriptor
    first_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class TasteSnippet(Base):
    """A persistent, free-form taste signal for one user.

    The "我知道你喜欢什么" store. Each snippet is natural-language ("likes quiet
    coffee places", "avoids crowds", from a typed interest / import / feedback),
    NOT a fixed keyword/tag from a maintained vocabulary — taste is understood
    via embeddings, not enumerated. Snippets accrue over time and decay, so the
    profile evolves as the user keeps using the product.
    """

    __tablename__ = "taste_snippets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    text: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(24), default="")  # interest/import/feedback/review
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    polarity: Mapped[float] = mapped_column(Float, default=1.0)  # +like / -dislike
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class TravelPersona(Base):
    """Abstract travel-taste persona (MBTI-style axes), one per user.

    Not a list of concrete checkboxes — six bipolar axes scored 0–100 (50 neutral),
    derived from behavior (feedback / reviews / trips) plus an optional onboarding
    quiz. A short type code + title + blurb are generated from the dominant axes.
    Axes bias ranking so recommendations match the user's character.
    """

    __tablename__ = "travel_personas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    # Bipolar axis scores (0–100, 50 neutral). See services/persona.py for poles.
    indoor_outdoor: Mapped[float] = mapped_column(Float, default=50.0)
    calm_adventurous: Mapped[float] = mapped_column(Float, default=50.0)
    culture_nature: Mapped[float] = mapped_column(Float, default=50.0)
    quiet_social: Mapped[float] = mapped_column(Float, default=50.0)
    leisurely_active: Mapped[float] = mapped_column(Float, default=50.0)
    popular_novel: Mapped[float] = mapped_column(Float, default=50.0)
    # Confidence 0–1: how much evidence backs the scores (few events → low).
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    quiz_json: Mapped[str] = mapped_column(Text, default="{}")  # raw quiz answers, if taken
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


def _database_url() -> str:
    return settings.database_url or _DEFAULT_DB


_engine = None
SessionLocal = None


def get_engine():
    global _engine, SessionLocal
    if _engine is None:
        url = _database_url()
        if url.startswith("sqlite"):
            _DATA_DIR.mkdir(parents=True, exist_ok=True)
            _engine = create_engine(url, connect_args={"check_same_thread": False})
        else:
            _engine = create_engine(url)
        SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
    return _engine


def _ensure_sqlite_columns(engine) -> None:
    """Lightweight dev migration: add newly-introduced columns to existing tables.

    `create_all` never ALTERs existing tables, so a dev SQLite file created before
    a column was added would be missing it. Add the trending_spots experience
    columns if absent (no-op when already present or on non-sqlite backends)."""
    if not str(engine.url).startswith("sqlite"):
        return
    from sqlalchemy import text

    per_table = {
        "trending_spots": {
            "experience_tags": "VARCHAR(240) DEFAULT ''",
            "blurb": "VARCHAR(280) DEFAULT ''",
        },
        "users": {
            "contact": "VARCHAR(120) DEFAULT ''",
            "home_label": "VARCHAR(200) DEFAULT ''",
            "home_lat": "FLOAT DEFAULT 0.0",
            "home_lng": "FLOAT DEFAULT 0.0",
            "default_prefs": "TEXT DEFAULT '[]'",
            "token_version": "INTEGER DEFAULT 0",
        },
    }
    with engine.begin() as conn:
        for table, wanted in per_table.items():
            existing = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}
            if not existing:
                continue  # table not created yet; create_all handles it fresh
            for col, ddl in wanted.items():
                if col not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"))


def init_db() -> None:
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_columns(engine)


def get_db():
    get_engine()
    assert SessionLocal is not None
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def place_key(name: str) -> str:
    return " ".join(name.strip().lower().split())
