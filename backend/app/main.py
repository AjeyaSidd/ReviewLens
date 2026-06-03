from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.logging_config import setup_logging
from app.routers import admin, public
import logging

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("App Review Intelligence API starting up")
    yield
    logger.info("App Review Intelligence API shutting down")

app = FastAPI(
    title="App Review Intelligence",
    description="PM-facing tool to explore curated App Store and Play Store reviews with trends and natural-language Q&A.",
    version="1.0.0",
    lifespan=lifespan,
    swagger_ui_parameters={"persistAuthorization": True},
)

# CORS
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(admin.router)
app.include_router(public.router)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
