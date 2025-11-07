from app.log_config import logger
import os
import requests
import time
import redis
import json

JOIN_MEETING_URL = os.getenv("JOIN_MEETING_URL")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_KEY = "meeting_states"



def join_meeting_with_retry(meeting_url, bot_name):
    meetings_map = {}
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    json_str = redis_client.get(REDIS_KEY)
    if json_str:
        meetings_map = json.loads(json_str)
                
    if meetings_map.get(meeting_url, "") in ["joined", "joined_recording", "joining"]:
        logger.info(f"Meeting {meeting_url} already in progress with state: {meetings_map[meeting_url]}")
        return
    
    attendee_api_key = os.getenv("ATTENDEE_API_KEY")
    headers={
        "Authorization": f"Token {attendee_api_key}",
        "Content-Type": "application/json"
    }

    bot_id = None
    
    logger.info(f"Joining meeting: {meeting_url} with bot: {bot_name}")
    response = requests.post(
        JOIN_MEETING_URL,
        headers=headers,
        json={"meeting_url": meeting_url, "bot_name": bot_name}
    )
    logger.info(f"Join bot response: {response.status_code}, {response.text}")
    if response.status_code != 201:
        logger.info(f"Failed to create bot for joining meeting: {meeting_url}")
        return
    
    bot_id = response.json().get("id")
    if not bot_id:
        logger.info(f"Joining meeting failed")
        return

    logger.info(f"Bot created with ID: {bot_id}")
    meetings_map[meeting_url] = response.json().get("state")
    redis_client.set(REDIS_KEY, json.dumps(meetings_map))
    
    retry_count = 0
    while True:
        if retry_count >= 5:
            logger.info("Max retry of joining meeting exceeded")
            return
        retry_count += 1
        status_response = requests.get(
                    f"{JOIN_MEETING_URL}/{bot_id}",
                    headers=headers
                )

        status_data = status_response.json()
        state = status_data.get("state")
        meetings_map[meeting_url] = state
        redis_client.set(REDIS_KEY, json.dumps(meetings_map))
        
        if state not in ["joined_recording", "joined"]:
            time.sleep(10)
            continue

        if state in ["joined_recording", "joined"]:
            logger.info(f"{bot_name} Bot joined successfully into {meeting_url} ")
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