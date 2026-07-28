"""Preference Profile v1 — deterministic, interpretable, versioned (§7.2).

The plan is explicit that this is a *materialized interpretable* profile, not a
learned model: "Make user feedback affect the next recommendation without
creating a new echo chamber or requiring online model training after every
click." So this module is pure functions over plain dicts. No database, no
model, no randomness — given the same profile and the same event you get the
same profile back, byte for byte, which is what makes `PERS-005`'s versioning
meaningful and what lets `PERS-006` test decay and conflict without fixtures.

Four decisions carry most of the behaviour, and each is a rule from §7.2 that
would be easy to implement backwards:

**Dislike moves less than Like, not more.** The intuitive reading is that a
dislike is a stronger signal — someone bothered to reject something. §7.2 says
the opposite ("decreases them more cautiously to avoid overfitting one click"),
and it is right: a like says "more of this", while a dislike often says "not
this one *right now*". One dislike of a shoegaze track should not delete
shoegaze from a profile built over fifty likes.

**Skip is conditional, not a weak dislike.** A skip two seconds in is a
rejection; a skip at the four-minute mark is a finished listen. Without that
context a skip carries no signal at all, and inventing one from the click alone
is how a profile drifts away from the person it describes.

**Decay is computed from elapsed time at read/update, never by a scheduled job.**
A cron that "ages" every profile nightly makes the result depend on whether the
job ran, which is untestable and silently wrong after an outage. Here the same
profile at the same timestamp always yields the same weights.

**Explicit preferences outrank inferred ones and are never decayed.** Somebody
who typed "I hate country" has said something more durable than fifty implicit
signals, and §7.2 requires that ordering.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Optional

PROFILE_VERSION_ALGORITHM = "preference-profile-v1"

# --- tuning constants, all named so a change is a visible decision ----------

# Asymmetric by design (see the module docstring). Like pulls harder than
# dislike pushes.
LIKE_STRENGTH = 0.20
DISLIKE_STRENGTH = 0.08
SKIP_STRENGTH = 0.04
PLAY_STRENGTH = 0.06
EXPORT_STRENGTH = 0.25  # the strongest implicit signal: they kept it

# A skip only counts as a negative when the user barely heard the track. Past
# this fraction they listened to most of it, and skipping is just "next".
SKIP_NEGATIVE_MAX_FRACTION = 0.35

# How long an inferred affinity takes to lose half its strength. 30 days is
# slow enough that a month-old taste still shapes results and fast enough that
# a phase someone has moved on from stops dominating.
DECAY_HALF_LIFE_DAYS = 30.0

# Affinities are clamped so no single dimension can dominate the ranker, and so
# a long run of likes cannot make a weight unbounded.
AFFINITY_MIN = -1.0
AFFINITY_MAX = 1.0

# Below this an affinity is dropped entirely rather than kept as noise -- it
# keeps the stored profile small and readable, which is the point of an
# interpretable profile.
AFFINITY_PRUNE_THRESHOLD = 0.02

# §7.3 / §7.2: discovery mode controls how strongly the profile influences
# ranking. `adventurous` deliberately *reduces* personal-taste weight -- that is
# the echo-chamber lever, and it belongs here rather than in the ranker so that
# one number explains the whole behaviour.
DISCOVERY_TASTE_WEIGHT = {
    "safe": 1.4,
    "balanced": 1.0,
    "adventurous": 0.55,
}

DEFAULT_DISCOVERY_MODE = "balanced"

# Actions we accept. Anything else is ignored rather than guessed at.
POSITIVE_ACTIONS = {"like", "play", "export"}
NEGATIVE_ACTIONS = {"dislike", "skip"}
KNOWN_ACTIONS = POSITIVE_ACTIONS | NEGATIVE_ACTIONS

_ACTION_STRENGTH = {
    "like": LIKE_STRENGTH,
    "play": PLAY_STRENGTH,
    "export": EXPORT_STRENGTH,
    "dislike": -DISLIKE_STRENGTH,
    "skip": -SKIP_STRENGTH,
}


@dataclass
class Profile:
    """An interpretable preference profile.

    Every field is readable by a human and explainable to a user, which is a
    requirement of §7.2 rather than a nicety: the app has to be able to say
    *why* it recommended something.
    """

    version: int = 0
    genres: dict[str, float] = field(default_factory=dict)
    artists: dict[str, float] = field(default_factory=dict)
    # Explicit statements from onboarding or settings. Higher confidence than
    # anything inferred, and never decayed.
    explicit_genres: dict[str, float] = field(default_factory=dict)
    energy_mean: Optional[float] = None
    energy_count: int = 0
    discovery_mode: str = DEFAULT_DISCOVERY_MODE
    evidence_count: int = 0
    updated_at: Optional[str] = None
    algorithm: str = PROFILE_VERSION_ALGORITHM

    # -- serialization ------------------------------------------------------

    @classmethod
    def from_dict(cls, payload: Optional[dict[str, Any]]) -> "Profile":
        payload = payload or {}
        return cls(
            version=int(payload.get("version") or 0),
            genres=_clean_affinities(payload.get("genres")),
            artists=_clean_affinities(payload.get("artists")),
            explicit_genres=_clean_affinities(payload.get("explicit_genres")),
            energy_mean=_opt_float(payload.get("energy_mean")),
            energy_count=int(payload.get("energy_count") or 0),
            discovery_mode=(payload.get("discovery_mode") or DEFAULT_DISCOVERY_MODE),
            evidence_count=int(payload.get("evidence_count") or 0),
            updated_at=payload.get("updated_at"),
            algorithm=payload.get("algorithm") or PROFILE_VERSION_ALGORITHM,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "genres": dict(sorted(self.genres.items())),
            "artists": dict(sorted(self.artists.items())),
            "explicit_genres": dict(sorted(self.explicit_genres.items())),
            "energy_mean": self.energy_mean,
            "energy_count": self.energy_count,
            "discovery_mode": self.discovery_mode,
            "evidence_count": self.evidence_count,
            "updated_at": self.updated_at,
            "algorithm": self.algorithm,
        }

    # -- the view the recommendation graph consumes -------------------------

    def to_graph_profile(self, discovery_mode: Optional[str] = None) -> dict[str, Any]:
        """Shape the graph's `load_or_accept_user_profile` already understands.

        Deliberately the same contract the guest profile uses, so a signed-in
        profile and a guest profile are interchangeable everywhere downstream
        and no node needs to know which it has.
        """
        mode = discovery_mode or self.discovery_mode or DEFAULT_DISCOVERY_MODE
        taste = DISCOVERY_TASTE_WEIGHT.get(mode, 1.0)
        # A profile with no evidence must not claim taste weight -- that was the
        # §4.7 bug where an empty profile silently zeroed a real signal.
        personal = round(taste * min(1.0, self.evidence_count / 5.0), 3)
        return {
            "profile_type": "user" if self.evidence_count else "guest",
            "version": self.version,
            "discovery_mode": mode,
            "weights": {
                "text_relevance": 1.0,
                "personal_taste": personal,
                "provider_taste": round(personal * 0.5, 3),
            },
            "preferred_genres": self.top_genres(),
            "avoided_genres": self.avoided_genres(),
            "preferred_artists": [name for name, _ in _ranked(self.artists)[:8]],
            "energy_target": self.energy_mean,
        }

    def effective_genres(self) -> dict[str, float]:
        """Inferred affinities with explicit statements layered over the top.

        An explicit entry **replaces** the inferred one rather than being ranked
        alongside it. That distinction is the whole of §7.2's "explicit
        preferences ... have higher confidence than inferred signals", and
        getting it wrong is subtle: an earlier version listed explicit positives
        first and then appended inferred positives that were not already in that
        list — so a genre the user had explicitly *rejected* was not in the
        positives list, was therefore not excluded, and came straight back as a
        recommendation. Someone who states "no country" and is then recommended
        country has been ignored in the most visible way available.
        """
        merged = dict(self.genres)
        merged.update(self.explicit_genres)
        return merged

    def top_genres(self, limit: int = 8) -> list[str]:
        """Preferred genres, explicit statements taking precedence."""
        explicit_positive = {n for n, s in self.explicit_genres.items() if s > 0}
        ranked = _ranked(self.effective_genres())
        # Explicit positives lead, then inferred positives.
        first = [n for n, s in ranked if s > 0 and n in explicit_positive]
        rest = [n for n, s in ranked if s > 0 and n not in explicit_positive]
        return (first + rest)[:limit]

    def avoided_genres(self, limit: int = 8) -> list[str]:
        return [
            name for name, score in _ranked(self.effective_genres(), reverse=False)
            if score < -0.1
        ][:limit]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _opt_float(value: Any) -> Optional[float]:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _clean_affinities(raw: Any) -> dict[str, float]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, float] = {}
    for key, value in raw.items():
        name = _normalize_label(key)
        number = _opt_float(value)
        if name and number is not None:
            out[name] = _clamp(number)
    return out


def _normalize_label(value: Any) -> str:
    """Lower-cased, whitespace-collapsed. Keeps 'Indie Folk' and 'indie  folk'
    from becoming two independent affinities that each learn half the signal."""
    return " ".join(str(value or "").strip().lower().split())


def _clamp(value: float) -> float:
    return max(AFFINITY_MIN, min(AFFINITY_MAX, value))


def _ranked(scores: dict[str, float], reverse: bool = True) -> list[tuple[str, float]]:
    # Sorted by score, then by name: without the name tie-break, two genres with
    # equal affinity could swap order between runs and make the profile
    # non-deterministic in exactly the way §7.2 forbids.
    return sorted(scores.items(), key=lambda kv: (-kv[1] if reverse else kv[1], kv[0]))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_time(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Decay
# ---------------------------------------------------------------------------


def decay_factor(previous: Optional[str], now: Optional[datetime] = None) -> float:
    """Exponential decay over elapsed time. 1.0 when no time has passed."""
    started = _parse_time(previous)
    if started is None:
        return 1.0
    elapsed = (now or _now()) - started
    days = max(0.0, elapsed / timedelta(days=1))
    if days <= 0:
        return 1.0
    return 0.5 ** (days / DECAY_HALF_LIFE_DAYS)


def apply_decay(profile: Profile, now: Optional[datetime] = None) -> Profile:
    """Age inferred affinities toward zero. Explicit ones are untouched.

    Applied at update time rather than by a scheduled job: a cron makes the
    stored value depend on whether the job ran, which is untestable and quietly
    wrong after any outage.
    """
    factor = decay_factor(profile.updated_at, now)
    if factor >= 0.999:
        return profile
    profile.genres = _prune({k: v * factor for k, v in profile.genres.items()})
    profile.artists = _prune({k: v * factor for k, v in profile.artists.items()})
    return profile


def _prune(scores: dict[str, float]) -> dict[str, float]:
    return {
        k: round(_clamp(v), 4)
        for k, v in scores.items()
        if abs(v) >= AFFINITY_PRUNE_THRESHOLD
    }


# ---------------------------------------------------------------------------
# The update rule
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FeedbackSignal:
    """One interaction, already resolved to the features it carries."""

    action: str
    genres: tuple[str, ...] = ()
    artists: tuple[str, ...] = ()
    energy: Optional[float] = None
    # Skip only counts as negative when the user barely heard the track.
    played_fraction: Optional[float] = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FeedbackSignal":
        genres = payload.get("genres") or ([payload["genre"]] if payload.get("genre") else [])
        artists = payload.get("artists") or ([payload["artist"]] if payload.get("artist") else [])
        return cls(
            action=_normalize_label(payload.get("action")),
            genres=tuple(_normalize_label(g) for g in _as_iter(genres) if _normalize_label(g)),
            artists=tuple(_normalize_label(a) for a in _as_iter(artists) if _normalize_label(a)),
            energy=_opt_float(payload.get("energy")),
            played_fraction=_opt_float(payload.get("played_fraction")),
        )


def _as_iter(value: Any) -> Iterable[Any]:
    if isinstance(value, (list, tuple, set)):
        return value
    return [value] if value else []


def effective_strength(signal: FeedbackSignal) -> float:
    """The signed weight this signal contributes, or 0.0 when it carries none.

    A skip is the interesting case, and the reason this is a function rather
    than a lookup: `skip` at 3% of a track is a rejection, `skip` at 80% is a
    completed listen with an impatient finger. Treating both as a negative is
    how a profile learns to dislike music the user actually finished.
    """
    if signal.action not in KNOWN_ACTIONS:
        return 0.0
    if signal.action == "skip":
        if signal.played_fraction is None:
            # No context, so §7.2's "only when context supports that
            # interpretation" is not satisfied. Contributes nothing.
            return 0.0
        if signal.played_fraction > SKIP_NEGATIVE_MAX_FRACTION:
            return 0.0
    return _ACTION_STRENGTH.get(signal.action, 0.0)


def update(
    profile: Profile,
    signal: FeedbackSignal,
    *,
    now: Optional[datetime] = None,
    discovery_mode: Optional[str] = None,
) -> Profile:
    """Apply one feedback event. Always returns a profile; never raises.

    The version increments **only when something actually changed**. A version
    that moves on every request is not a version, it is a counter, and it makes
    "did the profile change?" unanswerable — which the Phase 7 gate asks
    directly ("a Like or Dislike ... updates the profile version").
    """
    moment = now or _now()
    profile = apply_decay(profile, moment)

    strength = effective_strength(signal)
    if strength == 0.0:
        # Recorded as seen but not learned from. The event still exists in
        # `feedback_events` -- this only decides whether it moved any weight.
        if discovery_mode and discovery_mode != profile.discovery_mode:
            profile.discovery_mode = discovery_mode
            profile.version += 1
            profile.updated_at = moment.isoformat()
        return profile

    for genre in signal.genres:
        profile.genres[genre] = _clamp(profile.genres.get(genre, 0.0) + strength)
    for artist in signal.artists:
        # Artist affinity moves faster than genre: naming an artist is a much
        # narrower statement than naming a genre, so one like says more.
        profile.artists[artist] = _clamp(profile.artists.get(artist, 0.0) + strength * 1.5)

    if signal.energy is not None and strength > 0:
        # Running mean over liked tracks only. A disliked track's energy says
        # nothing about the energy someone wants -- they may have disliked it
        # for its genre, its vocals or its era.
        total = (profile.energy_mean or 0.0) * profile.energy_count + signal.energy
        profile.energy_count += 1
        profile.energy_mean = round(total / profile.energy_count, 4)

    profile.genres = _prune(profile.genres)
    profile.artists = _prune(profile.artists)
    profile.evidence_count += 1
    profile.version += 1
    profile.updated_at = moment.isoformat()
    if discovery_mode:
        profile.discovery_mode = discovery_mode
    return profile


def set_explicit_genres(
    profile: Profile, genres: dict[str, float], *, now: Optional[datetime] = None
) -> Profile:
    """Record stated preferences. These outrank inference and never decay."""
    cleaned = _clean_affinities(genres)
    if cleaned == profile.explicit_genres:
        return profile
    profile.explicit_genres = cleaned
    profile.version += 1
    profile.updated_at = (now or _now()).isoformat()
    return profile


# ---------------------------------------------------------------------------
# Guest migration (PERS-003)
# ---------------------------------------------------------------------------


def merge_guest_into_user(user: Profile, guest: Profile, *, now: Optional[datetime] = None) -> Profile:
    """Fold a guest profile into a user's on sign-in.

    The user's own history wins where the two disagree — they have been
    themselves for longer than they have been this browser session. Guest
    evidence is added at reduced weight rather than averaged in, because a
    guest session is short and unverified, and letting it overwrite a long
    history would make signing in feel like losing your profile.
    """
    moment = now or _now()
    if not guest.evidence_count:
        return user

    for source, target, scale in (
        (guest.genres, user.genres, 0.5),
        (guest.artists, user.artists, 0.5),
    ):
        for name, score in source.items():
            target[name] = _clamp(target.get(name, 0.0) + score * scale)

    if guest.energy_mean is not None:
        total = (user.energy_mean or 0.0) * user.energy_count + guest.energy_mean * guest.energy_count
        user.energy_count += guest.energy_count
        user.energy_mean = round(total / user.energy_count, 4) if user.energy_count else None

    user.genres = _prune(user.genres)
    user.artists = _prune(user.artists)
    user.evidence_count += guest.evidence_count
    user.version += 1
    user.updated_at = moment.isoformat()
    return user


def explain(profile: Profile) -> list[str]:
    """Human-readable statements about the profile.

    §7.3 requires unusual recommendations to be explainable, and an
    interpretable profile is worth little if nothing ever reads it aloud.
    """
    lines: list[str] = []
    top = profile.top_genres(3)
    if top:
        lines.append("Leans towards " + ", ".join(top))
    avoided = profile.avoided_genres(3)
    if avoided:
        lines.append("Tends to skip " + ", ".join(avoided))
    # Artists were omitted here at first, so a profile built purely from
    # artist-level feedback reported "not enough signal yet" while holding
    # real affinities -- an explanation that contradicted the profile it
    # was explaining.
    artists = [name for name, score in _ranked(profile.artists)[:3] if score > 0]
    if artists:
        lines.append("Likes " + ", ".join(artists))
    if profile.energy_mean is not None:
        descriptor = "high" if profile.energy_mean > 0.66 else (
            "low" if profile.energy_mean < 0.33 else "moderate"
        )
        lines.append(f"Prefers {descriptor} energy")
    if not lines:
        lines.append("Not enough signal yet — recommendations are unpersonalized")
    return lines
