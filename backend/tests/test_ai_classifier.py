
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from app import ai_classifier


def test_classifies_multiple_problems(monkeypatch):
    # Create a fake Gemini client
    fake_client = MagicMock()

    # Pretend Gemini returned two detected problems
    fake_client.models.generate_content.return_value.text = """
    {
        "issues": [
            {
                "category": "engine_stall",
                "evidence": "engine stalled"
            },
            {
                "category": "brake_failure",
                "evidence": "brakes stopped working"
            }
        ]
    }
    """

    # Use the fake client instead of the real Gemini API
    monkeypatch.setattr(
        ai_classifier,
        "create_gemini_client",
        lambda: fake_client
    )

    # Run our classifier
    complaint = "The engine stalled and the brakes stopped working."
    result = ai_classifier.classify_complaint(complaint)

    # Check that both problems were identified
    assert len(result["issues"]) == 2
    assert result["issues"][0]["category"] == "engine_stall"
    assert result["issues"][1]["category"] == "brake_failure"



def test_rejects_invented_evidence(monkeypatch):
    fake_client = MagicMock()

    # Simulate Gemini returning one real and one invented issue
    fake_client.models.generate_content.return_value.text = """
    {
        "issues": [
            {
                "category": "engine_oil_leak",
                "evidence": "engine leaking oil"
            },
            {
                "category": "transmission_failure",
                "evidence": "transmission completely failed"
            }
        ]
    }
    """

    monkeypatch.setattr(
        ai_classifier,
        "create_gemini_client",
        lambda: fake_client
    )

    complaint = "My engine leaking oil was noticed yesterday."

    result = ai_classifier.classify_complaint(complaint)

    # Keep the issue supported by the complaint
    assert len(result["issues"]) == 1
    assert result["issues"][0]["category"] == "engine_oil_leak"



def test_empty_complaint_skips_gemini(monkeypatch):
    # Gemini should never be called for an empty complaint
    def fail_if_called():
        raise AssertionError("Gemini should not be called")

    monkeypatch.setattr(
        ai_classifier,
        "create_gemini_client",
        fail_if_called
    )

    result = ai_classifier.classify_complaint("   ")

    assert result == {"issues": []}



def test_ai_endpoint_disabled_by_default(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app

    # Make sure AI is disabled
    monkeypatch.delenv("AFTERBADGE_ENABLE_AI", raising=False)

    # Try calling our AI endpoint
    client = TestClient(app)
    response = client.post("/api/complaints/10459314/analyze")

    # The endpoint should reject the request
    assert response.status_code == 403
    assert response.json()["detail"] == "AI analysis is disabled."



def test_ai_endpoint_enabled(monkeypatch):
    from types import SimpleNamespace
    from fastapi.testclient import TestClient
    from app import main
    from app.database import get_db

    # Enable AI for this test only
    monkeypatch.setenv("AFTERBADGE_ENABLE_AI", "true")
    monkeypatch.setitem(main.ai_request_count, "used", 0)


    # Create a fake database complaint
    fake_db = MagicMock()
    fake_db.scalar.return_value = SimpleNamespace(
        summary="The engine stalled while driving.",
        components="ENGINE, UNKNOWN OR OTHER",
    )

    # Create a fake Gemini classification
    def fake_classify(complaint):
        assert complaint == "The engine stalled while driving."
        return {
            "issues": [
                {
                    "category": "engine_stall",
                    "evidence": "engine stalled",
                    "component": "engine",
                }
            ]
        }

    # Replace the real AI function
    monkeypatch.setattr(main, "classify_complaint", fake_classify)

    # Replace the database for this test
    def get_fake_db():
        yield fake_db

    main.app.dependency_overrides[get_db] = get_fake_db

    try:
        client = TestClient(main.app)


        for _ in range(10):
            main.ai_result_cache.pop("10459314", None)
            response = client.post("/api/complaints/10459314/analyze")
            assert response.status_code == 200

        # Cached result should work without another Gemini request
        cached = client.post("/api/complaints/10459314/analyze")
        assert cached.status_code == 200
        assert cached.json() == response.json()
        assert main.ai_request_count["used"] == 10




        assert response.status_code == 200

        result = response.json()

        assert result["odi_number"] == "10459314"
        assert len(result["issues"]) == 1
        assert result["issues"][0]["category"] == "engine_stall"
        assert result["reported_components"] == ["ENGINE", "UNKNOWN OR OTHER"]
        assert result["issues"][0]["component"] == "engine"

        # The 11th request should be blocked
        main.ai_result_cache.pop("10459314", None)
        blocked = client.post("/api/complaints/10459314/analyze")
        assert blocked.status_code == 429


    finally:
        # Restore the original database dependency
        main.app.dependency_overrides.pop(get_db, None)


CASES = json.loads((Path(__file__).parent / "fixtures" / "complaint_cases.json").read_text())


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_labeled_case_keeps_component_and_quote(monkeypatch, case):
    expected = case["expected_issues"]
    for issue in expected:
        assert issue["evidence"] in case["complaint"]
        assert issue["component"] in ai_classifier.COMPONENTS
    if "odi_number" in case:
        assert case["source_url"].endswith("=" + case["odi_number"])

    fake_client = MagicMock()
    fake_client.models.generate_content.return_value.text = json.dumps({"issues": expected})
    monkeypatch.setattr(ai_classifier, "create_gemini_client", lambda: fake_client)

    assert ai_classifier.classify_complaint(case["complaint"]) == {"issues": expected}


def test_unlisted_component_becomes_unknown(monkeypatch):
    fake_client = MagicMock()
    fake_client.models.generate_content.return_value.text = json.dumps({"issues": [
        {"category": "loud_bang", "evidence": "heard a bang", "component": "window motor"},
        {"category": "engine_stall", "evidence": "engine stalled"},
    ]})
    monkeypatch.setattr(ai_classifier, "create_gemini_client", lambda: fake_client)

    result = ai_classifier.classify_complaint("I heard a bang, then the engine stalled.")
    assert [issue["component"] for issue in result["issues"]] == ["unknown", "unknown"]
