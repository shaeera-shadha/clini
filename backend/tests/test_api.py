from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.main import app

client = TestClient(app)


def parse_sse(body: str) -> list[tuple[str, dict[str, object]]]:
    events = []
    for block in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((lines["event"], json.loads(lines["data"])))
    return events


def test_health_reports_mode_and_models() -> None:
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["mode"] in {"mock", "live"}
    assert body["models"]["extractor"] != body["models"]["verifier"]


def test_samples_list_and_detail() -> None:
    listing = client.get("/samples").json()
    assert {"id": "cough"}.items() <= listing[0].items()
    detail = client.get("/samples/cough").json()
    assert detail["transcript"].startswith("Doctor:")
    missing = client.get("/samples/nope")
    assert missing.status_code == 404
    assert missing.json()["code"] == "unknown_sample"


def test_generate_json_in_mock_mode() -> None:
    res = client.post("/generate", json={"sample_id": "cough"})
    assert res.status_code == 200
    note = res.json()["note"]
    assert len(res.json()["sentences"]) == 36
    # Every item in the note is verified and cites at least one existing sentence.
    ids = {s["id"] for s in res.json()["sentences"]}
    assert note["items"]
    for item in note["items"]:
        assert item["status"] == "verified"
        assert item["evidence"] and set(item["evidence"]) <= ids
    flagged = {f["item"]["text"]: f for f in note["flagged"]}
    assert flagged["Asthma"]["verifier_verdict"] == "unsupported"
    assert flagged["Chest infection"]["verifier_verdict"] == "not_run"
    assert note["meta"]["transcript_hash"]
    assert set(note["meta"]["timings_ms"]) == {"preprocess", "extract", "verify"}


def test_generate_streams_stage_events_then_result() -> None:
    res = client.post(
        "/generate", json={"sample_id": "cough"}, headers={"Accept": "text/event-stream"}
    )
    assert res.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(res.text)
    stages = [(d["stage"], d["state"]) for e, d in events if e == "stage"]
    assert stages == [
        ("preprocess", "running"), ("preprocess", "done"),
        ("extract", "running"), ("extract", "done"),
        ("verify", "running"), ("verify", "done"),
    ]  # fmt: skip
    assert events[-1][0] == "result"


def test_stream_reports_plain_language_error() -> None:
    res = client.post(
        "/generate",
        json={"transcript": "Doctor: Hello.\nPatient: Hi."},
        headers={"Accept": "text/event-stream"},
    )
    event, data = parse_sse(res.text)[-1]
    assert event == "error"
    assert data["code"] == "mock_fixture_missing"
    assert "sample" in str(data["message"])


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ({}, "empty_transcript"),
        ({"transcript": "  "}, "empty_transcript"),
        ({"transcript": "no labels here"}, "no_speakers"),
    ],
)
def test_generate_json_errors(body: dict[str, str], code: str) -> None:
    res = client.post("/generate", json=body)
    assert res.status_code == 422
    assert res.json()["code"] == code


def test_settings_reject_same_model_for_both_roles() -> None:
    with pytest.raises(ValidationError, match="must be different"):
        Settings(extractor_model="m", verifier_model="m", _env_file=None)


def test_settings_require_key_in_live_mode() -> None:
    with pytest.raises(ValidationError, match="GROQ_API_KEY"):
        Settings(llm_mode="live", groq_api_key=None, _env_file=None)
