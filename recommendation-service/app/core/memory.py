"""Conversational memory for the agent.

Melody had none. Every message was an independent recommendation request, and
the three failures that produced were all the same failure wearing different
clothes: a correction was treated as a search query, a meta-question was matched
lexically, and there was nothing to inspect to find out why.

**Storage policy: keep everything. Send a window.**

Disk is not the constraint -- a turn is ~1.5 KB, so a thousand users at twenty
turns each is about 30 MB. What costs money is replaying turns into the model on
every request: ten turns is roughly 1,500 extra input tokens *per call*. So the
store is append-only and complete, and `load_window` is where the bounded
context policy lives. Changing the policy never means losing history.

**Owner is user OR guest, never both** -- mirroring `profile_store`, and for the
same reason: someone who has not signed in still holds a conversation.

**Failure policy: best effort, loudly logged.** A memory write must never fail
the reply the user is waiting for. Losing a turn degrades the next answer;
raising here would destroy this one.
"""

from __future__ import annotations

import logging
import os
import uuid
from contextlib import contextmanager
from typing import Any, Optional

logger = logging.getLogger("melody.recommendation.memory")

_engine = None
_session_factory = None

# How many turns are replayed to the model. 24 is twelve exchanges -- deep
# enough that a correction made several messages ago is still in view, which is
# the failure that started this work ("Coldplay is not a new artist" was not
# just unheard, it was unrememberable). Turns beyond this stay in the database
# and are simply not sent; raising the window later loses nothing.
#
# Cost, so the number is a decision rather than a guess: ~150 tokens/turn means
# a full window is ~3,600 input tokens, about $0.003 per request on Haiku.
DEFAULT_WINDOW_TURNS = 24

# Hard cap on a single stored turn. A pasted wall of text should not become a
# permanent tax on every subsequent prompt in the conversation.
MAX_TURN_CHARS = 4000


def _database_url() -> str:
    """Same resolution order as profile_store: POSTGRES_* first, DATABASE_URL second."""
    user = os.getenv("POSTGRES_USER", "")
    password = os.getenv("POSTGRES_PASSWORD", "")
    host = os.getenv("POSTGRES_HOST", "")
    port = os.getenv("POSTGRES_PORT", "5432")
    database = os.getenv("POSTGRES_DB", "")
    if user and database and host:
        return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{database}"

    url = (os.getenv("DATABASE_URL") or "").strip()
    if url:
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return ""


def _factory():
    global _engine, _session_factory
    if _session_factory is not None:
        return _session_factory
    url = _database_url()
    if not url:
        return None
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        _engine = create_engine(url, pool_pre_ping=True, pool_size=3, max_overflow=2)
        _session_factory = sessionmaker(bind=_engine, expire_on_commit=False)
    except Exception:
        logger.warning("memory_unavailable", exc_info=True)
        return None
    return _session_factory


@contextmanager
def _session():
    factory = _factory()
    if factory is None:
        yield None
        return
    session = factory()
    try:
        yield session
    finally:
        session.close()


def available() -> bool:
    return _factory() is not None


def reset_for_tests(factory: Optional[Any] = None) -> None:
    global _session_factory, _engine
    _session_factory = factory
    if factory is None:
        _engine = None


def _as_uuid(value: Any) -> Optional[uuid.UUID]:
    """Guest ids are not always UUIDs (the smoke suite sends 'guest-smoke-001'),
    so a non-UUID is an ordinary case rather than an error."""
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return None


def _owner(user_id: Any, guest_id: Any) -> tuple[Optional[uuid.UUID], Optional[uuid.UUID]]:
    """Resolve exactly one owner. A signed-in user always wins over a guest id:
    the browser keeps sending its guest cookie after sign-in, and splitting one
    person's conversation across two owners is how memory appears to 'forget'."""
    user = _as_uuid(user_id)
    if user is not None:
        return user, None
    return None, _as_uuid(guest_id)


def load_window(
    *,
    user_id: Any = None,
    guest_id: Any = None,
    limit: int = DEFAULT_WINDOW_TURNS,
) -> list[dict[str, str]]:
    """The last `limit` turns, oldest first, as [{role, content}].

    Oldest-first because that is the order a model expects a transcript in, and
    reversing it at the call site is the kind of detail that gets forgotten once
    and then silently inverts the conversation.

    Never raises: a memory failure degrades the next answer rather than
    destroying this one.
    """
    owner_user, owner_guest = _owner(user_id, guest_id)
    if owner_user is None and owner_guest is None:
        return []

    try:
        from sqlalchemy import text as sql_text

        with _session() as session:
            if session is None:
                return []
            column = "user_id" if owner_user else "guest_session_id"
            rows = session.execute(
                sql_text(
                    f"SELECT role, content FROM conversation_turns "
                    f"WHERE {column} = :owner "
                    "ORDER BY turn_index DESC, created_at DESC LIMIT :limit"
                ),
                {"owner": owner_user or owner_guest, "limit": max(0, limit)},
            ).all()
        return [{"role": r[0], "content": r[1]} for r in reversed(rows)]
    except Exception:  # noqa: BLE001
        logger.warning("memory_load_failed", exc_info=True)
        return []


def append_turns(
    turns: list[dict[str, Any]],
    *,
    user_id: Any = None,
    guest_id: Any = None,
    request_id: str = "",
) -> int:
    """Append turns for one owner. Returns the number written (0 on failure).

    `turn_index` continues from whatever is already stored, so ordering survives
    identical timestamps -- two turns written in the same millisecond are common
    when a user message and the reply are saved together.
    """
    owner_user, owner_guest = _owner(user_id, guest_id)
    if (owner_user is None and owner_guest is None) or not turns:
        return 0

    try:
        from sqlalchemy import text as sql_text

        with _session() as session:
            if session is None:
                return 0
            column = "user_id" if owner_user else "guest_session_id"
            owner = owner_user or owner_guest

            next_index = session.execute(
                sql_text(
                    f"SELECT coalesce(max(turn_index), -1) + 1 FROM conversation_turns "
                    f"WHERE {column} = :owner"
                ),
                {"owner": owner},
            ).scalar_one()

            rows = []
            for offset, turn in enumerate(turns):
                content = str(turn.get("content") or "")[:MAX_TURN_CHARS]
                if not content.strip():
                    continue
                rows.append(
                    {
                        "id": str(uuid.uuid4()),
                        "owner": owner,
                        "turn_index": next_index + offset,
                        "role": turn.get("role", "user"),
                        "content": content,
                        "metadata": turn.get("metadata") or {},
                        "request_id": request_id or None,
                    }
                )
            if not rows:
                return 0

            import json as _json

            for row in rows:
                row["metadata"] = _json.dumps(row["metadata"])

            session.execute(
                sql_text(
                    f"INSERT INTO conversation_turns "
                    f"(id, {column}, turn_index, role, content, metadata, request_id) "
                    "VALUES (:id, :owner, :turn_index, :role, :content, "
                    "CAST(:metadata AS jsonb), :request_id)"
                ),
                rows,
            )
            session.commit()
            return len(rows)
    except Exception:  # noqa: BLE001
        logger.warning("memory_append_failed", exc_info=True)
        return 0


def merge_guest_into_user(*, guest_id: Any, user_id: Any) -> int:
    """Re-point a guest's turns at the signed-in user. Returns rows moved.

    The same move `profile.merge_guest_into_user` makes for preferences, and for
    the same reason: signing in should not make the assistant forget the
    conversation you were just having with it.

    The single-owner CHECK means this must set `guest_session_id` to NULL in the
    same statement -- a row with both owners cannot exist.
    """
    owner_user = _as_uuid(user_id)
    owner_guest = _as_uuid(guest_id)
    if owner_user is None or owner_guest is None:
        return 0

    try:
        from sqlalchemy import text as sql_text

        with _session() as session:
            if session is None:
                return 0
            # Continue the user's numbering rather than the guest's, or the
            # merged turns interleave with the user's existing history.
            offset = session.execute(
                sql_text(
                    "SELECT coalesce(max(turn_index), -1) + 1 FROM conversation_turns "
                    "WHERE user_id = :u"
                ),
                {"u": owner_user},
            ).scalar_one()
            moved = session.execute(
                sql_text(
                    "UPDATE conversation_turns "
                    "SET user_id = :u, guest_session_id = NULL, "
                    "    turn_index = turn_index + :offset "
                    "WHERE guest_session_id = :g"
                ),
                {"u": owner_user, "g": owner_guest, "offset": offset},
            ).rowcount
            session.commit()
            if moved:
                logger.info("memory_merged_guest_turns: %s", moved)
            return moved
    except Exception:  # noqa: BLE001
        logger.warning("memory_merge_failed", exc_info=True)
        return 0
