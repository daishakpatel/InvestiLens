"""Alert event-type registry (Phase 7a, FR-AL-001..003, FR-AL-018). Offline."""

from __future__ import annotations

import json

import pytest

from app.alerts import registry
from app.citation.advice import contains_advice


def test_registry_holds_the_legacy_detectors() -> None:
    """FR-AL-003: the pre-7a alert kinds are all registered."""
    keys = {t.key for t in registry.all_types()}
    assert {"new_filing", "price_move", "new_risk_factor", "news_category"} <= keys


@pytest.mark.parametrize("event_type", registry.all_types(), ids=lambda t: t.key)
def test_every_detector_sample_is_free_of_advice(event_type: registry.AlertEventType) -> None:
    """FR-AL-018 / LGL-006: notification text never contains investment advice."""
    sample = event_type.sample
    assert not contains_advice(sample.title)
    assert not contains_advice(sample.body)
    assert sample.source_ids, "every event carries backend-issued evidence ids"
    # Keys never collide across types: each is prefixed by its type, or is itself a
    # type-unique evidence ID (`red_flag` events use the flag's `redflag:` source ID, FR-RF-011),
    # or a key the task fixed (`guidance_miss` keys `guidance_outcome:{id}`, FR-GD-013).
    own_prefix = {"guidance_miss": "guidance_outcome:"}.get(event_type.key, f"{event_type.key}:")
    assert sample.event_key.startswith(own_prefix) or (sample.event_key in sample.source_ids)


@pytest.mark.parametrize("event_type", registry.all_types(), ids=lambda t: t.key)
def test_params_schema_is_json_schema_with_defaults(event_type: registry.AlertEventType) -> None:
    """FR-AL-001: `{}` is always valid (defaults), and the schema serialises for the API."""
    event_type.params_schema.model_validate({})
    schema = event_type.params_schema.model_json_schema()
    assert schema["type"] == "object"
    json.dumps(schema)


def test_registering_a_key_twice_fails() -> None:
    existing = registry.all_types()[0]
    with pytest.raises(ValueError, match="already registered"):
        registry.register(existing)
