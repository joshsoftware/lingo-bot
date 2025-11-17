import os
import requests
import json
import app.core.config as config
from app.log_config import logger

def save_transcription(response, document_url, document_name, user_id):
    # Prepare the payload
    # import pdb; pdb.set_trace()
    payload = {
        "documentUrl": document_url,
        "userID": user_id,
        "documentName": document_name,
        "summary": response["summary"],
        "translation": response["translation"],
        "audioDuration": response.get("audioDuration", 0),  # Assuming you might add this later
        "segments": response["segments"],
        "detectedLanguage": response["detected_language"]
    }
    
    logger.info(f"UMV : Payload for saving transcription: \n{payload}")
    # API endpoint
    #endpoint = "https://lingo.ai.joshsoftware.com/api/transcribe/save"
    endpoint = os.getenv("LINGO_API_URL") + "/api/transcribe/save"
    
    # Send the POST request
    # If USER_ID is empty, warn (helps debugging when DB lookup failed)
    if not payload.get("userID"):
        logger.warning("USER_ID is empty in transcription payload; check DB fetch and configuration")

    try:
        res = requests.post(endpoint, data=json.dumps(payload))
        res.raise_for_status()  # Raise an exception for HTTP errors (4xx, 5xx)
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        return None



