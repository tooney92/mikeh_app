from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.admin import mount_admin
from app.db import init_db
from app.routers import decisions, opportunities, profiles, radar, scan, sources
from app.seed import run as run_seed


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    run_seed()  # idempotent — skips any table that already has rows
    yield


app = FastAPI(
    title="TM Global Business Intelligence API",
    version="0.1.0",
    lifespan=lifespan,
)

# The Vite dev server runs on 5173; loosen or tighten once staging is set.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

mount_admin(app)  # back-office CRUD at /admin

app.include_router(radar.router)
app.include_router(opportunities.router)
app.include_router(decisions.router)
app.include_router(profiles.router)
app.include_router(sources.router)
app.include_router(scan.router)


@app.get("/api/health", tags=["meta"])
def health():
    return {"status": "ok"}
