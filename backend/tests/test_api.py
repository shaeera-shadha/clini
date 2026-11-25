from __future__ import annotations

import json
from pathlib import Path

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


def test_baseline_endpoint_returns_scored_claims() -> None:
    res = client.post("/baseline", json={"sample_id": "rash"})
    assert res.status_code == 200
    body = res.json()
    assert body["claims"] and body["segments"] and body["sentences"]
    flagged = [c for c in body["claims"] if c["status"] == "flagged"]
    assert any("dermatitis" in c["text"].lower() for c in flagged)


def test_eval_endpoint_serves_saved_report_or_explains(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import app.main as main

    monkeypatch.setattr(main, "EVAL_REPORT", tmp_path / "missing.json")
    missing = client.get("/eval")
    assert missing.status_code == 404
    assert "python -m eval.run_eval" in missing.json()["message"]

    report = tmp_path / "latest.json"
    report.write_text(
        json.dumps(
            {
                "run_at": "2026-11-25T00:00:00+00:00",
                "mode": "mock",
                "fixture_source": "Hand-made mock fixtures, not model output",
                "models": {},
                "prompt_versions": {},
                "definitions": {},
                "labels": {},
                "systems": {},
                "verifier_audit": {},
                "samples": [],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(main, "EVAL_REPORT", report)
    assert client.get("/eval").json()["mode"] == "mock"
