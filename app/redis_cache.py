import redis.asyncio as aioredis
from app.config import REDIS_URL

redis = aioredis.from_url(REDIS_URL)

async def get_redis():
    return redis
