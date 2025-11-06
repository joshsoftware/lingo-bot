import os
from fastapi.security import OAuth2AuthorizationCodeBearer

# Google OAuth Configuration
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
CLIENT_SECRETS_FILE = 'credentials.json'
REDIRECT_URI = os.getenv("REDIRECT_URIS")

# OAuth2 Scheme
OAUTH2_SCHEME = OAuth2AuthorizationCodeBearer(
    tokenUrl="",
    authorizationUrl="https://accounts.google.com/o/oauth2/auth"
)

# API URLs
SCHEDULE_JOIN_BOT_URL = os.getenv("SCHEDULE_JOIN_BOT_URL")
JOIN_MEETING_URL = os.getenv("JOIN_MEETING_URL")
LINGO_API_URL = os.getenv("LINGO_API_URL")
GET_MEETING_URL = os.getenv("GET_MEETING_URL")
LINGO_CALLBACK_URL = os.getenv("LINGO_CALLBACK_URL")
LINGO_SAVE_TRANSCRIPTION_URL = os.getenv("LINGO_SAVE_TRANSCRIPTION_URL", "https://lingo.ai.joshsoftware.com/api/transcribe/save")

# Redis Configuration
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))

# Server Configuration
BOT_SERVER_HOST = os.getenv("BOT_SERVER_HOST", "0.0.0.0")
BOT_SERVER_PORT = int(os.getenv("BOT_SERVER_PORT", "8001"))

# Google OAuth Credentials
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
TOKEN_URI = os.getenv("TOKEN_URI")

# Webhook Configuration
WEBHOOK_ADDR = os.getenv("WEBHOOK_ADDR")

# User Configuration
USER_ID = os.getenv("USER_ID")
