import time
import functools
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
import logging
from research_copilot.logging import get_logger

logger = get_logger("retry")

# Retry decorator for OpenAI calls
def retry_openai(func):
    """
    Retry decorator for OpenAI API calls.
    Handles rate limits (429) and transient 5xx errors.
    3 attempts, exponential backoff: 1s → 2s → 4s
    """
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type((Exception,)),
        before_sleep=before_sleep_log(
            logging.getLogger("tenacity"), logging.WARNING
        ),
        reraise=True,
    )
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper


# Retry decorator for Pinecone calls
def retry_pinecone(func):
    """
    Retry decorator for Pinecone operations.
    Slightly more lenient — up to 4 attempts.
    """
    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((Exception,)),
        reraise=True,
    )
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper


def timed(label: str):
    """
    Decorator that logs execution time of any function.
    Usage: @timed("summarization_llm_call")
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            result = func(*args, **kwargs)
            elapsed = round(time.time() - start, 3)
            logger.info("timed_call", label=label, elapsed_s=elapsed)
            return result
        return wrapper
    return decorator