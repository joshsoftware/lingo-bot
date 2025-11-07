from fastapi import APIRouter
from fastapi.responses import JSONResponse
import app.core.config as config

router = APIRouter()


@router.get("/internal/bot_user_id")
def get_bot_user_id():
    """Return the cached bot user id and where it was read from.

    Priority: in-process cache -> Redis -> DB fetch
    """
    try:
        uid = getattr(config, '_USER_ID_CACHE', None)
        if uid:
            return JSONResponse({"user_id": uid, "source": "memory"})

        # Try Redis
        try:
            redis_val = config._get_user_id_from_redis()
            if redis_val:
                return JSONResponse({"user_id": redis_val, "source": "redis"})
        except Exception:
            # ignore redis errors here; we'll try DB
            pass

        # Fallback to DB fetch (this may perform a DB call)
        uid2 = config.get_user_id()
        if uid2:
            return JSONResponse({"user_id": uid2, "source": "db"})

        return JSONResponse({"user_id": "", "source": "none"})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)
