"""Ensure `shared_lib` resolves before pytest's rootdir path insertion.

Without a conftest.py present, collecting `test_smoke.py` from this directory
fails with `ImportError: cannot import name 'AppError' from 'shared_lib'
(unknown location)` -- pytest inserts the rootdir into sys.path[0] at
collection time, and `shared_lib` gets bound as an empty namespace package
before the editable-install finder for melody-shared-lib gets a chance to
resolve it. Importing it here, at conftest load (which happens first), binds
the real package. `python -c "import main"` from this directory always worked,
which is what makes the failure look mysterious.

The other services don't need this because their own packages (`app/`) are
imported first and pull shared_lib in along the way.
"""

import shared_lib  # noqa: F401  -- imported for its import side effect only
