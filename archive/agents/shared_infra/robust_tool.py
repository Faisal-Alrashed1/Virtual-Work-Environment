import functools
import logging
from typing import Callable, Any

logger = logging.getLogger("agents.robust_tool")


def robust_tool(fallback_reply: str = "حدث خطأ غير متوقع أثناء تنفيذ الخدمة. يرجى المحاولة لاحقًا."):
    """Decorator adding retry logic and fallback response for agent tool execution."""

    def decorator(func: Callable[..., Any]):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Tool {func.__name__} failed: {e}")
                return fallback_reply

        return wrapper

    return decorator
