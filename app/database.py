
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import POSTGRES_URL

# async engine
engine = create_async_engine(POSTGRES_URL, echo=True)

# base class for models
Base = declarative_base()

# session factory for AsyncSession
SessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def get_db():
    async with SessionLocal() as session:
        yield session
