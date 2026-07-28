"""Bind the real `shared_lib` before pytest's rootdir path insertion.

Same fix as `rag-service/conftest.py` and `provider-gateway/conftest.py`, needed
here from N8N-REAL-004 onward: this service's tests now import `contracts.*`,
which only resolves with the repository root on sys.path -- and that root also
contains a `shared_lib/` directory (the packaging folder, not the package),
which binds as an empty namespace package and shadows the installed
melody-shared-lib. Importing it here, at conftest load, resolves the real
package first.

In the container `contracts/` is copied next to main.py, so this is a test-only
concern.
"""

import shared_lib  # noqa: F401  -- imported for its import side effect only

# Order matters: shared_lib above, *then* the root that would shadow it.
import sys
from pathlib import Path

_ROOT = str(Path(__file__).resolve().parent.parent)
if _ROOT not in sys.path:
    sys.path.append(_ROOT)

import pytest  # noqa: E402  -- must follow the sys.path fix above


@pytest.fixture(autouse=True)
def _no_live_database(monkeypatch):
    """Keep the suite genuinely offline: no test may reach a real database.

    Not a hypothetical guard. `test_recommendations_run_real_graph` calls the
    endpoint, and once `/recommendations/run` began persisting model usage
    (N8N-REAL-004) that test started **writing rows into the development
    database** -- but only inside the container, where POSTGRES_* is actually
    configured, so it passed on the host and quietly polluted real data in
    Docker. Two junk rows were written before it was noticed.

    Patching the URL resolvers rather than the store functions means the guard
    covers any future endpoint test too, instead of the one that happened to
    exist when the problem was found. Tests that genuinely want persistence
    inject their own session factory, which is consulted first and therefore
    wins over this.
    """
    from app.core import profile_store, usage_store

    monkeypatch.setattr(usage_store, "_database_url", lambda: "")
    monkeypatch.setattr(profile_store, "_database_url", lambda: "")
    usage_store.reset_for_tests(None)
    profile_store.reset_for_tests(None)
    yield
    usage_store.reset_for_tests(None)
    profile_store.reset_for_tests(None)
