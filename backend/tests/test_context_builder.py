import pytest

from backend.services import context_builder


def test_build_context_for_real_incident(real_db_readonly):
    row = real_db_readonly.execute("SELECT incident_id FROM incidents LIMIT 1").fetchone()
    incident_id = row["incident_id"]

    ctx = context_builder.build_incident_context(real_db_readonly, incident_id)

    assert ctx["incident"]["incident_id"] == incident_id
    assert ctx["facility"] is not None
    assert isinstance(ctx["related_incidents"], list)
    assert isinstance(ctx["controls"], list)
    assert isinstance(ctx["existing_corrective_actions"], list)
    # bounds are respected
    assert len(ctx["related_incidents"]) <= 8
    assert len(ctx["controls"]) <= 10
    assert len(ctx["existing_corrective_actions"]) <= 8


def test_build_context_unknown_incident_raises(real_db_readonly):
    with pytest.raises(context_builder.IncidentNotFoundError):
        context_builder.build_incident_context(real_db_readonly, "INC-NOPE-9999")


def test_context_is_json_serializable(real_db_readonly):
    row = real_db_readonly.execute("SELECT incident_id FROM incidents LIMIT 1").fetchone()
    ctx = context_builder.build_incident_context(real_db_readonly, row["incident_id"])
    text = context_builder.context_to_prompt_json(ctx)
    assert row["incident_id"] in text
