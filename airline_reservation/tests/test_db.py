from __future__ import annotations

from pathlib import Path

from sqlalchemy import text

from aerobooking.db import (
    DEFAULT_SQLITE_URL,
    database_url,
    get_engine,
    get_session_factory,
    reset_database_for_tests,
)


def test_default_database_is_zero_configuration(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("AEROBOOKING_SQLITE_PATH", raising=False)
    assert database_url() == DEFAULT_SQLITE_URL


def test_postgres_urls_use_psycopg3(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://aero:secret@localhost/aero")
    assert database_url() == "postgresql+psycopg://aero:secret@localhost/aero"
    monkeypatch.setenv("DATABASE_URL", "postgres://aero:secret@localhost/aero")
    assert database_url() == "postgresql+psycopg://aero:secret@localhost/aero"


def test_sqlite_file_override_and_factory(monkeypatch, tmp_path: Path) -> None:
    reset_database_for_tests()
    monkeypatch.delenv("DATABASE_URL", raising=False)
    db_file = tmp_path / "override.db"
    monkeypatch.setenv("AEROBOOKING_SQLITE_PATH", str(db_file))
    engine = get_engine()
    assert str(engine.url).endswith("override.db")
    factory = get_session_factory()
    with factory() as session:
        assert session.execute(text("select 1")).scalar_one() == 1
    reset_database_for_tests()
    assert engine.pool is not None


def test_explicit_in_memory_sqlite_engine() -> None:
    engine = get_engine("sqlite+pysqlite:///:memory:")
    try:
        assert engine.dialect.name == "sqlite"
    finally:
        engine.dispose()
