from passlib.context import CryptContext
from app.models import User
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException,Depends,Request,status
from app.database import get_db
from sqlalchemy.future import select
from app.redis_cache import get_redis
from redis.asyncio import Redis


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
async def get_current_user(request: Request, db: AsyncSession = Depends(get_db), redis: Redis = Depends(get_redis)) -> User:
    session_id = request.session.get("session_id")
    
    if not session_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not authenticated")
    
    # user_id from Redis using session ID
    user_id = await redis.get(session_id)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not authenticated")
    

    user = await db.get(User, int(user_id))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not authenticated")
    
    return user



def hash_password(password: str) -> str:
    return pwd_context.hash(password)

async def verify_user(email: str, password: str, db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalars().first()
    if user and pwd_context.verify(password, user.password):
        return user
    raise HTTPException(status_code=400, detail="Invalid credentials")
