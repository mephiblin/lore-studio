from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.model_connections import router as model_connections_router
from app.api.router import router
from app.config import settings
from app.db import Base, SessionLocal, engine
from app.services.config_loader import seed_builtin_recipes, seed_builtin_voice_profiles
from app.services.model_connections import load_model_connection_overrides


@asynccontextmanager
async def lifespan(_: FastAPI):
    # SQLite is an isolated test convenience. PostgreSQL is migrated by Alembic.
    if settings.database_url.startswith("sqlite"):
        Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        load_model_connection_overrides(db)
        seed_builtin_recipes(db)
        seed_builtin_voice_profiles(db)
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router, prefix="/api/v1")
app.include_router(model_connections_router, prefix="/api/v1")


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "docs": "/docs",
        "health": "/api/v1/health",
    }
