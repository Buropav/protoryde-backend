from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import os
from app.api import triggers
from app.core.scheduler import start_scheduler
from app.core.database import init_db

logging.basicConfig(level=logging.INFO)
import threading

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Run init_db in a background thread so uvicorn binds to the port
    # immediately. Render kills deploys that don't open a port quickly.
    db_thread = threading.Thread(target=init_db, daemon=True)
    db_thread.start()
    scheduler = None
    if os.getenv("ENABLE_SCHEDULER", "false").lower() == "true":
        scheduler = start_scheduler()
    yield
    if scheduler is not None:
        scheduler.shutdown()

app = FastAPI(
    title="ProtoRyde Phase 2 - Trigger & Simulation Backend",
    lifespan=lifespan
)

_origins_raw = os.getenv("ALLOWED_ORIGINS", "*")
_allow_origins = [o.strip() for o in _origins_raw.split(",")] if _origins_raw != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=_origins_raw != "*",
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(triggers.router)

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "ProtoRyde FastAPI Server"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
