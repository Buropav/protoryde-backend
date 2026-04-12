from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import os
from app.api import triggers
from app.core.scheduler import start_scheduler
from app.core.database import init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
import threading

_DB_INIT_TIMEOUT_S = 30

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Run init_db in a background thread so uvicorn binds to the port
    # immediately. Render kills deploys that don't open a port quickly.
    db_thread = threading.Thread(target=init_db, daemon=True)
    db_thread.start()
    # Wait up to _DB_INIT_TIMEOUT_S for tables to be created. If it times out,
    # the app still starts — pool_pre_ping handles reconnection later.
    db_thread.join(timeout=_DB_INIT_TIMEOUT_S)
    if db_thread.is_alive():
        logger.warning(
            "init_db still running after %ds — app will start without confirmed tables.",
            _DB_INIT_TIMEOUT_S,
        )
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

_origins_raw = os.getenv("ALLOWED_ORIGINS", "").strip()
if _origins_raw and _origins_raw != "*":
    _allow_origins = [o.strip() for o in _origins_raw.split(",") if o.strip()]
    _allow_credentials = True
else:
    # Default to wildcard only in development; log a warning for production awareness.
    _allow_origins = ["*"]
    _allow_credentials = False
    if _origins_raw != "*":
        logger.warning("ALLOWED_ORIGINS not set — CORS is wide open. Set it in production.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=_allow_credentials,
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

