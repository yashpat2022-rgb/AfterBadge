"""Regression tests for the vehicle dropdown and empty NHTSA results."""
import asyncio

import httpx
import pytest

from app import nhtsa


def mock_nhtsa(monkeypatch, handler):
    client = httpx.AsyncClient
    transport = httpx.MockTransport(handler)

    def build_client(**kwargs):
        return client(transport=transport, **kwargs)

    monkeypatch.setattr(nhtsa.httpx, "AsyncClient", build_client)


@pytest.mark.parametrize("model,missing,fields", [
    ("330I", "complaints", {"count": 0, "message": "Results returned successfully"}),
    ("3 SERIES", "recalls", {"Count": 0, "Message": "Results returned successfully"}),
])
def test_no_data_does_not_discard_other_results(monkeypatch, model, missing, fields):
    def handler(request):
        assert request.url.params["model"] == model
        if request.url.path.startswith(f"/{missing}/"):
            return httpx.Response(400, json={**fields, "results": []})
        return httpx.Response(200, json={"results": [{"example": "existing record"}]})

    mock_nhtsa(monkeypatch, handler)
    complaints, recalls = asyncio.run(nhtsa.fetch_vehicle_data("BMW", model, 2021))
    assert len(complaints) == (0 if missing == "complaints" else 1)
    assert len(recalls) == (0 if missing == "recalls" else 1)


def test_actual_upstream_failure_is_reported(monkeypatch):
    def handler(request):
        return httpx.Response(400, json={"count": 0, "message": "Invalid request", "results": []})

    mock_nhtsa(monkeypatch, handler)
    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(nhtsa.fetch_vehicle_data("BMW", "330I", 2021))


def test_models_include_catalog_names_and_trims(monkeypatch):
    def handler(request):
        if request.url.host == "vpic.nhtsa.dot.gov":
            assert request.url.path.endswith("/make/bmw/modelyear/2021")
            return httpx.Response(200, json={"Results": [{"Model_Name": "330i"}]})
        assert request.url.params["modelYear"] == "2021"
        assert request.url.params["make"] == "BMW"
        return httpx.Response(200, json={"results": [{"model": "3 SERIES"}]})

    mock_nhtsa(monkeypatch, handler)
    options, incomplete = asyncio.run(nhtsa.fetch_vehicle_options(2021, "BMW"))
    assert options == ["3 SERIES", "330I"]
    assert incomplete is False
