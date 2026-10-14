# AeroReserve: flight booking and seat allocation

AeroReserve is a **working academic demo** that converts the Railway Reservation System into an actual flight-booking domain. It has date-specific fictional flights, direct and connecting itineraries, cabin-specific seats, fare quotes, one PNR per itinerary, cancellations, a REST API, an interactive browser UI and live seat-map updates.

> **Demo only:** all schedules and fares are fictional. The project has no airline inventory feed, ticketing/payment integration, passenger login or identity verification.

## Feature scope

- Seven sample Indian airports: **VGA, HYD, BLR, BOM, DEL, MAA and GOI**; 27 fictional AeroSky flights repeat daily as dated instances.
- Search **Economy, Premium Economy, Business and First** inventory by route and date.
- Direct itineraries and up to two connections (three flight legs), with a **45-minute minimum** connection time.
- One PNR and one database transaction cover every flight leg in a connecting itinerary; seat selection is cabin- and flight-instance-specific.
- Seat-map preview plus **first-fit**, **window-first** and **family-aware** seat allocation.
- Fare breakdown by leg, illustrative 5% tax and INR 99 per-passenger service fee.
- Booking retrieval, cancellation, persisted audit events, and server-sent events (SSE) for live seat-map refreshes.
- Browser UI served by FastAPI, plus a command-line search/booking/stress demo.
- SQLite with no setup by default. PostgreSQL can be selected via `DATABASE_URL` or Docker Compose.

## Quick start

Requires **Python 3.11 or newer**.

### Windows PowerShell

```powershell
cd airline_reservation
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m uvicorn aerobooking.api:app --reload --host 0.0.0.0 --port 8000
```

If PowerShell blocks activation, use `cmd.exe` and the included `setup.bat` / `run_demo.bat` scripts instead. The scripts have not been executed in this Linux validation environment.

### Linux / macOS

```bash
cd airline_reservation
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
python -m uvicorn aerobooking.api:app --reload --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000** (include port `8000`). The root page is the booking UI; API docs are at `http://localhost:8000/docs`.

The first run creates `./aerobooking.db` and its tables automatically. No sample database download or database-server setup is required. The default schedule appears for today through the next 180 days (Indian Standard Time date). Example starting route: Vijayawada (`VGA`) to New Delhi (`DEL`).

## Optional PostgreSQL

Installations using the package's dependencies already include the Psycopg 3 driver. Set a SQLAlchemy URL such as:

```bash
export DATABASE_URL='postgresql+psycopg://aero:change-me@localhost:5432/aerobooking'
python -m uvicorn aerobooking.api:app --host 0.0.0.0 --port 8000
```

PowerShell equivalent:

```powershell
$env:DATABASE_URL = 'postgresql+psycopg://aero:change-me@localhost:5432/aerobooking'
python -m uvicorn aerobooking.api:app --host 0.0.0.0 --port 8000
```

There is also a Docker Compose file with a PostgreSQL service: `docker compose up --build`. The automated tests in this deliverable use isolated SQLite databases; **PostgreSQL has not been integration-tested here**. The current seat lock manager and SSE event bus are process-local. Do not run multiple API worker processes and claim cross-process booking or live-event correctness: that needs shared transactional inventory locking and a cross-process event broker, then dedicated tests.

## Quick command-line demo

After `pip install -e .`:

```bash
aerobooking airports
aerobooking search --from VGA --to DEL --date 2026-10-14 --connections 2
aerobooking book --from VGA --to DEL --date 2026-10-14 -p 'Asha Rao:22' -p 'Ravi Rao:25'
aerobooking booking <PNR>
aerobooking cancel <PNR>
```

The date above is an example. Omit `--date` to use tomorrow's date in IST. `book` reserves the first itinerary returned by the route search. For a safe fresh-database concurrency demonstration on a local shell:

```bash
AEROBOOKING_SQLITE_PATH=./stress-demo.db aerobooking stress --flight AS110 --threads 50
```

On a clean database, the Economy cabin has 36 seats; this race should confirm 36 single-passenger requests and reject 14, with no repeated seat label. Existing bookings on that date reduce the confirmed count. The stress result demonstrates **threads in one process only**, not multiple application processes.

## API outline

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/airports` | Sample airports |
| `GET` | `/api/flights/search` | Dated direct and connecting itineraries, availability and quote |
| `GET` | `/api/flights/{flight_id}/seats` | Cabin-specific seat map |
| `GET` | `/api/flights/{flight_id}/events` | SSE snapshot and booking/cancellation events |
| `POST` | `/api/bookings/quote` | Recalculate an itinerary quote |
| `POST` | `/api/bookings` | Reserve all legs under one PNR |
| `GET` | `/api/bookings/{pnr}` | Retrieve a booking |
| `POST` | `/api/bookings/{pnr}/cancel` | Cancel and release seats on every leg |
| `GET` | `/api/health` | Database, active bookings, subscribers and process-local lock counters |
| `GET` | `/api/admin/audit` | Recent persisted audit entries |

Example search (change date as needed):

```bash
curl 'http://localhost:8000/api/flights/search?origin=VGA&destination=DEL&travel_date=2026-10-14&cabin=Economy&max_connections=2&passengers=2'
```

## Design notes and limits

- **Dated inventory key:** `(flight_id, cabin)`. Each dated flight/cabin has its own seat labels and availability; the same seat label on a different flight is independent.
- **Search:** bounded route walk over the daily fictional schedule. It avoids airport cycles, allows at most three legs, validates a 45-minute minimum layover and sorts by arrival time, then connection count and distance.
- **Seat maps:** illustrative single-aisle cabin layouts: Economy 36, Premium Economy 12, Business 8 and First 4 seats per flight.
- **Fare:** Economy ₹3.80/km, Premium Economy ₹5.50/km, Business ₹9.50/km and First ₹15.00/km, multiplied by passenger count; add 5% illustrative tax and ₹99 per passenger. These are project formula values, **not real fares or tax advice**.
- **Storage:** `bookings`, `booking_legs` and `audit_log` SQLAlchemy tables. Each PNR is the booking key; the leg rows retain date, cabin, times and seat assignments.
- **Concurrency boundary:** each app process uses sorted, process-local per-flight locks and database transactions. The threaded race test checks the current single-process path. The JSON seat payload does not provide a shared cross-process seat uniqueness constraint; no multi-worker guarantee is claimed.
- **Live updates:** SSE sends an initial seat snapshot and then in-process booking/cancellation events. It is suitable for the single-process demo; multiple workers would require a shared event broker.

## Tests and quality checks

```bash
pytest -q
pytest -q --cov=aerobooking --cov-report=term-missing
ruff check src tests
ruff format --check src tests
mypy
```

The included suite covers route rules, cabin maps, allocation, quotes, booking/cancellation, API responses, SSE delivery, Hypothesis properties and a concurrent 50-request seat race. The Postgres URL path and Windows scripts are supplied but not validated by these checks.

## Deliverables

- `docs/PROJECT_REPORT.docx` — project report.
- `docs/DEFENCE_SLIDES.pptx` — 11-slide viva presentation.
- `docs/DEFENCE_PACK.md` — demo script, likely questions and evidence/limitations.
- `docs/ARCHITECTURE.md` and `docs/VALIDATION_RESULTS.md` — implementation notes and local verification record.
- `AeroReserve_Submission.zip` — clean source, tests, documentation and report/deck package (rebuild with `python scripts/make_package.py`).
- `scripts/make_report.py`, `scripts/make_slides.py`, `scripts/make_diagrams.py` — reproducible report, deck and diagram generators.
- `requirements.txt`, `requirements-dev.txt`, `pyproject.toml`, Docker and CI configuration.

Update the cover-page student/institution fields before submission. The generated documents describe only functionality present in this repository and list untested items and process-local concurrency limits explicitly.
