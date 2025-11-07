import os
import redis
from fastapi import FastAPI
from app.api import auth, meetings, scheduler
from app.core.scheduler import scheduler as apscheduler
from starlette.middleware.cors import CORSMiddleware
from app.log_config import logger

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all HTTP methods
    allow_headers=["*"],  # Allows all headers
)

def cleanup_redis_on_startup(redis_key):
    REDIS_HOST = os.getenv("REDIS_HOST", "redis")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    r.delete(redis_key)
    logger.info(f"Cleaned up Redis key: {redis_key} on startup.")


@app.on_event("startup")
def startup_event():
    if not apscheduler.running:
        logger.info("Starting scheduler...")
        apscheduler.start()
    else:
        logger.info("Scheduler already running.")

@app.on_event("shutdown")
def shutdown_event():
    logger.info("Shutting down scheduler...")
    apscheduler.shutdown()

cleanup_redis_on_startup("meeting_states")
cleanup_redis_on_startup("bot_added_in_meeting")

app.include_router(auth.router)
app.include_router(meetings.router)
app.include_router(scheduler.router)
