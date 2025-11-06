import requests
from app.core.config import USER_ID, LINGO_SAVE_TRANSCRIPTION_URL

def save_transcription(response, document_url, document_name):
    # Prepare the payload
    # import pdb; pdb.set_trace()
    payload = {
        "documentUrl": document_url,
        "userID": USER_ID,
        "documentName": document_name,
        "summary": response["summary"],
        "translation": response["translation"],
        "audioDuration": response.get("audioDuration", 0),  # Assuming you might add this later
        "segments": response["segments"]
    }
    
    # Send the POST request
    try:
        res = requests.post(LINGO_SAVE_TRANSCRIPTION_URL, json=payload)
        res.raise_for_status()  # Raise an exception for HTTP errors (4xx, 5xx)
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        return None



