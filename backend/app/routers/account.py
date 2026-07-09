from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.db import PlaceReview, Trip, User, get_db, place_key
from app.models.schemas import (
    AuthResponse,
    LoginRequest,
    PlaceReviewsResponse,
    ProfileOut,
    RegisterRequest,
    ReviewCreate,
    ReviewOut,
    SaveTripRequest,
    TripOut,
    UserOut,
)
from app.services.personalization import public_reviews_for_place, rebuild_profile_text

router = APIRouter(prefix="/api", tags=["account"])


def _user_out(u: User) -> UserOut:
    return UserOut(id=u.id, email=u.email, display_name=u.display_name or "")


def _trip_out(t: Trip) -> TripOut:
    try:
        places = json.loads(t.places_json or "[]")
    except json.JSONDecodeError:
        places = []
    return TripOut(
        id=t.id,
        destination=t.destination,
        destination_lat=t.destination_lat,
        destination_lng=t.destination_lng,
        travel_mode=t.travel_mode,
        start_date=t.start_date,
        end_date=t.end_date,
        summary=t.summary,
        places=places if isinstance(places, list) else [],
        created_at=t.created_at.isoformat() if t.created_at else "",
    )


def _review_out(r: PlaceReview) -> ReviewOut:
    return ReviewOut(
        id=r.id,
        place_name=r.place_name,
        destination=r.destination,
        rating=r.rating,
        comment=r.comment,
        author=r.user.display_name or r.user.email.split("@")[0],
        created_at=r.created_at.isoformat() if r.created_at else "",
        updated_at=r.updated_at.isoformat() if r.updated_at else "",
    )


@router.post("/auth/register", response_model=AuthResponse)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=422, detail="Invalid email")
    existing = db.scalar(select(User).where(User.email == email))
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(
        email=email,
        display_name=(body.display_name or email.split("@")[0]).strip()[:120],
        password_hash=hash_password(body.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(user.id, user.email)
    return AuthResponse(access_token=token, user=_user_out(user))


@router.post("/auth/login", response_model=AuthResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token(user.id, user.email)
    return AuthResponse(access_token=token, user=_user_out(user))


@router.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return _user_out(user)


@router.get("/me/profile", response_model=ProfileOut)
def my_profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    trips = db.scalars(select(Trip).where(Trip.user_id == user.id)).all()
    reviews = db.scalars(select(PlaceReview).where(PlaceReview.user_id == user.id)).all()
    return ProfileOut(
        user=_user_out(user),
        profile_text=rebuild_profile_text(db, user),
        trip_count=len(trips),
        review_count=len(reviews),
    )


@router.post("/trips", response_model=TripOut)
def save_trip(
    body: SaveTripRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    trip = Trip(
        user_id=user.id,
        destination=body.destination.strip(),
        destination_lat=body.destination_lat,
        destination_lng=body.destination_lng,
        travel_mode=body.travel_mode,
        start_date=body.start_date,
        end_date=body.end_date or "",
        summary=body.summary[:2000],
        places_json=json.dumps([p.strip() for p in body.places if p.strip()][:40]),
    )
    db.add(trip)
    db.commit()
    db.refresh(trip)
    return _trip_out(trip)


@router.get("/trips", response_model=list[TripOut])
def list_trips(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Trip).where(Trip.user_id == user.id).order_by(Trip.created_at.desc())
    ).all()
    return [_trip_out(t) for t in rows]


@router.post("/reviews", response_model=ReviewOut)
def upsert_review(
    body: ReviewCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    name = body.place_name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="place_name required")
    key = place_key(name)
    existing = db.scalar(
        select(PlaceReview).where(PlaceReview.user_id == user.id, PlaceReview.place_key == key)
    )
    now = datetime.utcnow()
    if existing:
        existing.rating = body.rating
        existing.comment = body.comment.strip()[:2000]
        existing.destination = body.destination.strip()
        existing.place_name = name
        existing.updated_at = now
        db.commit()
        db.refresh(existing)
        return _review_out(existing)

    review = PlaceReview(
        user_id=user.id,
        place_key=key,
        place_name=name,
        destination=body.destination.strip(),
        rating=body.rating,
        comment=body.comment.strip()[:2000],
        created_at=now,
        updated_at=now,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return _review_out(review)


@router.get("/places/{place_name}/reviews", response_model=PlaceReviewsResponse)
def list_place_reviews(place_name: str, db: Session = Depends(get_db)):
    rows, avg, count = public_reviews_for_place(db, place_name)
    return PlaceReviewsResponse(
        place_name=place_name,
        average_rating=avg,
        review_count=count,
        reviews=[_review_out(r) for r in rows],
    )
