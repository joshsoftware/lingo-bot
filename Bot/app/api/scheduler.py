from fastapi import APIRouter
from app.core.scheduler import scheduler
from app.core.join import join_meeting_with_retry

from app.models.schemas import ScheduleBotRequest
from app.log_config import logger
import os

router = APIRouter(prefix="/scheduler", tags=["Scheduler"])
JOIN_MEETING_URL = os.getenv("JOIN_MEETING_URL")



@router.post("/schedule-join-bot")
def schedule_join_bot(request: ScheduleBotRequest):
    meeting_url = request.meeting_url
    bot_name = request.bot_name
    meeting_time = request.meeting_time
    meeting_end_time = request.meeting_end_time

    join_meeting_with_retry(meeting_url, bot_name)
    return {"message": "Job scheduled", "meeting_url": meeting_url, "meeting_time": meeting_time, "meeting_end_time": meeting_end_time}


@router.get("/scheduled-jobs")
def get_scheduled_jobs():
    jobs = scheduler.get_jobs()
    return [job.id for job in jobs]


@router.delete("/stop-all-jobs")
def stop_all_jobs():
    jobs = scheduler.get_jobs()
    for job in jobs:
        scheduler.remove_job(job.id)
    return {"message": "All jobs stopped."}


