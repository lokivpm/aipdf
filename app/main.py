from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import get_db, engine
from app.models import Base
from app.routes.auth import router as auth_router
from starlette.middleware.sessions import SessionMiddleware 
from app.config import SECRET_KEY,FRONTEND_URL

#cors origins

app = FastAPI()

origins = [
    "https://chatfront-cvpr.onrender.com",
    "http://localhost:3000",  
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    SessionMiddleware, 
    secret_key=SECRET_KEY, 
    session_cookie="session_id",    # Name of the session cookie
    same_site="none",               # Allow cookies across origins
    https_only=True                 # True for production; False for local development over HTTP
)
@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# authentication routes
app.include_router(auth_router)
