from fastapi.security import OAuth2AuthorizationCodeBearer
import os
import asyncio
import asyncpg
import redis
from app.log_config import logger

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

# Database URL used to fetch the bot's user id from the session table in
# the postgres-lingo-db container. If DATABASE_URL is not set we will attempt
# to construct one from PG_* env vars (PG_USER, PG_PASS, PG_HOST, PG_PORT, DB_NAME).
DATABASE_URL = os.getenv('DATABASE_URL')
REDIS_HOST = os.getenv('REDIS_HOST', 'redis')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
# TTL (seconds) for cached USER_ID in Redis. Default 24 hours.
REDIS_USER_ID_TTL = int(os.getenv('REDIS_USER_ID_TTL', 24 * 3600))


def _build_db_url_from_env():
    user = os.getenv('PG_USER')
    password = os.getenv('PG_PASS')
    host = os.getenv('PG_HOST')
    port = os.getenv('PG_PORT')
    db = os.getenv('DB_NAME')
    if user and password and host and port and db:
        return f"postgres://{user}:{password}@{host}:{port}/{db}"
    return None


# Internal cache for fetched user id
_USER_ID_CACHE = None


def _get_redis_client():
    try:
        return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    except Exception:
        logger.exception('Unable to create Redis client')
        return None


def _get_user_id_from_redis(key='bot:user_id'):
    """Return user id from redis if present, else None."""
    try:
        r = _get_redis_client()
        if not r:
            return None
        val = r.get(key)
        return val
    except Exception:
        logger.exception('Error reading USER_ID from Redis')
        return None


def _set_user_id_in_redis(value, key='bot:user_id', ttl=REDIS_USER_ID_TTL):
    try:
        r = _get_redis_client()
        if not r:
            return False
        r.set(key, value, ex=ttl)
        return True
    except Exception:
        logger.exception('Error writing USER_ID to Redis')
        return False

async def _fetch_user_id_async(db_url: str):
    try:
        conn = await asyncpg.connect(dsn=db_url)
        print("Connected successfully!")

        try:
            query = "SELECT user_id FROM session LIMIT 1"
            val = await conn.fetchval(query)
            if val:
                return str(val)
            return ''

        finally:
            await conn.close()

    except Exception as e:
        logger.exception("Error fetching USER_ID from DB ")
        return ''



def get_user_id():
    """Synchronous helper that returns the USER_ID, fetching it from DB if needed.

    This will cache the value after the first successful fetch. If there is no
    DATABASE_URL configured or an error occurs, an empty string is returned.
    """
    global _USER_ID_CACHE
    # Return in-process cache if present
    if _USER_ID_CACHE is not None:
        return _USER_ID_CACHE

    # Check Redis cache before hitting the DB
    try:
        redis_val = _get_user_id_from_redis()
        if redis_val:
            _USER_ID_CACHE = redis_val
            logger.debug('USER_ID loaded from Redis cache')
            return _USER_ID_CACHE
    except Exception:
        # _get_user_id_from_redis already logs exceptions; continue to DB
        pass

    db_url = DATABASE_URL or _build_db_url_from_env()
    print( "Database URL:", db_url)
    if not db_url:
        logger.error('No DATABASE_URL or PG_* env vars set; cannot fetch USER_ID')
        _USER_ID_CACHE = ''
        return _USER_ID_CACHE

    try:
        # If an event loop is already running (e.g. FastAPI startup), use
        # run_coroutine_threadsafe, otherwise use asyncio.run
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            # run coroutine in running loop thread-safely. Don't block too long
            # waiting for it; attach a callback so the cache is populated when
            # the coroutine finishes.
            fut = asyncio.run_coroutine_threadsafe(_fetch_user_id_async(db_url), loop)

            def _on_fut_done(future):
                try:
                    res = future.result()
                    if res:
                        # populate in-process cache and Redis
                        global _USER_ID_CACHE
                        _USER_ID_CACHE = res
                        try:
                            _set_user_id_in_redis(res)
                        except Exception:
                            pass
                except Exception:
                    logger.exception('Error in background USER_ID fetch')

            fut.add_done_callback(_on_fut_done)

            try:
                # wait briefly for the result in case DB is fast
                _USER_ID_CACHE = fut.result(timeout=3)
            except Exception:
                # Timeout or other error: we won't block; callback will fill cache
                logger.warning('USER_ID fetch timed out; continuing without blocking')
        else:
            _USER_ID_CACHE = asyncio.run(_fetch_user_id_async(db_url))
    except Exception:
        logger.exception('Failed to fetch USER_ID synchronously')
        _USER_ID_CACHE = ''

    # Store in Redis for cross-process caching if possible
    try:
        if _USER_ID_CACHE:
            _set_user_id_in_redis(_USER_ID_CACHE)
    except Exception:
        # _set_user_id_in_redis logs exceptions
        pass

    return _USER_ID_CACHE


# USER_ID is always fetched from the DB session table; do NOT read it from
# environment variables anymore. Code should prefer calling get_user_id(),
# but we keep a `USER_ID` symbol for backwards compatibility (populated from DB).
USER_ID = get_user_id()

WEBHOOK_ADDR = os.getenv('WEBHOOK_ADDR', '')
