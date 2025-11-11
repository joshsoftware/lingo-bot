import os
import time
import redis
from fastapi import FastAPI
from app.api import auth, meetings, scheduler, internal
from app.core.scheduler import scheduler as apscheduler
from starlette.middleware.cors import CORSMiddleware
from app.log_config import logger
import app.core.config as config

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
    # Retry a few times in case Redis isn't ready yet
    max_attempts = 10
    for attempt in range(1, max_attempts + 1):
        try:
            # ping ensures connection is established
            r.ping()
            r.delete(redis_key)
            logger.info(f"Cleaned up Redis key: {redis_key} on startup.")
            break
        except Exception as e:
            if attempt == max_attempts:
                logger.error(f"Failed to connect to Redis to cleanup key '{redis_key}': {e}")
                break
            sleep_seconds = 1 * attempt
            logger.info(f"Redis not ready (attempt {attempt}/{max_attempts}). Retrying in {sleep_seconds}s...")
            time.sleep(sleep_seconds)


@app.on_event("startup")
def startup_event():
    if not apscheduler.running:
        logger.info("Starting scheduler...")
        apscheduler.start()
    else:
        logger.info("Scheduler already running.")
    # Fetch and cache the bot USER_ID from the session table so it's available
    # to other modules and so we log any DB connection issues at startup.
    try:
        uid = config.get_user_id()
        if uid:
            logger.info(f"Fetched USER_ID from DB: {uid}")
        else:
            logger.warning("Fetched empty USER_ID from DB; check DATABASE_URL and session table")
    except Exception:
        logger.exception("Error while fetching USER_ID on startup")

@app.on_event("shutdown")
def shutdown_event():
    logger.info("Shutting down scheduler...")
    apscheduler.shutdown()

cleanup_redis_on_startup("meeting_states")
cleanup_redis_on_startup("bot_added_in_meeting")

app.include_router(auth.router)
app.include_router(meetings.router)
app.include_router(scheduler.router)
app.include_router(internal.router)
