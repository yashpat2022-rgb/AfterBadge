"""Extract records and vehicle names using the official NHTSA APIs."""
import asyncio
from urllib.parse import quote

import httpx

BASE = "https://api.nhtsa.gov"
VPIC = "https://vpic.nhtsa.dot.gov/api/vehicles"


async def fetch_results(
    client: httpx.AsyncClient,
    url: str,
    params: dict,
    *,
    results_key: str = "results",
    allow_empty_400: bool = False,
) -> list[dict]:
    response = await client.get(url, params=params)
    if not (allow_empty_400 and response.status_code == 400):
        response.raise_for_status()

    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("Unexpected response format from NHTSA")
    results = payload.get(results_key)

    # These endpoints sometimes return HTTP 400 with a successful, empty lookup.
    if response.status_code == 400:
        count = payload.get("count", payload.get("Count"))
        message = payload.get("message", payload.get("Message"))
        if results == [] and count == 0 and message == "Results returned successfully":
            return []
        response.raise_for_status()

    if not isinstance(results, list) or not all(isinstance(row, dict) for row in results):
        raise ValueError("Unexpected response format from NHTSA")
    return results


async def fetch_vehicle_data(make: str, model: str, year: int) -> tuple[list[dict], list[dict]]:
    params = {"make": make, "model": model, "modelYear": year}
    async with httpx.AsyncClient(base_url=BASE, timeout=30, follow_redirects=True) as client:
        complaints, recalls = await asyncio.gather(
            fetch_results(client, "/complaints/complaintsByVehicle", params, allow_empty_400=True),
            fetch_results(client, "/recalls/recallsByVehicle", params, allow_empty_400=True),
        )
        return complaints, recalls


async def fetch_vehicle_options(year: int, make: str | None = None) -> tuple[list[str], bool]:
    """Merge complaint, recall, and (for models) manufacturer listings."""
    field = "model" if make else "make"
    path = f"/products/vehicle/{field}s"
    params = {"modelYear": year}
    if make:
        params["make"] = make

    async with httpx.AsyncClient(base_url=BASE, timeout=12, follow_redirects=True) as client:
        requests = [
            fetch_results(client, path, {**params, "issueType": issue_type})
            for issue_type in ("c", "r")
        ]
        fields = [field, field]
        if make:
            make_path = quote(make.lower(), safe="")
            url = f"{VPIC}/GetModelsForMakeYear/make/{make_path}/modelyear/{year}"
            requests.append(fetch_results(client, url, {"format": "json"}, results_key="Results"))
            fields.append("Model_Name")
        responses = await asyncio.gather(*requests, return_exceptions=True)

    failures = [response for response in responses if isinstance(response, BaseException)]
    if len(failures) == len(responses):
        raise failures[0]

    options = set()
    for response, key in zip(responses, fields):
        if isinstance(response, list):
            for row in response:
                name = row.get(key)
                if isinstance(name, str) and name.strip():
                    options.add(" ".join(name.upper().split()))
    return sorted(options), bool(failures)
