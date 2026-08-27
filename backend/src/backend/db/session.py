from collections.abc import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.config import get_settings


def make_engine() -> Engine:
    # Short timeout avoids Windows' long default TCP connect timeout when DB is down.
    return create_engine(get_settings().database_url, connect_args={"connect_timeout": 3})


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
