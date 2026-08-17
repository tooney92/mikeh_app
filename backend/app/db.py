from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import inspect as sqlalchemy_inspect
from sqlmodel import Session, SQLModel, create_engine

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "tm_bi.db"

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
)


def init_db() -> None:
    # Import so SQLModel.metadata knows about every table before create_all.
    from app import models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    _check_schema_drift()


def _check_schema_drift() -> None:
    """Fail LOUDLY when an existing database is missing columns we now need.

    create_all() creates missing TABLES. It never adds a COLUMN to a table that
    already exists, and there are no migrations here. So booting this code
    against a database made before a column was added dies deep inside the
    seeder with `sqlite3.OperationalError: no such column`, which tells you
    nothing about what to do next.

    This turns that into a sentence naming the columns and the fix. It is a
    diagnostic, not a migration: it refuses to guess and it never writes.
    """
    import sqlite3

    inspector = sqlalchemy_inspect(engine)
    existing = {t: {c["name"] for c in inspector.get_columns(t)} for t in inspector.get_table_names()}

    missing: list[str] = []
    for table in SQLModel.metadata.sorted_tables:
        have = existing.get(table.name)
        if have is None:
            continue  # create_all just made it
        for column in table.columns:
            if column.name not in have:
                missing.append(f"{table.name}.{column.name}")

    if not missing:
        return

    raise sqlite3.OperationalError(
        "This database predates the current models and is missing "
        f"{len(missing)} column(s): {', '.join(sorted(missing))}.\n"
        "There are no migrations here, and create_all() does not alter "
        "existing tables.\n"
        "Either ALTER TABLE ADD COLUMN each one (back the file up first — this "
        "is how min_fit_percent was added and it keeps everyone signed in), "
        "or reseed with `python -m app.seed --reset`, which DESTROYS the data "
        "and mints a new random admin password."
    )


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
