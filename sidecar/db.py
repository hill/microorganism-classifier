"""Engine and session helpers.

The engine is created once at module import. FastAPI route handlers depend on
`get_session` to get a per-request session. The camera worker creates its own
short-lived sessions for writes using `session_scope`.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session as DbSession
from sqlmodel import create_engine

from sidecar.paths import DB_PATH, ensure_state_dir


def _make_engine() -> Engine:
    ensure_state_dir()
    return create_engine(
        f"sqlite:///{DB_PATH}",
        connect_args={"check_same_thread": False},
    )


@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode = WAL")
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.close()


engine = _make_engine()


def run_migrations() -> None:
    """Apply any pending Alembic migrations. Called at sidecar startup."""
    from alembic import command
    from alembic.config import Config

    from sidecar.paths import PROJECT_ROOT

    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    command.upgrade(cfg, "head")


def get_session() -> Iterator[DbSession]:
    """FastAPI dependency."""
    with DbSession(engine) as session:
        yield session


@contextmanager
def session_scope() -> Iterator[DbSession]:
    """Context manager for code outside FastAPI (workers, scripts)."""
    session = DbSession(engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
