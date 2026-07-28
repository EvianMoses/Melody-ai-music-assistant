"""Bind the real `shared_lib` before pytest's rootdir path insertion.

Same fix as rag-service/conftest.py, needed here from §5.5 onward: this service
now imports `contracts.*`, which only resolves with the repository root on
sys.path -- and that root also contains a `shared_lib/` directory (the packaging
folder, not the package), which binds as an empty namespace package and shadows
the installed melody-shared-lib. Importing it here, at conftest load, resolves
the real package first.
"""

import shared_lib  # noqa: F401  -- imported for its import side effect only

# Order matters: shared_lib above, *then* the root that would shadow it. In the
# container `contracts/` is copied next to main.py so this is a test-only need.
import sys
from pathlib import Path

_ROOT = str(Path(__file__).resolve().parent.parent)
if _ROOT not in sys.path:
    sys.path.append(_ROOT)

import pytest  # noqa: E402  -- must follow the sys.path fix above


@pytest.fixture(autouse=True)
def _no_live_database(monkeypatch):
    """Keep the suite offline: no test may reach a real database.

    Found by running it, not by reading it. Once `_record_quota_usage` began
    persisting rows (N8N-REAL-004), the adapter tests -- which call it dozens of
    times with fake HTTP responses -- wrote **24 rows of fictional quota usage
    into the development database** on a single run. Inside the container only,
    where POSTGRES_* is configured, so it looked clean on the host.

    That data is worse than useless: WF-008 reads this table to decide whether
    the YouTube budget is nearly spent, and a test run would have made it report
    consumption that never happened.

    Only the URL resolver is patched, so tests that deliberately inject a SQLite
    session factory (the export tests) are unaffected -- an injected factory is
    consulted first.
    """
    from app import db

    def _refuse() -> str:
        raise RuntimeError("database disabled in tests (conftest._no_live_database)")

    db.reset_for_tests(None)
    monkeypatch.setattr(db, "_resolve_database_url", _refuse)
    yield
    db.reset_for_tests(None)
