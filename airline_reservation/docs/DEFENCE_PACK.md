# AeroReserve defence pack

This pack contains an 8-minute working-demo script, anticipated viva questions and the tested/unverified boundaries. Use the report and deck for the formal presentation. **All schedules and fares are fictional.**

## 1. Eight-minute live demonstration

### 0. Start the application

Linux / macOS:

```bash
cd airline_reservation
. .venv/bin/activate
python -m uvicorn aerobooking.api:app --reload --host 0.0.0.0 --port 8000
```

Windows: run `setup.bat` once, then `run_demo.bat` (or `run_demo.ps1`). These Windows scripts were not executed in the Linux validation environment.

Open **http://localhost:8000**. Do include port `8000` in the address. SQLite creates its file and tables automatically. `/docs` shows the API interface at **http://localhost:8000/docs**.

Say: *“This is an academic flight-booking demo with a fictional sample timetable. The default local store is SQLite and needs no separate setup. PostgreSQL can be selected by URL, but I have not integration-tested it here.”*

### Interface tour

| Area | What to point out |
|---|---|
| Search bar | Airports, travel date, passenger count and cabin. Default demo route is VGA → DEL. |
| Itinerary list | Non-stop and one-/two-connection options, flight numbers, times, fare and seats left on every leg. |
| Booking panel | Passenger inputs, allocation policy and fare breakdown. |
| Seat-map preview | Cabin-specific seats for the selected leg; connection tabs show each flight separately. |
| Header buttons | API, Live, DB and Subs each open a popover with service/stream/store/subscriber information. |
| Live indicator | Selecting an itinerary opens SSE streams; a second tab can observe a committed seat change. |

### 1. Search and compare (2 minutes)

Use `VGA` → `DEL` for tomorrow’s date. Point to the non-stop option, then the one-stop and two-stop options.

A sample one-stop connection is:

- AS101: VGA → HYD, 06:00–07:15.
- AS205: HYD → DEL, 08:30–10:55.
- Layover: 75 minutes.

A sample two-stop path is AS101 VGA → HYD, AS206 HYD → BLR, and AS306 BLR → DEL. Each transfer is 90 minutes in the sample timetable.

Say: *“The search is over a dated fictional schedule. The legs must join at the same transfer airport, the minimum layover is 45 minutes, and the itinerary can contain at most three flight legs.”*

### 2. Cabins, seat map and fare (1 minute)

Change cabin and passenger count. Select a connecting itinerary and use the leg tabs to inspect each cabin seat map. Change between **Keep group together**, **First available seats**, and **Prefer window seats**. Explain that the family-aware policy seeks a contiguous same-row block on one side of the aisle, and falls back to first-fit if none is available.

Say: *“The numbers and fare formula are sample data, not live fares or tax advice. A connecting booking gets a separate seat assignment on each flight.”*

### 3. Book and explain the PNR (1 minute)

Enter fictional names and book the selected one- or two-connection route. Read the PNR and each leg’s seat assignment. Explain that the repository writes one booking row plus an ordered leg row per flight in one database transaction. Do not enter real passenger data.

### 4. Live update (1 minute)

Before booking, open the same route/date/cabin in a second browser tab and select the same flight or itinerary. Book from the first tab. The other tab refreshes its seat map when its SSE connection receives the committed booking event.

Say: *“The client receives an initial snapshot and then in-process server-sent events. The event bus is local to this one app process; a multi-worker deployment needs a shared event broker.”*

### 5. Cancellation and seat release (1 minute)

Copy the PNR, then use the terminal:

```bash
aerobooking cancel <PNR>
aerobooking booking <PNR>
```

Cancellation changes the PNR state and frees seats on every leg. The second tab should observe cancellation when subscribed to the affected flights.

### 6. Tests and concurrency boundary (2 minutes)

Run quality checks:

```bash
pytest -q
ruff check src tests && ruff format --check src tests && mypy
```

For a repeatable fresh-database thread race, in Linux/macOS:

```bash
rm -f stress-demo.db
AEROBOOKING_SQLITE_PATH=./stress-demo.db aerobooking stress --flight AS110 --threads 50
```

PowerShell equivalent:

```powershell
Remove-Item .\stress-demo.db -Force -ErrorAction SilentlyContinue
$env:AEROBOOKING_SQLITE_PATH = '.\stress-demo.db'
aerobooking stress --flight AS110 --threads 50
```

On a fresh database, the expected output is 50 attempts, 36 confirmed, 14 rejected and 0 duplicate seat assignments. Say: *“This validates 50 threads handled inside one process against 36 sample Economy seats. It is not a multi-process or PostgreSQL concurrency test, and it is not a throughput benchmark.”*

## 2. Anticipated questions

### Problem solving and computational thinking

**Q: How is this more than a UI rename?**  
A: The domain now uses airports, dated flights, four cabins, ordered flight legs, connection rules and an itinerary-level PNR. The schedule, search, seat capacity, APIs, persistence, UI and tests all use the flight domain.

**Q: How does connection search work?**  
A: For the selected date, the service groups flights by origin and performs a recursive route walk to a maximum depth of three legs. It rejects airport cycles and only follows a transfer if the next departure is at least 45 minutes after the previous arrival. Results are sorted by arrival, connection count, distance and flight IDs.

**Q: Why a bounded depth-first route walk instead of a more complex planner?**  
A: The sample network is small, and the product scope caps itineraries at three legs. A bounded route walk is simple to audit and test. Large networks, multiple time zones and multi-day connections would need a more sophisticated, measured routing design.

**Q: What is the search complexity?**  
A: If `b` is the number of candidate outgoing flights and `k ≤ 3` is the leg limit, path enumeration is bounded by roughly `O(Σ b^i)` for `i=1…k`, plus sorting `P` returned paths in `O(P log P)`. This is a bound for the sample graph, not a benchmark or a claim about airline-scale networks.

**Q: How is the 45-minute rule tested?**  
A: It is applied in the route walk and in the `Itinerary` domain validator. Tests inspect every adjacent leg in returned options and test invalid itineraries/inputs.

**Q: Why use three seat strategies?**  
A: They make allocation trade-offs visible and testable: first-fit is deterministic, window-first prioritises windows, and family-aware tries an aisle-safe same-row block before falling back to first-fit. These are greedy per-request policies, not global optimisers.

**Q: Why isn’t a seat “free” for the whole day?**  
A: In this airline demo, inventory is scoped to a dated flight instance and cabin. A separate label such as `E01A` on a different flight instance is independent. The project does not reuse a seat across route segments of one train.

### Programming and data structures

**Q: Which data structures are important?**  
A: Dictionaries map airport codes to outgoing flights and IDs to dated flights; sets track visited airports and occupied seats; tuples preserve ordered immutable itinerary legs; bounded queues carry live events; and the lock manager maps flight IDs to process-local locks.

**Q: Where are pure or side-effect-light functions used?**  
A: Cabin layout generation, seat selection, seat-map formatting and fare calculation take explicit inputs and return values. Persistence, locks and event publication are kept in the service/repository flow rather than hidden in the allocator.

**Q: How is a connecting PNR stored?**  
A: One `bookings` record is keyed by the PNR. One to three ordered `booking_legs` records reference it. Passenger and quote details are JSON payloads; the audit table records `BOOK` and `CANCEL` actions.

**Q: What is the fare formula?**  
A: Each flight line is `distance × cabin rate × passenger count`. The project adds an illustrative 5% and ₹99 per passenger. Rates are fictionally chosen constants and are not live market prices or official tax values.

### Software design and concurrency

**Q: Why separate the repository from the service?**  
A: The service owns the booking workflow and domain rules; the repository owns SQLAlchemy reads/writes. Tests can supply a temporary SQLite repository and can verify persisted assignments after a concurrent race.

**Q: How does the transaction cover all itinerary legs?**  
A: The service first builds seat assignments for all legs while holding its flight locks, then sends the booking and all leg rows to one repository transaction. If the transaction fails, the ORM transaction rolls back rather than leaving only some leg rows.

**Q: How do locks avoid deadlock for two connecting itineraries?**  
A: All involved flight IDs are acquired in sorted order. Locks are released by the context manager even when an error occurs. They are `RLock` objects held by this process only.

**Q: Does the stress test prove multi-process correctness?**  
A: No. It launches 50 threads in one process. The lock map is not shared, and the database stores the leg’s seat list as JSON without a unique row per seat. Multi-worker booking safety requires a shared authoritative inventory/locking design and a separate multi-process race test. The report does not claim otherwise.

**Q: Does PostgreSQL work?**  
A: The dependencies and URL configuration support SQLAlchemy with Psycopg 3, and Compose declares a PostgreSQL service. PostgreSQL was not available or integration-tested in this validation, so I only claim that the option is configured—not verified.

**Q: How do live events work?**  
A: The route sends a current seat snapshot and then booking/cancellation SSE frames from a bounded in-process event bus. The browser refreshes the seat map after an event. There is no persistent replay log; the audit table is the durable record.

**Q: What happens when someone cancels?**  
A: The service looks up the PNR, locks its flight IDs, changes the booking status to `CANCELLED` and adds an audit row in a transaction. Inventory queries count only confirmed bookings, so seats on all legs become free. Cancellation events are then published.

### Quality, deployment and scope

**Q: What did you actually test?**  
A: The validation run reports 45 passing tests and 93.1% statement/branch coverage, with route, seat, fare, lifecycle, API, Hypothesis, SSE-over-Uvicorn and thread-race tests. Ruff and strict mypy checks passed. The coverage number is not a proof of correctness.

**Q: Why SQLite by default?**  
A: A zero-setup file database makes the project easy to run in a defence. SQLAlchemy provides a configured optional PostgreSQL URL. The actual test run uses isolated SQLite files.

**Q: Why no waitlist, login, payment or live airline feed?**  
A: Those were not in the selected scope. The current application is a functioning booking demo with fictional schedules and rates; adding real ticketing or personal data would require commercial integrations, authentication, privacy and security controls, and additional validation.

**Q: Is it safe for real passenger data?**  
A: No. It has no login, access control or production privacy/retention controls. Use fictional names only.

**Q: Why is the SSE event bus in-process?**  
A: It keeps the demo dependency-free and directly demonstrates push updates. Multi-instance fan-out would require Redis, PostgreSQL `LISTEN/NOTIFY` or a comparable shared service, plus tests.

### AI-assisted development and academic integrity

**Q: Was AI used, and how was output checked?**  
A: AI assistance was used for implementation, test and document drafts. The work was checked against the requested flight scope, made executable and covered by automated tests. Examples documented in the report include testing aisle-aware grouping, running a live SSE integration test, catching a UI confirmation-reset issue, and narrowing claims to the evidence. The student should state their own actual review process and follow institutional disclosure requirements.

## 3. Complexity and constants reference

| Component | Current implementation |
|---|---|
| Daily sample network | 27 templates · 7 airports · generated by date |
| Max itinerary | 3 flight legs / 2 connections |
| Minimum layover | 45 minutes |
| Seats per sample flight | Economy 36 · Premium Economy 12 · Business 8 · First 4 |
| Seat allocation | O(C) first-fit/family scan; O(C log C) window-first sort; C ≤ 36 |
| Fare quote | O(L) per itinerary; L ≤ 3 |
| Lock ordering | O(L log L) for sorted flight IDs; locks local to one process |
| Thread race | 50 contenders · 36 confirmed · 14 rejected · 0 duplicate labels on fresh local SQLite |
| Automated suite | 45 passed · 93.1% statement/branch coverage |

No heap-based allocator, waitlist, branch-and-bound search or external benchmark is included in this airline build.

## 4. AI-assisted development record

- **Specification:** confirm full airline conversion, dated/cabin-specific search, connecting itineraries, 45-minute minimum, one PNR, fictional schedules, no live feed/payment/login, and zero-config SQLite with optional PostgreSQL.
- **Implementation:** domain models and schedule, seat allocator, SQLAlchemy repository, booking service, FastAPI routes, CLI, browser UI and deployment/docs.
- **Verification:** isolated SQLite tests; property-based seat/fare checks; live SSE over a local Uvicorn server; 50-thread race on one flight; ruff and strict mypy.
- **Corrections from review:** give family-aware allocation an aisle-specific test; preserve PNR confirmation during post-book search refresh; make the route graph and date/cabin semantics explicit; correct report claims to the implemented persistence and single-process locking model.
- **Known gaps retained:** PostgreSQL and Windows not executed; no external schedules or payments; no multi-process correctness claim.

Before submission, replace student/institution placeholders, run the demo yourself, review the generated Office files, and make any AI-assistance disclosure required by the course.
