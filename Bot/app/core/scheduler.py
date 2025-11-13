from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()
scheduler.start()


import subprocess
import os
import sys
from app.log_config import logger
from dotenv import load_dotenv


load_dotenv(os.path.join(os.path.dirname(__file__), '../../.env'))

def run_meeting_scheduler():
    script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../meeting_scheduler.py'))
    logger.info(f"Running meeting scheduler... script_path {script_path}")
    try:
        process = subprocess.Popen(
            ['python3', script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        logger.info(f"Meeting scheduler process started with PID: {process.pid}")
    except Exception as e:
        logger.error(f"Failed to start meeting scheduler: {str(e)}", exc_info=True)

interval_seconds = int(os.getenv('BOT_SCHEDULER_INTERVAL_SECONDS', '60'))
scheduler.add_job(run_meeting_scheduler, 'interval', seconds=interval_seconds)