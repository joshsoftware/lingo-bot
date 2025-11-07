from fastapi import APIRouter, Depends, HTTPException, Header, Request, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from app.core.config import OAUTH2_SCHEME
import datetime
import requests
from app.helper.generate_presigned_url import generate_presigned_url, extract_file_url
from app.helper.save_transaction import save_transcription
from app.log_config import logger
import redis
from uuid import uuid4
import json
from app.core import config
import os

# Now you can access the values like this:
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
TOKEN_URI = os.getenv("TOKEN_URI")
REDIRECT_URIS = os.getenv("REDIRECT_URIS")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
BOT_ADDED_IN_MEETING_KEY = "bot_added_in_meeting"
MEETING_DETAILS_KEY = "meeting_details"

router = APIRouter(prefix="/meetings", tags=["Meetings"])

LINGO_API_URL = os.getenv("LINGO_API_URL")
GET_MEETING_URL=os.getenv("GET_MEETING_URL")
SCHEDULE_JOIN_BOT_URL=os.getenv("SCHEDULE_JOIN_BOT_URL")
JOIN_METTING_BEFORE_IN_MINUTES = int(os.getenv("JOIN_METTING_BEFORE_IN_MINUTES", 2))  # default to 2 minutes

class LingoRequest(BaseModel):
    key: str
    meeting_details: str

class ScheduleMeeting(BaseModel):
    refresh_token: str
    bot_name: str


@router.get("/")
def get_meetings(body: ScheduleMeeting, token: str = Depends(OAUTH2_SCHEME)):
    logger.info("Received request to fetch and schedule meetings")
    creds = Credentials(
        token=token,
        refresh_token=body.refresh_token,
        token_uri=TOKEN_URI,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET
    )

    service = build('calendar', 'v3', credentials=creds)

    now = datetime.datetime.utcnow().isoformat() + 'Z'
    one_week_later = (datetime.datetime.utcnow() + datetime.timedelta(days=1)).isoformat() + 'Z'

    events_result = service.events().list(
        calendarId='primary',
        timeMin=now,
        timeMax=one_week_later,
        maxResults=10,
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    events = events_result.get('items', [])
    scheduled_meetings = []
    meetings_map = {}
    for event in events:
        meeting_url = event.get('hangoutLink')

        # check is bot request is aleady sent for the meeting
        json_str = redis_client.get(BOT_ADDED_IN_MEETING_KEY)
        if json_str:
            meetings_map = json.loads(json_str)

        if meetings_map and meeting_url in meetings_map.get(body.bot_name):
            logger.info(f" {meeting_url} is requested to be added by bot {body.bot_name} already scheduled. Skipping... ")
            continue

        if meeting_url:
            title = event.get('summary', 'Unnamed Meeting')
            start_time = event['start'].get('dateTime')
            end_time = event['end'].get('dateTime')
            if not start_time or not end_time:
                continue  # Skip all-day events

            # Convert time to the expected format
            meeting_time = datetime.datetime.fromisoformat(start_time).strftime('%Y-%m-%dT%H:%M:%S')
            meeting_end_time = datetime.datetime.fromisoformat(end_time).strftime('%Y-%m-%dT%H:%M:%S')


            current_time = datetime.datetime.now()
            meeting_datetime = datetime.datetime.fromisoformat(meeting_time.replace('Z', '+00:00'))
            time_difference = abs((meeting_datetime - current_time).total_seconds() / 60)

            # skipp the meeting if not within 2 minutes
            if abs(time_difference) > JOIN_METTING_BEFORE_IN_MINUTES:
                if meeting_datetime < current_time:
                    logger.info(f"{title} at {meeting_datetime} is already past. Meeting skipped.")
                else:
                    logger.info(f"{title} at {meeting_datetime} is not within 2 minutes of current time. Skipping...")
                continue

            # set to map for bot has sent request to attendee api
            bot_map = {body.bot_name: []}
            bot_map[body.bot_name].append(meeting_url)
            redis_client.set(BOT_ADDED_IN_MEETING_KEY, json.dumps(bot_map))


            meeting_details = {body.bot_name: []}
            meeting_details[body.bot_name].append({"title": title,"meeting_time": meeting_time})
            redis_client.set(MEETING_DETAILS_KEY, json.dumps(meeting_details))
            logger.info(f"Scheduling bot for upcoming meeting '{title}' at {meeting_time}")
            # Schedule the bot by calling the existing API
            try:
                    response = requests.post(
                        SCHEDULE_JOIN_BOT_URL,
                        headers={"Content-Type": "application/json"},
                        json={
                            "meeting_url": meeting_url,
                            "bot_name": body.bot_name,
                            "meeting_time": meeting_time,
                            "meeting_end_time": meeting_end_time
                        }
                    )
                    message = response.json().get("message", "Failed")
            except Exception as e:
                    logger.error(f"Failed to schedule bot for '{title}': {e}")
                    message = "Failed due to exception"

            scheduled_meetings.append({
                "title": title,
                "meeting_url": meeting_url,
                "status": message
            })

    logger.info("Completed scheduling of all meetings")
    return {"scheduled_meetings": scheduled_meetings}




@router.post("/call-to-lingo")
def call_to_lingo(request: LingoRequest):
    # import pdb; pdb.set_trace()
    logger.info(f"Call Recieved for {request.key}")
    presigned_url = generate_presigned_url(request.key)
    
    if not presigned_url:
        raise HTTPException(status_code=500, detail="Failed to generate presigned URL")
    

    
    file_url = extract_file_url(presigned_url)
    if not file_url:
        raise HTTPException(status_code=500, detail="Failed to extract file URL")
    
    # Step 3: Call the Lingo API
    payload = {
        "documentUrl": file_url,
        "documentName": os.path.basename(request.key)
    }
    
    logger.info("Call to /api/transcribe lingo api")
    response = requests.post(f"{LINGO_API_URL}/api/transcribe", data=json.dumps(payload))
    
    transcribe_response = response.json()


    save_transcription_response = save_transcription(response.json(), file_url, request.meeting_details)
    
    if not save_transcription_response:
        raise HTTPException(status_code=500, detail="Failed to save transcription")

    logger.info("Done!")
    return {
        "message": "Callback received",
        "file_url": file_url,
        "lingo_response": transcribe_response,
        "transcription_response": save_transcription_response
    }
    

@router.post("/watch-calendar")
def watch_calendar(token: str = Depends(OAUTH2_SCHEME), refresh_token: str = Body(..., embed=True)):
    creds = Credentials(
    token=token,
    refresh_token=refresh_token,
    token_uri=TOKEN_URI,
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET
)
    service = build('calendar', 'v3', credentials=creds)
    # Unique channel ID for this watch session
    channel_id = str(uuid4())
    # Expire after 7 days (Google's max for watch)
    expiration_time = int((datetime.datetime.utcnow() + datetime.timedelta(days=7)).timestamp() * 1000)

    body = {
        "id": channel_id,
        "type": "web_hook",
        "address": config.WEBHOOK_ADDR,  # your webhook receiver
        "params": {
            "ttl": "604800"
        },
        "expiration": expiration_time
    }
    response = service.events().watch(calendarId='primary', body=body).execute()
    try: 
        redis_client.set(channel_id, token)

    except Exception as e:
        logger.info(e)
    return {
        "message": "Calendar watch started",
        "channel_id": response.get("id"),
        "resource_id": response.get("resourceId"),
        "expiration": response.get("expiration")
    }


@router.post("/webhook/calendar")
async def calendar_webhook(
    request: Request,
    x_goog_channel_id: str = Header(None),
    x_goog_resource_state: str = Header(None),
    x_goog_resource_id: str = Header(None),
    x_goog_message_number: str = Header(None),
):
    body = await request.body()

    # Log or process headers and body
    logger.info(f"Received Calendar Notification")
    logger.info(f"Channel ID: {x_goog_channel_id}")
    logger.info(f"Resource ID: {x_goog_resource_id}")    
    ttl = redis_client.ttl(x_goog_channel_id)
    logger.info(f"Redis DB info: {redis_client.info('keyspace')}")

    
    for i in range(20):
        token = redis_client.get(str(x_goog_channel_id))
        if token: break

    if token:
        logger.info("Calling /meetings/ endpoint via requests")
        try:
            response = requests.get(
                GET_MEETING_URL,
                headers={"Authorization": f"Bearer {token}"}
            )

            if response.status_code == 200:
                scheduled = response.json().get("scheduled_meetings", [])
                logger.info(f"Meetings scheduled: {len(scheduled)}")
                return {"message": "Webhook received and meetings processed", "scheduled": scheduled}
            else:
                logger.error(f"Failed to fetch meetings. Status: {response.status_code}, Details: {response.text}")
                return JSONResponse(status_code=response.status_code, content=response.json())
        except Exception as e:
            logger.error(f"Error while calling meetings API: {e}")
            return JSONResponse(status_code=500, content={"message": "Internal error", "details": str(e)})
    else:
        logger.warning("Token not found for channel_id.")
        return JSONResponse(status_code=404, content={"message": "Token not found"})

