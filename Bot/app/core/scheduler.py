from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()
scheduler.start()


# import subprocess
# import os
# import sys
# from app.log_config import logger
# from dotenv import load_dotenv


# load_dotenv(os.path.join(os.path.dirname(__file__), '../../.env'))

# def run_meeting_scheduler():
#     logger.info("Running meeting scheduler...")
#     script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../meeting_scheduler.py'))
#     subprocess.Popen(['python3', script_path])

# interval_seconds = int(os.getenv('BOT_SCHEDULER_INTERVAL_SECONDS', '60'))
# scheduler.add_job(run_meeting_scheduler, 'interval', seconds=60)