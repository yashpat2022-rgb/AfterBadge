# AfterBadge — What the badge won't tell you

**v0.3 · Full-stack automotive problem intelligence**

AfterBadge is an independent, educational SWE portfolio app. It helps users
research owner-reported vehicle problems using public U.S. National Highway
Traffic Safety Administration (NHTSA) complaint and recall data. It does not
sell cars or generate unsupported reliability rankings.

## What's working

- Search a year/make/model and import its complaints and recalls from NHTSA.
- Normalize and store those records with stable IDs in SQLite (or PostgreSQL).
- Explore NHTSA component categories and the full original complaint narratives.
- Compare two saved vehicles side by side by complaint components and recalls.
- **New in v0.3:** a conservative, transparent **phrase-based symptom explorer**:
  groups consumer complaint narratives that explicitly mention engine stalls,
  brake concerns, steering loss, unexpected acceleration, shifting, airbag
  non-deployment, electrical failures, or overheating.
- **New in v0.3:** click a group to filter the exact supporting complaint IDs,
  review the original narratives, and open their official NHTSA source links.
- Offline automated tests for normalization, comparisons, text matching,
  grouping, and API integration.

**This is deliberately rule-based, not a trained ML model.** A matching phrase
is an allegation in a narrative, not proof of a defect. The rules are written
in `backend/app/patterns.py`, so reviewers can understand and test them.

## Run on macOS

Requires Python 3.11+ and Node.js 20+. Open this directory in VS Code.

### Terminal 1 (backend)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest -q
uvicorn app.main:app --reload
```

Backend docs: http://127.0.0.1:8000/docs

### Terminal 2 (frontend)

```bash
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173.

For existing v0.2 users who have pushed GitHub already, **use
`UPGRADING.md` and the smaller update ZIP** rather than replacing your
Git-connected folder.

## New v0.3 data flow

```text
React frontend (App.tsx)
  -> GET /api/vehicles/{id}
  -> FastAPI (main.py)
  -> SQLAlchemy (service.py, models.py)
  -> Complaint narratives in SQLite
  -> patterns.py: explicit phrase rules + per-pattern ODI IDs
  -> UI symptom cards -> click to filter source complaint records
```

There is **no schema migration** in v0.3. Groups are computed from already
stored complaint descriptions when a vehicle is viewed. The SQLite default
remains `backend/autoinsight.db` for compatibility with v0.2 installs.

## API

- `GET /api/health`: health check
- `GET /api/vehicles`: imported vehicle list
- `GET /api/vehicles/{vehicle_id}`: vehicle details including `problem_patterns`
- `GET /api/compare?left_id=1&right_id=2`: side-by-side component comparisons
- `POST /api/vehicles/sync?make=ACURA&model=RDX&year=2012`: import/refresh NHTSA records (local development only)

Each `problem_patterns` entry contains its rule key/title, matched report
count, original ODI IDs, and up to three evidence examples with source URLs.
There can be multiple patterns in a single complaint.

## Important limitations and safeguards

- This is not a vehicle safety rating, an actuarial failure probability, or
  a substitute for a mechanic's pre-purchase inspection.
- Complaint narratives are user-submitted and may include mistaken statements,
  duplicates of real-world events, or phrases used in a different context.
- The rule engine uses explicit phrases and may miss alternate wording or
  incorrectly match a phrase in a quotation or hypothetical description.
- A complaint can mention multiple components and match multiple patterns.
- No matching phrase **does not** mean a vehicle is problem-free.
- Model-level recall records do not say whether a particular VIN has an open
  recall. Check that using NHTSA's official VIN lookup.
- The POST sync endpoint is for local testing; authenticate or disable it
  before public hosting. It has no production rate-limiting or job scheduler.
- Avoid committing private .env files or local databases.

## Next SWE milestones

1. Add explicit phrase context and negation handling, better rule-coverage tests.
2. Persist structured group assignments with provenance and incremental refreshes.
3. Add pagination and full-text search over complaint narratives.
4. Introduce backend sync jobs, retries, metrics, and a CI workflow.

## Sources

- https://www.nhtsa.gov/nhtsa-datasets-and-apis
- https://api.nhtsa.gov/complaints/complaintsByVehicle?make=acura&model=rdx&modelYear=2012
- https://api.nhtsa.gov/recalls/recallsByVehicle?make=acura&model=rdx&modelYear=2012

AfterBadge is not affiliated with NHTSA.
