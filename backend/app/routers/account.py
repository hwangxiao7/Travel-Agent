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
from app.db import FeedbackEvent, PlaceReview, Trip, User, get_db, place_key
from app.models.schemas import (
    AuthResponse,
    ChangePasswordRequest,
    DeleteAccountRequest,
    FeedbackCreate,
    FeedbackOut,
    LoginRequest,
    MyReviewsResponse,
    PersonaOut,
    PersonaQuizResponse,
    PersonaQuizSubmit,
    PersonaUpdate,
    PlaceReviewsResponse,
    ProfileOut,
    ProfileUpdateRequest,
    RegisterRequest,
    ReviewCreate,
    ReviewOut,
    SaveTripRequest,
    TripOut,
    UserOut,
)
from app.services.personalization import public_reviews_for_place, rebuild_profile_text
from app.services.persona import (
    get_or_build_persona,
    quiz_answers_to_leans,
    save_persona,
    set_manual_scores,
)

router = APIRouter(prefix="/api", tags=["account"])


def _public_email(raw: str | None) -> str:
    e = (raw or "").strip()
    if e.startswith("__phone__") or e.startswith("__wx__"):
        return ""
    return e


def _mask_phone(phone: str | None) -> str:
    p = (phone or "").strip()
    if len(p) < 7:
        return ""
    # +8613800138000 → 138****8000
    digits = p[3:] if p.startswith("+86") else p
    if len(digits) == 11:
        return f"{digits[:3]}****{digits[-4:]}"
    return p[-4:].rjust(4, "*")


def _user_out(u: User) -> UserOut:
    try:
        prefs = json.loads(getattr(u, "default_prefs", "[]") or "[]")
    except json.JSONDecodeError:
        prefs = []
    providers: list[str] = []
    email = _public_email(u.email)
    if email:
        providers.append("email")
    phone = getattr(u, "phone", None) or ""
    if phone:
        providers.append("phone")
    if getattr(u, "wechat_openid", None):
        providers.append("wechat")
    pwd = getattr(u, "password_hash", "") or ""
    return UserOut(
        id=u.id,
        email=email,
        display_name=u.display_name or "",
        contact=getattr(u, "contact", "") or "",
        home_label=getattr(u, "home_label", "") or "",
        home_lat=getattr(u, "home_lat", 0.0) or 0.0,
        home_lng=getattr(u, "home_lng", 0.0) or 0.0,
        default_prefs=[p for p in prefs if isinstance(p, str)],
        crowd_opt_out=bool(getattr(u, "crowd_opt_out", 0)),
        phone=_mask_phone(phone),
        has_password=bool(pwd),
        auth_providers=providers,
    )


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
        author=(r.user.display_name or _public_email(r.user.email).split("@")[0] or "user"),
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
    token = create_access_token(user.id, user.email, user.token_version or 0)
    return AuthResponse(access_token=token, user=_user_out(user))


@router.post("/auth/login", response_model=AuthResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    from app.auth import _DUMMY_PASSWORD_HASH

    email = body.email.strip().lower()
    if not email or "@" not in email:
        verify_password(body.password, _DUMMY_PASSWORD_HASH)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        # Same work + same error as wrong password (no email enumeration).
        verify_password(body.password, _DUMMY_PASSWORD_HASH)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    pwd = user.password_hash or ""
    if not pwd or not verify_password(body.password, pwd):
        if pwd:
            pass  # already verified false
        else:
            verify_password(body.password, _DUMMY_PASSWORD_HASH)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token(user.id, user.email, user.token_version or 0)
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


@router.patch("/me", response_model=UserOut)
def update_profile(
    body: ProfileUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update display name / contact / home base / default preferences."""
    if body.display_name is not None:
        user.display_name = body.display_name.strip()[:120]
    if body.contact is not None:
        user.contact = body.contact.strip()[:120]
    if body.home_label is not None:
        user.home_label = body.home_label.strip()[:200]
    if body.home_lat is not None:
        user.home_lat = body.home_lat
    if body.home_lng is not None:
        user.home_lng = body.home_lng
    if body.default_prefs is not None:
        user.default_prefs = json.dumps([p.value for p in body.default_prefs])
    if body.crowd_opt_out is not None:
        user.crowd_opt_out = 1 if body.crowd_opt_out else 0
    db.commit()
    db.refresh(user)
    return _user_out(user)


@router.post("/auth/change-password", response_model=AuthResponse)
def change_password(
    body: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pwd = user.password_hash or ""
    if not pwd or not verify_password(body.current_password, pwd):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    user.password_hash = hash_password(body.new_password)
    user.token_version = (user.token_version or 0) + 1  # invalidate old sessions
    db.commit()
    db.refresh(user)
    token = create_access_token(user.id, user.email, user.token_version)
    return AuthResponse(access_token=token, user=_user_out(user))


@router.delete("/me")
def delete_account(
    body: DeleteAccountRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pwd = user.password_hash or ""
    if not pwd:
        raise HTTPException(
            status_code=400,
            detail="This account has no password — contact support or re-auth via phone to delete",
        )
    if not verify_password(body.password, pwd):
        raise HTTPException(status_code=401, detail="Password is incorrect")
    db.delete(user)  # cascade removes trips + reviews
    db.commit()
    return {"ok": True}


@router.post("/auth/logout-all")
def logout_all(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Invalidate every existing token for this user (server-side logout)."""
    user.token_version = (user.token_version or 0) + 1
    db.commit()
    return {"ok": True}


@router.get("/me/reviews", response_model=MyReviewsResponse)
def my_reviews(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(PlaceReview).where(PlaceReview.user_id == user.id).order_by(PlaceReview.updated_at.desc())
    ).all()
    return MyReviewsResponse(reviews=[_review_out(r) for r in rows])


@router.get("/me/persona", response_model=PersonaOut)
def get_persona(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return PersonaOut(**get_or_build_persona(db, user).to_dict())


@router.post("/me/persona/recompute", response_model=PersonaOut)
def recompute_persona(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return PersonaOut(**get_or_build_persona(db, user, recompute=True).to_dict())


@router.patch("/me/persona", response_model=PersonaOut)
def update_persona(
    body: PersonaUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manually tune persona axis scores (slider drag) → persisted, biases ranking."""
    return PersonaOut(**set_manual_scores(db, user, body.scores).to_dict())


@router.get("/me/persona/quiz", response_model=PersonaQuizResponse)
def persona_quiz(language: str = "en"):
    from app.services.persona import quiz_questions

    return PersonaQuizResponse(questions=quiz_questions(language))


@router.post("/me/persona/quiz", response_model=PersonaOut)
def submit_persona_quiz(
    body: PersonaQuizSubmit,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Persist quiz → recompute persona (quiz-dominant) → taste + default prefs."""
    from app.services.persona import (
        apply_quiz_to_user,
        compute_persona,
        quiz_answers_to_leans,
    )

    leans = quiz_answers_to_leans(body.answers)
    if not leans:
        raise HTTPException(status_code=422, detail="No valid quiz answers")
    persona = get_or_build_persona(db, user, recompute=True)
    persona.quiz = leans
    save_persona(db, user, persona)
    # Explicit retake: quiz outweighs stale behavior so the result actually moves.
    fresh = compute_persona(db, user, quiz_weight=0.8)
    save_persona(db, user, fresh)
    apply_quiz_to_user(db, user, fresh)
    return PersonaOut(**fresh.to_dict())


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
    from app.services.interaction_log import log_event

    log_event(user, stage="saved", surface="trip",
              item_name=trip.destination, item_kind="destination")
    return _trip_out(trip)


@router.post("/feedback", response_model=FeedbackOut)
def record_feedback(
    body: FeedbackCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Record a behavior event (design doc §14) → feeds personalized ranking."""
    name = body.place_name.strip()
    event = FeedbackEvent(
        user_id=user.id,
        event_type=body.event_type,
        place_key=place_key(name) if name else "",
        place_name=name,
        destination=body.destination.strip(),
        value=body.value,
    )
    db.add(event)
    db.commit()

    _STAGE = {"save": "saved", "visit": "saved", "share": "saved",
              "rate": "rated", "skip": "skipped", "click": "selected"}
    stage = _STAGE.get(body.event_type)
    if stage:
        from app.services.interaction_log import log_event

        log_event(user, stage=stage, surface="feedback",
                  item_key=event.place_key, item_name=name or body.destination.strip(),
                  item_kind="place" if name else "destination",
                  outcome_value=float(body.value or 0.0))
    return FeedbackOut(ok=True, event_type=body.event_type, destination=body.destination.strip())


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

    def _log_rating():
        from app.services.interaction_log import log_event

        log_event(user, stage="rated", surface="review", item_key=key,
                  item_name=name, item_kind="place", outcome_value=float(body.rating))

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
        _log_rating()
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
    _log_rating()
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
