"""Production entry point (Render / Docker).

Environment variables:
  DATABASE_URL      postgres://... (Neon) - required on Render, the local disk is wiped on restart
  INVITE_CODE       optional; when set, registering requires this code
  REGISTRATION      "open" (default) or "closed"
  CONFIG_PATH       optional config.yaml path
  PORT              set by Render
"""

from __future__ import annotations

import logging
import os

from ..config import load_config
from .app import create_app

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def build():
    return create_app(
        load_config(os.environ.get("CONFIG_PATH")),
        db_url=os.environ.get("DATABASE_URL", "jobs.db"),
        invite_code=os.environ.get("INVITE_CODE") or None,
        secure_cookies=os.environ.get("SECURE_COOKIES", "1") != "0",
        registration_open=os.environ.get("REGISTRATION", "open") != "closed",
    )



def main() -> None:
    import uvicorn

    uvicorn.run("jobsearch_il.web.server:build", factory=True, host="0.0.0.0",
                port=int(os.environ.get("PORT", "8000")), proxy_headers=True, forwarded_allow_ips="*")


if __name__ == "__main__":
    main()
