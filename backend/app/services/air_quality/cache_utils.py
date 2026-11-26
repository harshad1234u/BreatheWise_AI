import asyncio
from collections import OrderedDict
from typing import Any, Awaitable, Callable, Dict, TypeVar

T = TypeVar("T")


def set_bounded_lru(
    cache: OrderedDict[str, Any],
    key: str,
    value: Any,
    max_entries: int,
) -> None:
    """Stores an entry as most-recently-used and evicts oldest entries beyond max_entries."""
    cache[key] = value
    cache.move_to_end(key)
    while len(cache) > max(1, max_entries):
        cache.popitem(last=False)


def _consume_unretrieved_exception(task: asyncio.Task) -> None:
    if not task.cancelled():
        try:
            task.exception()
        except Exception:
            pass


async def run_coalesced(
    in_flight: Dict[str, asyncio.Task],
    key: str,
    coro_factory: Callable[[], Awaitable[T]],
) -> T:
    """
    Single-flight coalescing across concurrent callers for the same cache key.
    Uses asyncio.shield so cancellation of one caller does not abort shared upstream
    work for other callers, while guaranteeing in-flight cleanup on success or failure.
    """
    task = in_flight.get(key)
    if task is None or task.done():
        async def _runner() -> T:
            try:
                return await coro_factory()
            finally:
                if in_flight.get(key) is task:
                    in_flight.pop(key, None)

        task = asyncio.create_task(_runner())
        task.add_done_callback(_consume_unretrieved_exception)
        in_flight[key] = task

    return await asyncio.shield(task)
