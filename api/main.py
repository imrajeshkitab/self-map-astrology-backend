"""
api/main.py
-----------
FastAPI application entry point.

Run:
    uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

Interactive docs:
    http://localhost:8000/docs       (Swagger UI)
    http://localhost:8000/redoc      (ReDoc)
"""

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load .env before anything else so ASTRO_API_KEY is available
load_dotenv()

# Make src/ importable
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.routes.self_map import router as self_map_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: verify env and ensure output dir exists
    if not os.environ.get("ASTRO_API_KEY"):
        raise RuntimeError("ASTRO_API_KEY is not set. Add it to your .env file.")
    Path("output").mkdir(exist_ok=True)
    yield
    # Shutdown: nothing to clean up


app = FastAPI(
    title="Kitab Personality Self Map API",
    description=(
        "Generates an 8-dimension Vedic + Western astrology personality Self Map "
        "from birth data. Returns a radar chart (PNG) and full JSON profile. "
        "Designed for the Kitab book recommendation engine."
    ),
    version="1.1.0",
    lifespan=lifespan,
)

# CORS — adjust origins for your frontend in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    expose_headers=["X-Cache-Key", "X-Cached"],
)

app.include_router(self_map_router, prefix="/api/v1", tags=["Self Map"])


@app.get("/health", tags=["Health"])
async def health() -> dict:
    return {
        "status": "ok",
        "api_key_set": bool(os.environ.get("ASTRO_API_KEY")),
    }
