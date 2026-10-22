"""Alert-rule evaluation and dispatch (§26.2, Phase 5d; registry since Phase 7a)."""

# Importing the detectors registers the built-in event types (FR-AL-003). Later event types
# register from their own modules, imported here too so dispatch and the API always see them.
from app.alerts import detectors as _detectors  # noqa: F401
