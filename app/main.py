from fastapi import FastAPI, HTTPException
from app.routers.auth import auth_router
from app.database.config.db import engine, Base
from fastapi.middleware.cors import CORSMiddleware
from app.routers.auth import auth_router

app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-App-Error-Code", "X-Account-Status"],  # Expose custom headers
)

app.include_router(auth_router)
