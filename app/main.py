from fastapi import FastAPI
from app.database.config.db import engine, Base
from fastapi.middleware.cors import CORSMiddleware
from app.routers import api_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "https://college-admin-portal-amber.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-App-Error-Code", "X-Account-Status"],  # Expose custom headers
)

# Include the API router
app.include_router(api_router)
