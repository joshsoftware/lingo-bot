import asyncio
import aiohttp
import asyncpg
import logging
from datetime import datetime
import os

# Configuration
PG_USER = os.getenv("PG_USER")
PG_PASS = os.getenv("PG_PASS")
PG_HOST = os.getenv("PG_HOST")
PG_PORT = os.getenv("PG_PORT")
DB_NAME = os.getenv("DB_NAME")
SQL_QUERY = 'SELECT "accessToken", "refreshToken", "botName" FROM bot;'
PG_CONN_STRING = f"postgresql://{PG_USER}:{PG_PASS}@{PG_HOST}:{PG_PORT}/{DB_NAME}"
GOOGLE_TOKEN_URL = os.getenv("GOOGLE_TOKEN_URL")  # Google's token endpoint
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Refresh access token using refresh token
async def refresh_google_access_token(session, refresh_token, bot_name):
    """
    Refresh Google OAuth access token using refresh token
    Returns new tokens or None if failed
    """
    try:
        # Google OAuth refresh token payload
        refresh_payload = {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token"
        }
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        async with session.post(
            GOOGLE_TOKEN_URL,
            data=refresh_payload,  # Use 'data' for form-encoded
            headers=headers,
            timeout=10
        ) as response:
            
            if response.status == 200:
                token_data = await response.json()
                new_access_token = token_data.get("access_token")
                expires_in = token_data.get("expires_in", 3600)  # Default 1 hour
                
                logger.info(f"Bot: {bot_name} -> Google token refreshed successfully (expires in {expires_in}s)")
                return {
                    "access_token": new_access_token,
                    "refresh_token": refresh_token,  # Google typically doesn't return new refresh token
                    "expires_in": expires_in
                }
            else:
                error_data = await response.json()
                error_msg = error_data.get("error_description", "Unknown error")
                logger.error(f"Bot: {bot_name} -> Google token refresh failed: {response.status} - {error_msg}")
                return None
                
    except Exception as e:
        logger.error(f"Bot: {bot_name} -> Google token refresh error: {e}")
        return None
# Update tokens in database
async def update_tokens_in_db(bot_id, new_access_token, new_refresh_token=None):
    """
    Update access token and refresh token in database
    """
    try:
        conn = await asyncpg.connect(PG_CONN_STRING)
        
        if new_refresh_token:
            # Update both tokens
            update_query = """
                UPDATE bot 
                SET accessToken = $1, refreshToken = $2, updated_at = $3
                WHERE id = $4
            """
            await conn.execute(update_query, new_access_token, new_refresh_token, datetime.now(), bot_id)
        else:
            # Update only access token
            update_query = """
                UPDATE bot
                SET accessToken = $1, updated_at = $2
                WHERE id = $3
            """
            await conn.execute(update_query, new_access_token, datetime.now(), bot_id)
        
        await conn.close()
        logger.info(f"Bot ID: {bot_id} -> Tokens updated in database")
        return True
        
    except Exception as e:
        logger.error(f"Bot ID: {bot_id} -> Database update error: {e}")
        return False

# Get tokens from database
async def get_tokens_from_db():
    """
    Fetch all tokens from database
    """
    try:
        conn = await asyncpg.connect(PG_CONN_STRING)
        query = 'SELECT id, "accessToken", "refreshToken", "botName" FROM bot'
        rows = await conn.fetch(query)
        await conn.close()
        
        return [
            {
                "id": row["id"],
                "access_token": row["accessToken"],
                "refresh_token": row["refreshToken"],
                "bot_name": row["botName"],
            }
            for row in rows
        ]
    except Exception as e:
        logger.error(f"Database fetch error: {e}")
        return []

# Refresh and update single token
async def refresh_and_update_token(session, token_data):
    """
    Refresh token and update in database
    """
    refresh_result = await refresh_google_access_token(
        session,
        token_data['refresh_token'],
        token_data['bot_name']
    )
    
    if refresh_result:
        success = await update_tokens_in_db(
            token_data['id'],
            refresh_result['access_token'],
            refresh_result['refresh_token']
        )
        return success
    return False

# Main function to refresh all tokens
async def refresh_all_tokens():
    """
    Refresh all tokens in database
    """
    tokens = await get_tokens_from_db()
    logger.info(f"Found {len(tokens)} tokens to refresh")
    
    async with aiohttp.ClientSession() as session:
        tasks = [refresh_and_update_token(session, token) for token in tokens]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        successful = sum(1 for result in results if result is True)
        logger.info(f"Refresh completed: {successful}/{len(tokens)} tokens updated")

# Entry point
if __name__ == "__main__":
    asyncio.run(refresh_all_tokens())