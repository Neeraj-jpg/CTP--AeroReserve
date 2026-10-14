from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from aerobooking import cli
from aerobooking.db import reset_database_for_tests


@pytest.fixture
def cli_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    reset_database_for_tests()
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("AEROBOOKING_SQLITE_PATH", str(tmp_path / "cli.db"))
    yield
    reset_database_for_tests()


def test_cli_airports_search_book_retrieve_cancel(
    cli_database: None, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["airports"]) == 0
    airports = json.loads(capsys.readouterr().out)
    assert len(airports) == 7

    assert cli.main(["search", "--from", "VGA", "--to", "DEL", "--connections", "2"]) == 0
    options = json.loads(capsys.readouterr().out)
    assert options[0]["flights"] == ["AS110"]
    assert any(option["connections"] == 2 for option in options)

    assert cli.main(["book", "--from", "VGA", "--to", "DEL", "-p", "Asha Rao:22"]) == 0
    booking = json.loads(capsys.readouterr().out)
    assert len(booking["pnr"]) == 10
    assert booking["legs"] == ["AS110"]

    assert cli.main(["booking", booking["pnr"]]) == 0
    stored = json.loads(capsys.readouterr().out)
    assert stored["status"] == "CONFIRMED"
    assert cli.main(["cancel", booking["pnr"]]) == 0
    assert "CANCELLED" in capsys.readouterr().out


def test_cli_thread_stress_summary_is_scoped_to_one_process(
    cli_database: None, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["stress", "--flight", "AS110", "--threads", "40"]) == 0
    output = capsys.readouterr().out
    assert "attempts: 40" in output
    assert "confirmed: 36" in output
    assert "rejected: 4" in output
    assert "duplicate seat assignments: 0" in output


def test_cli_invalid_search_and_unknown_pnr_are_reported(
    cli_database: None, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["search", "--from", "XXX", "--to", "DEL"]) == 2
    assert "unknown airport" in capsys.readouterr().out
    assert cli.main(["booking", "UNKNOWN1234"]) == 2
    assert "not found" in capsys.readouterr().out


def test_cli_rejects_malformed_passengers() -> None:
    with pytest.raises(ValueError, match="expected NAME:AGE"):
        cli._parse_passengers(["missing-age"])
    with pytest.raises(ValueError, match="expected NAME:AGE"):
        cli._parse_passengers(["Guest:999"])


def test_cli_threads_argument_must_be_positive() -> None:
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["stress", "--threads", "0"])
