# Local validation record

Date: 13 October 2026. Validation environment: Linux sandbox, Python 3.13.16. Results are for this project revision and the single-process demo configuration.

## Automated checks

| Command | Observed result |
|---|---|
| `ruff check src tests scripts` | All checks passed. |
| `ruff format --check src tests scripts` | 23 files already formatted. |
| `mypy` | Success: no issues found in 9 source files. |
| `PYTHONPATH=src pytest -q --cov=aerobooking --cov-branch --cov-report=term` | 45 passed; 93.1% combined statement/branch coverage. |
| `python -m build` | sdist and wheel built successfully. |
| `node --check` of the page's inline JavaScript | Passed. |

## Thread race

A clean temporary SQLite file was used with `aerobooking stress --flight AS110 --threads 50`:

```text
attempts: 50; confirmed: 36; rejected: 14; duplicate seat assignments: 0
```

AS110 Economy has 36 sample seats. This result is for 50 threads handled by one application process. It is not evidence of multi-process, PostgreSQL, remote-network or production-scale correctness.

## Live API smoke checks

- `GET http://localhost:8000/` returned HTTP 200 with the AeroReserve page and four clickable header-popover buttons.
- `GET http://localhost:8000/api/health` reported SQLite, zero active bookings and zero SSE subscribers at smoke-test time.
- VGA → DEL search for 14 October 2026 returned five sample itineraries, including 0-, 1- and 2-connection options; AS110 was the first result.
- A separate automated test starts Uvicorn, receives an SSE seat snapshot, posts a booking, and verifies the resulting booking event and updated seat map.

## Not run / not established

PostgreSQL integration, Docker/Compose execution, Windows launchers, remote GitHub Actions, multiple application workers, live airline integrations, production load/latency, payment processing, authentication and real passenger-data handling were not validated. Do not infer those properties from the local results above.
