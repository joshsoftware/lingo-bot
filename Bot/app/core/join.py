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

# Attendee API configuration
ATTENDEE_API_BASE_URL = os.getenv("ATTENDEE_API_BASE_URL", "http://attendee-app-local:8002")
API_KEY_CACHE = {}  # Simple in-memory cache for API keys


def get_api_key_for_bot(bot_name: str) -> str:
    """Get the API key for a specific bot by calling the attendee API

    This function calls an API endpoint in the attendee service to retrieve
    the API key for a bot. It caches the result to avoid repeated API calls.

    Args:
        bot_name: Name of the bot

    Returns:
        Plain text API key string or None if not found
    """
    # Check cache first
    if bot_name in API_KEY_CACHE:
        logger.debug(f"Using cached API key for bot '{bot_name}'")
        return API_KEY_CACHE[bot_name]

    try:
        # Call attendee API to get the API key for the bot
        # Endpoint returns the bot's project's API key object_id
        url = f"{ATTENDEE_API_BASE_URL}/api/v1/bots/{bot_name}/api-key"

        # If we have an internal secret configured, forward it so attendee
        # can return a plaintext API key for authorized callers.
        headers = {}
        internal_secret = os.getenv("ATTENDEE_INTERNAL_SECRET")
        if internal_secret:
            headers["X-ATTENDEE-SECRET"] = internal_secret

        response = requests.get(url, headers=headers or None, timeout=10)

        if response.status_code == 200:
            data = response.json()
            # If attendee returns a plaintext api_key (when called with internal secret), use it directly
            api_key_plain = data.get("api_key")
            if api_key_plain:
                API_KEY_CACHE[bot_name] = api_key_plain
                logger.info(f"Retrieved plaintext API key from attendee for bot '{bot_name}'")
                return api_key_plain
            # The API returns the object_id, but we need the plain text key
            # Try to get it from environment: API_KEY_{object_id}
            api_key_object_id = data.get("api_key_object_id")
            if api_key_object_id:
                # Try to retrieve the plain text key from environment variables
                api_key = os.getenv(f"API_KEY_{api_key_object_id}")
                if api_key:
                    # Cache the API key
                    API_KEY_CACHE[bot_name] = api_key
                    logger.info(f"Retrieved API key from environment for bot '{bot_name}' (object_id: {api_key_object_id})")
                    return api_key
                else:
                    logger.warning(f"API key object_id found ({api_key_object_id}) but plain text key not in environment for bot '{bot_name}'")
                    return None
        elif response.status_code == 404:
            logger.warning(f"Bot '{bot_name}' not found in attendee service")
            return None
        else:
            logger.error(f"Attendee API returned status {response.status_code}: {response.text}")
            return None

    except requests.exceptions.Timeout:
        logger.error(f"Timeout calling attendee API for bot '{bot_name}'")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Error calling attendee API for bot '{bot_name}': {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Failed to get API key for bot '{bot_name}': {str(e)}", exc_info=True)
        return None


def join_meeting_with_retry(meeting_url, bot_name):
    meetings_map = {}
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    json_str = redis_client.get(REDIS_KEY)
    if json_str:
        meetings_map = json.loads(json_str)
                
    if meetings_map.get(meeting_url, "") in ["joined", "joined_recording", "joining"]:
        logger.info(f"Meeting {meeting_url} already in progress with state: {meetings_map[meeting_url]}")
        return

    attendee_api_key = get_api_key_for_bot(bot_name)
    if not attendee_api_key:
        logger.error(f"Failed to retrieve API key for bot '{bot_name}'. No key in database or environment.")
        return

    logger.info(f"Retrieved API key for bot '{bot_name}' from database")

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