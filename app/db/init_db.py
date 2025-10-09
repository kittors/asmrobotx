"""Database bootstrapping utilities."""

from app.db import session as db_session
from app.models.base import Base


def init_db() -> None:
    """Create all database tables if they do not exist."""
    Base.metadata.create_all(bind=db_session.engine)
