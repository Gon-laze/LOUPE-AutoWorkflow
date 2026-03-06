from __future__ import annotations

from pathlib import Path

import uvicorn

from service import settings


def ensure_runtime_dirs() -> None:
    # Ensure runtime paths exist before server boot.
    Path(settings.runtime_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.log_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    ensure_runtime_dirs()
    uvicorn.run(
        "service:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=False,
        log_level=settings.log_level.lower(),
    )
