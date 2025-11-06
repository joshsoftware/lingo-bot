import uvicorn
import os

if __name__ == "__main__":
    host = os.getenv("BOT_SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("BOT_SERVER_PORT", "8001"))
    uvicorn.run("app.main:app", host=host, port=port, reload=True)
