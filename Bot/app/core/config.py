from fastapi.security import OAuth2AuthorizationCodeBearer
import os

# OAuth2 / Google settings
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
CLIENT_SECRETS_FILE = os.getenv('CLIENT_SECRETS_FILE', 'credentials.json')
REDIRECT_URI = os.getenv('REDIRECT_URIS', '')

# Provide an OAuth2 dependency for endpoints that expect a bearer token.
# The original code used an OAUTH2_SCHEME symbol imported from here.
OAUTH2_SCHEME = OAuth2AuthorizationCodeBearer(
    tokenUrl="",
    authorizationUrl="https://accounts.google.com/o/oauth2/auth",
)

# Other config values used elsewhere in the app
USER_ID = os.getenv('USER_ID', '')
WEBHOOK_ADDR = os.getenv('WEBHOOK_ADDR', '')
