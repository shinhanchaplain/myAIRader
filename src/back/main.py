"""AI Radar FastAPI 앱. 실행: uvicorn src.back.main:app --port 8020"""
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from . import db, scheduler
from .routes import router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
FRONT_DIR = Path(__file__).resolve().parents[1] / "front"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """기동 시 DB 를 초기화하고 스케줄러를 시작한다(RADAR_DISABLE_SCHEDULER=1 이면 생략)."""
    db.init_db()
    if os.environ.get("RADAR_DISABLE_SCHEDULER") != "1":
        scheduler.start_scheduler()
    yield
    scheduler.stop_scheduler()


app = FastAPI(title="AI Radar", version="0.1", lifespan=lifespan)
app.include_router(router)
app.mount("/", StaticFiles(directory=FRONT_DIR, html=True), name="front")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.back.main:app", host="0.0.0.0", port=8020)
