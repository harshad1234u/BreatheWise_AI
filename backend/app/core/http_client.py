import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator, Callable, Optional
import httpx

_shared_client: Optional[httpx.AsyncClient] = None
_shared_loop: Optional[asyncio.AbstractEventLoop] = None


def _build_pooled_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
        timeout=httpx.Timeout(15.0, connect=4.0),
    )


async def init_http_client() -> httpx.AsyncClient:
    """Initializes the shared pooled httpx.AsyncClient bound to the current event loop."""
    global _shared_client, _shared_loop
    loop = asyncio.get_running_loop()
    if _shared_client is not None and not _shared_client.is_closed and _shared_loop is loop:
        return _shared_client
    if _shared_client is not None and not _shared_client.is_closed:
        await _shared_client.aclose()
    _shared_client = _build_pooled_client()
    _shared_loop = loop
    return _shared_client


async def close_http_client() -> None:
    """Closes the shared pooled httpx.AsyncClient cleanly during FastAPI shutdown."""
    global _shared_client, _shared_loop
    client = _shared_client
    _shared_client = None
    _shared_loop = None
    if client is not None and not client.is_closed:
        await client.aclose()


def get_shared_http_client() -> Optional[httpx.AsyncClient]:
    """Returns the open shared AsyncClient only if bound to the active running event loop."""
    if _shared_client is None or _shared_client.is_closed:
        return None
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        return None
    if _shared_loop is not current_loop:
        return None
    return _shared_client


@asynccontextmanager
async def acquire_http_client(
    injected_client: Optional[httpx.AsyncClient] = None,
    timeout: float = 6.0,
    client_factory: Callable[..., httpx.AsyncClient] = httpx.AsyncClient,
) -> AsyncIterator[httpx.AsyncClient]:
    """
    Yields an open injected client, else the lifespan-managed pooled client,
    else a scoped ephemeral AsyncClient using the caller's httpx module reference.
    Never yields a closed client.
    """
    if injected_client is not None and not injected_client.is_closed:
        yield injected_client
        return

    shared = get_shared_http_client()
    if shared is not None:
        yield shared
        return

    async with client_factory(timeout=timeout) as ephemeral:
        yield ephemeral
