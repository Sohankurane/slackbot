"""Logging setup."""

import logging
import sys

from app.config import get_settings
from app.core.context import current_bot_slug, current_tenant_slug


class ContextFilter(logging.Filter):
    """Injects tenant/bot info into every LogRecord."""

    def filter(self, record: logging.LogRecord) -> bool:
        tenant = current_tenant_slug.get()
        bot = current_bot_slug.get()
        if tenant or bot:
            record.ctx = f"[tenant={tenant or '-'} bot={bot or '-'}] "
        else:
            record.ctx = ""
        return True


def setup_logging() -> None:
    settings = get_settings()
    root = logging.getLogger()
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)-7s %(name)s %(ctx)s%(message)s",
            datefmt="%H:%M:%S",
        )
    )
    handler.addFilter(ContextFilter())

    root.addHandler(handler)
    root.setLevel(settings.log_level.upper())

    # Quiet down noisy libs
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)