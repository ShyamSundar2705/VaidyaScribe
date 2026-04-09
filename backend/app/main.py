from contextlib import asynccontextmanager
import asyncio
import structlog

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import create_tables

log = structlog.get_logger()


async def _init_graph_with_fallback():
    """
    Try to initialise LangGraph with AsyncRedisSaver (requires Redis).
    If Redis is unavailable, fall back to MemorySaver (zero dependencies).
    Returns the context manager for AsyncRedisSaver if used, else None.
    """
    from app.agents import graph as graph_module

    # Try Redis-backed checkpointer first
    try:
        from langgraph.checkpoint.redis import AsyncRedisSaver
        from app.agents.graph import _build_compiled_graph

        # Test Redis connection before committing
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=3)
        await r.ping()
        await r.aclose()

        # Redis is up — use AsyncRedisSaver with proper async with
        log.info("redis_available", url=settings.REDIS_URL)
        saver_cm = AsyncRedisSaver.from_conn_string(settings.REDIS_URL)
        saver = await saver_cm.__aenter__()
        graph_module._graph = _build_compiled_graph(saver)
        log.info("graph_initialised", checkpointer="AsyncRedisSaver")
        return saver_cm   # caller must __aexit__ this on shutdown

    except Exception as e:
        log.warning("redis_unavailable_using_memory", error=str(e))
        from langgraph.checkpoint.memory import MemorySaver
        from app.agents.graph import _build_compiled_graph
        graph_module._graph = _build_compiled_graph(MemorySaver())
        log.info("graph_initialised", checkpointer="MemorySaver")
        return None   # no cleanup needed


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()
    saver_cm = await _init_graph_with_fallback()
    yield
    # Cleanup Redis connection if it was opened
    if saver_cm is not None:
        try:
            await saver_cm.__aexit__(None, None, None)
        except Exception:
            pass


app = FastAPI(
    title="VaidyaScribe API",
    version="1.0.0",
    description="Multilingual AI clinical documentation — Tamil/English, DPDP-compliant",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api.router import api_router
from app.api.websocket import ws_router

app.include_router(api_router, prefix="/api/v1")
app.include_router(ws_router)


@app.get("/health")
async def health():
    from app.agents.graph import _graph
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": "1.0.0",
        "graph_ready": _graph is not None,
    }
