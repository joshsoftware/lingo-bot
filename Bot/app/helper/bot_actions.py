import requests
import time
import os

def join_meeting_with_retries(meeting_url: str, bot_name: str):
    print("DEPRECATED FUNCTION - join_meeting_with_retry in bot_actions.py")
    f = True
    if f:
        return
    attendee_api_key = os.getenv("ATTENDEE_API_KEY")
    JOIN_MEETING_URL=os.getenv("JOIN_MEETING_URL")
    headers={
        "Authorization": f"Token {attendee_api_key}",
        "Content-Type": "application/json"
    }
    while True:
        print(f"Joining meeting: {meeting_url} with bot: {bot_name}")
        response = requests.post(
            JOIN_MEETING_URL,
            headers=headers,
            json={"meeting_url": meeting_url, "bot_name": bot_name}
        )
        print(f"Join bot response: {response.status_code}, {response.text}")

        if response.status_code == 201:
            bot_id = response.json().get("id")
            print(f"Bot created with ID: {bot_id}")

            while True:
                status_response = requests.get(
                    f"{JOIN_MEETING_URL}/{bot_id}",
                    headers=headers
                )
                status_data = status_response.json()
                print(f"Bot status: {status_data}")

                if status_data.get("state") in ["joined_recording", "joined"]:
                    print("Bot joined successfully")
                    return
                elif status_data.get("state") == "fatal_error":
                    print("Bot failed to join. Retrying...")
                    break

                print("Retrying bot status check in 30 seconds...")
                time.sleep(30)

        print("Retrying bot join in 30 seconds...")
        time.sleep(30)
