import redis
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import POSTGRES_URL, REDIS_URL

# PostgreSQL async engine
engine = create_async_engine(POSTGRES_URL, echo=True)

# Redis client with SSL
redis_client = redis.StrictRedis.from_url(REDIS_URL, ssl=True, ssl_cert_reqs=None)

# Base class for models
Base = declarative_base()

# Session factory for AsyncSession
SessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def get_db():
    async with SessionLocal() as session:
        yield session
