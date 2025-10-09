"""Database engine and session factory configuration."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.packages.system.core.config import get_settings

settings = get_settings()

# ``pool_pre_ping`` keeps the connection pool healthy; ``echo`` mirrors SQL logs
# when enabled in settings for easier debugging.
engine = create_engine(settings.sql_database_url, pool_pre_ping=True, echo=settings.database_echo)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
