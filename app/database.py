from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

settings.data_dir.mkdir(parents=True, exist_ok=True)

connect_args = {"check_same_thread": False} if settings.resolved_database_url.startswith("sqlite") else {}
engine = create_engine(settings.resolved_database_url, connect_args=connect_args)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record) -> None:
    if settings.resolved_database_url.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def ensure_columns() -> None:
    """Add columns introduced after the first release.

    create_all builds a new database. A Pi that already has a database
    needs the new column added in place.
    """
    if not settings.resolved_database_url.startswith("sqlite"):
        return
    with engine.begin() as conn:
        tables = {
            row[0]
            for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        if "days" not in tables:
            return
        columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(days)")}
        if "water_glasses" not in columns:
            conn.exec_driver_sql("ALTER TABLE days ADD COLUMN water_glasses INTEGER")


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
