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
    first_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


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


def init_db() -> None:
    engine = get_engine()
    Base.metadata.create_all(bind=engine)


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
