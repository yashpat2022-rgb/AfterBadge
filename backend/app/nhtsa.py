"""Extract records using the official NHTSA vehicle APIs."""
import asyncio
import httpx

BASE = "https://api.nhtsa.gov"

async def fetch_vehicle_data(make: str, model: str, year: int) -> tuple[list[dict], list[dict]]:
    params = {"make": make, "model": model, "modelYear": year}
    async with httpx.AsyncClient(base_url=BASE, timeout=30, follow_redirects=True) as client:
        async def request(path: str) -> list[dict]:
            response = await client.get(path, params=params)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
                raise ValueError("Unexpected response format from NHTSA")
            return payload["results"]
        complaints, recalls = await asyncio.gather(
            request("/complaints/complaintsByVehicle"),
            request("/recalls/recallsByVehicle"),
        )
        return complaints, recalls
