from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import os
from backend.api import triggers
from backend.core.scheduler import start_scheduler
from backend.core.database import init_db

logging.basicConfig(level=logging.INFO)

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(triggers.router)

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "ProtoRyde FastAPI Server"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
