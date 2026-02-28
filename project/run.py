import uvicorn

from service import settings


if __name__ == "__main__":
    uvicorn.run("service:app", host=settings.app_host, port=settings.app_port, reload=False, log_level=settings.log_level.lower())
