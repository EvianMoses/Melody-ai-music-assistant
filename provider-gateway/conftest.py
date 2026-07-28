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
