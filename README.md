# AutoInsight — automotive problem intelligence

A full-stack software engineering portfolio project (v0.2) built around **real government vehicle safety data**, not a car marketplace.

It fetches NHTSA complaints and recall campaigns for a make/model/year, normalizes and deduplicates the results in a SQL database, and serves a React dashboard through a FastAPI backend.

## What works in this starter

- Query official NHTSA complaints and recall endpoints using a vehicle year, make and model.
- Normalize NHTSA component categories, including multi-component complaints.
- Store complaint ODI IDs and recall campaign IDs in SQL with unique constraints to avoid duplicate inserts.
- Display counts, component-level report patterns, original complaint text, and official source links.
- Browse previously imported cars without re-fetching data.
- Compare two saved vehicles side by side by reported component categories, complaint totals, and recall totals.
- Follow a link from each comparison car to inspect original NHTSA records.
- Run offline unit tests using fake API responses.

**This is an MVP, not a production-ready public service.** It includes a localhost-only workflow for triggering manual imports. Disable or protect the sync endpoint before public deployment.

## Requirements

- Python 3.11 or newer
- Node.js 20 or newer and npm
- Internet connection for the NHTSA data requests and initial package installs

## Run it locally

Open two terminal windows from the `autoinsight_starter` folder.

### Terminal 1 — Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate   # macOS/Linux; on Windows use .venv\Scripts\activate
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

Go to http://127.0.0.1:8000/docs for interactive API documentation.

### Terminal 2 — Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173 in your browser.

Try: **ACURA / RDX / 2012** — the official NHTSA examples return complaint and recall records for that combination. The live data may change.

### Run tests

From `backend/` with the virtual environment active:

```bash
python -m pytest -q
```

### Optional: PostgreSQL instead of SQLite

The application defaults to SQLite to minimize setup. To use PostgreSQL, from the project root run:

```bash
docker compose up -d postgres
```

Then in the backend terminal (before starting uvicorn):

```bash
export DATABASE_URL='postgresql+psycopg://autoinsight:development_only_change_me@localhost:5432/autoinsight'
uvicorn app.main:app --reload
```

Use environment variables or secrets management and rotate the example credentials before any external deployment.

## Compare two vehicles (new in v0.2)

1. Start the backend and frontend as described above.
2. Search for one vehicle using **Explore a vehicle**, then search for a different make/model/year.
3. In **Compare two vehicles**, choose each imported car from a dropdown.
4. Click **Compare vehicles**. The comparison loads from the SQLite database (no fresh NHTSA requests).
5. Click **Inspect original reports** to see a selected car's full records.

You can also inspect the comparison endpoint directly in your browser or at http://127.0.0.1:8000/docs:

```text
GET /api/compare?left_id=1&right_id=2
```

IDs refer to records in your local database; they may differ on your machine. The comparison returns HTTP 400 if the two IDs are the same and HTTP 404 if one is missing.

**Updating from v0.1:** This ZIP is a complete version of the source. If you want to retain your previously imported vehicles, stop the backend and copy `backend/autoinsight.db` from your original project into the new project's `backend` directory before restarting the backend. You do not need to install a separate database, and no schema changes are required in v0.2.

## Architecture

```text
React + TypeScript web app
          |
          | HTTP (/api/...)
          v
      FastAPI server
          |
          +--- httpx client ---> NHTSA complaints + recalls APIs
          |
          +--- ETL service: normalize, upsert, timestamp
          |
          v
     SQLite / PostgreSQL
```

## API

- `GET /api/health` — health check
- `GET /api/vehicles` — previously imported cars
- `GET /api/vehicles/{id}` — problems, complaints and recalls for one vehicle
- `GET /api/compare?left_id=1&right_id=2` — lightweight side-by-side comparison of two imported cars
- `POST /api/vehicles/sync?make=ACURA&model=RDX&year=2012` — import or refresh one vehicle **(development only)**

The app points back to the official complaint URL (`/complaints/odinumber`) and recall campaign URL (`/recalls/campaignNumber`) for every record.

## Data quality notes

- NHTSA complaints are consumer-submitted safety allegations, not confirmed mechanical defects or representative failure rates. **Do not calculate a reliability score from raw complaint counts.**
- One complaint may reference more than one component, so category totals can exceed the number of complaints.
- Model-level recalls do not establish whether any particular VIN has an open recall. Verify VIN-specific status on the official NHTSA site.
- Model names must match NHTSA's naming. A missing result is not proof that a model is problem-free.
- This starter only adds/updates records, and does not yet reconcile removals or corrections by a source. It has no scheduled polling or rate limiting yet.
- We avoid displaying VINs or storing VINs from complaint data.

## Next engineering milestones

1. **Completed in v0.2:** Add a model-year comparison endpoint and side-by-side React views.
2. Add a separate structured `problem_cluster` layer backed by source complaints (do not imply clusters are confirmed diagnoses).
3. Implement controlled background sync jobs, retries with backoff, ingestion metrics, and raw payload archival.
4. Add pagination, database indexes, SQL migrations (Alembic), and integration tests.
5. Protect ingestion behind authentication/admin-only operations and deploy through CI/CD.

## Source documentation

- https://www.nhtsa.gov/nhtsa-datasets-and-apis
- https://api.nhtsa.gov/complaints/complaintsByVehicle?make=acura&model=rdx&modelYear=2012
- https://api.nhtsa.gov/recalls/recallsByVehicle?make=acura&model=rdx&modelYear=2012

AutoInsight is a student portfolio project and is not affiliated with NHTSA.

## Where to look in the code for comparison

- `backend/app/main.py`: `compare()` validates IDs and returns HTTP errors for invalid comparisons.
- `backend/app/service.py`: `compare_vehicles()` uses SQL queries and `Counter` objects to calculate complaint-component counts without fetching every full complaint narrative.
- `frontend/src/App.tsx`: `compareSaved()` calls the API; React state holds the selected vehicles and results; the table displays the response.
- `backend/tests/test_compare.py`: validates comparison counts, categories, HTTP 400 and HTTP 404 responses without calling live NHTSA.

The comparison is intentionally **not** a reliability ranking. Complaint counts are not normalized by vehicle population or exposure and must not be interpreted as failure rates.
