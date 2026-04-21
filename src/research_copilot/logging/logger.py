import logging
import structlog
from rich.logging import RichHandler
from research_copilot.config import get_settings


def setup_logging():
    """
    Configure structlog with Rich console output for development
    and JSON output for production.
    Called once at app startup.
    """
    settings = get_settings()
    is_dev = settings.app_env == "development"

    # Configure standard logging to use Rich in dev
    logging.basicConfig(
        level=logging.DEBUG if is_dev else logging.INFO,
        handlers=[RichHandler(rich_tracebacks=True, show_path=False)],
        format="%(message)s",
    )

    # Shared processors for all environments
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if is_dev:
        # Pretty colored output in dev
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True)
        ]
    else:
        # JSON lines in production (for log aggregators)
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG if is_dev else logging.INFO
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str):
    """Get a named structured logger. Use this everywhere instead of print()."""
    return structlog.get_logger(name)