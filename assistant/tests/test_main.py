import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient  # noqa: E402
import main  # noqa: E402

api = TestClient(main.app)

def test_health():
    res = api.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

def test_prompt_contains_alert_and_data():
    prompt = main.build_prompt("PodCrashLooping", "exitCode=1")
    assert "PodCrashLooping" in prompt
    assert "exitCode=1" in prompt

def test_resolved_alerts_are_ignored():
    payload = {"alerts": [{"status": "resolved",
                            "labels": {"alertname": "X", "namespace": "demo", "pod": "p"}}]}
    res = api.post("/alert", json=payload)
    assert res.json() == {"queued": 0}

def test_cooldown_blocks_duplicates():
    assert main.should_process("A/demo/pod-1") is True
    assert main.should_process("A/demo/pod-1") is False
