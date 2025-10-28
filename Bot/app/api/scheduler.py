from fastapi import APIRouter
from app.core.scheduler import scheduler
from app.models.schemas import ScheduleBotRequest
import requests
import time
import threading
from app.log_config import logger
import os

router = APIRouter(prefix="/scheduler", tags=["Scheduler"])
JOIN_MEETING_URL = os.getenv("JOIN_MEETING_URL")


def is_meeting_scheduled(meeting_url: str) -> bool:
    """Return True if a job for the given meeting_url is already scheduled.

    We use the meeting_url as the job id (same convention used when adding jobs).
    """
    try:
        job = scheduler.get_job(meeting_url)
        return job is not None
    except Exception:
        # If scheduler backend doesn't support get_job or another error occurs,
        # fall back to scanning jobs.
        jobs = scheduler.get_jobs()
        for job in jobs:
            if job.id == meeting_url:
                return True
        return False


def list_bot_upcoming_events():
    """Return a list of upcoming scheduled jobs (id and next_run_time).

    This is a lightweight helper for callers that want to show scheduled bot
    joins.
    """
    events = []
    jobs = scheduler.get_jobs()
    for job in jobs:
        # job.next_run_time may be a datetime or None; stringify for JSON safety
        events.append({"id": job.id, "next_run_time": str(job.next_run_time)})
    return events


def background_join_meeting(meeting_url, bot_name):
    logger.info(f"## DEBUG - background_join_meeting {time.time()}")
    """Runs join logic in a separate thread."""
    thread = threading.Thread(target=join_meeting_with_retry, args=(meeting_url, bot_name))
    thread.start()

def join_meeting_with_retry(meeting_url, bot_name):
    logger.info(f"## DEBUG - CALLING JOIN MEETING at {time.time()}")
    attendee_api_key = os.getenv("ATTENDEE_API_KEY")
    headers={
        "Authorization": f"Token {attendee_api_key}",
        "Content-Type": "application/json"
    }

    bot_id = None
    retry_count = 0
    while True:
        if retry_count >= 10:
            break
        retry_count += 1
        logger.info(f"Joining meeting: {meeting_url} with bot: {bot_name}")
        response = requests.post(
            JOIN_MEETING_URL,
            headers=headers,
            json={"meeting_url": meeting_url, "bot_name": bot_name}
        )
        logger.info(f"Join bot response: {response.status_code}, {response.text}")
        if response.status_code == 201:
            bot_id = response.json().get("id")
            logger.info(f"Bot created with ID: {bot_id}")
            break

        time.Sleep(5)
        logger.info("Retrying bot join in 5 seconds...")
    
    if not bot_id:
        logger.info(f"Joining meeting failed")
        return
    
    retry_count = 0
    while True:
        if retry_count >= 10:
            logger.info("Max retry of joining meeting exceeded")
            return
        retry_count += 1
        status_response = requests.get(
                    f"{JOIN_MEETING_URL}/{bot_id}",
                    headers=headers
                )
        status_data = status_response.json()
        logger.info(f"[####TEST] Bot status: {status_data}")
        state = status_data.get("state")
        if state not in ["joined_recording", "joined"]:
            time.sleep(5)
            continue

        if state in ["joined_recording", "joined"]:
            logger.info("Bot joined successfully")
            return


    """while True:
        logger.info(f"Joining meeting: {meeting_url} with bot: {bot_name}")
        response = requests.post(
            JOIN_MEETING_URL,
            headers=headers,
            json={"meeting_url": meeting_url, "bot_name": bot_name}
        )
        logger.info(f"Join bot response: {response.status_code}, {response.text}")

        if response.status_code == 201:
            bot_id = response.json().get("id")
            logger.info(f"Bot created with ID: {bot_id}")

            # Check bot status until success or meeting ends
            while True:
                status_response = requests.get(
                    f"{JOIN_MEETING_URL}/{bot_id}",
                    headers=headers
                )
                status_data = status_response.json()
                logger.info(f"[####TEST] Bot status: {status_data}")

                if status_data.get("state") in ["joining"]:
                    logger.info("Waiting for bot to join...")
                    # check status 
                    # if joined, then break, otherwise sleep and retry get
                    while True:
                        time.sleep(5)
                        status_response = requests.get(
                            f"{JOIN_MEETING_URL}/{bot_id}",
                            headers=headers
                        )
                        status_data = status_response.json()
                        logger.info(f"Waiting for user action ... Getting status: {status_data}")
                        if status_data.get("state") in ["joined_recording", "joined"]:
                            logger.info("Bot joined successfully")
                            return
                        elif status_data.get("state") == "fatal_error":
                            logger.info("Bot failed to join. Retrying...")
                # if status_data.get("state") in ["joined_recording", "joined"]:
                #     logger.info("Bot joined successfully")
                #     return
                # elif status_data.get("state") == "fatal_error":
                #     logger.info("Bot failed to join. Retrying...")
                #     break

                logger.info("Retrying bot status check in 30 seconds...")
                time.sleep(30)

        logger.info("Retrying bot join in 30 seconds...")
        time.sleep(30)"""

@router.post("/schedule-join-bot")
async def schedule_join_bot(request: ScheduleBotRequest):
    logger.info(f"[@@@ DEBUG ###] schedule-join-bot ..: {request}")
    meeting_url = request.meeting_url
    bot_name = request.bot_name
    meeting_time = request.meeting_time
    meeting_end_time = request.meeting_end_time


    # If a job for this meeting_url is already scheduled, skip creating another
    if is_meeting_scheduled(meeting_url):
        logger.info(f"Schedule request ignored: job for {meeting_url} already exists")
        return {"message": "Job already scheduled", "meeting_url": meeting_url, "meeting_time": meeting_time, "meeting_end_time": meeting_end_time}

    # Schedule the job at the meeting time and keep retrying until meeting ends
    scheduler.add_job(background_join_meeting, 'date', run_date=meeting_time, id=meeting_url, replace_existing=True, kwargs={"meeting_url": meeting_url, "bot_name": bot_name})
    return {"message": "Job scheduled", "meeting_url": meeting_url, "meeting_time": meeting_time, "meeting_end_time": meeting_end_time}


@router.get("/scheduled-jobs")
def get_scheduled_jobs():
    jobs = scheduler.get_jobs()
    return [job.id for job in jobs]


@router.get("/upcoming-events")
def upcoming_events():
    """Return a list of upcoming scheduled bot join events.

    Each item returns the job id and next_run_time.
    """
    return list_bot_upcoming_events()


@router.delete("/stop-all-jobs")
def stop_all_jobs():
    jobs = scheduler.get_jobs()
    for job in jobs:
        scheduler.remove_job(job.id)
    return {"message": "All jobs stopped."}

