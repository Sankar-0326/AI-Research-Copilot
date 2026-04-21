from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from research_copilot.api.routes.papers import router as papers_router
from research_copilot.api.routes.analysis import router as analysis_router
from research_copilot.api.routes.auth import router as auth_router
from research_copilot.config import get_settings
from research_copilot.logging import setup_logging, get_logger
from research_copilot.db import dispose_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup / shutdown lifecycle.
    Pre-warms the retriever connection on startup so the
    first request doesn't pay the Pinecone init cost.
    """
    setup_logging()                         
    logger = get_logger("startup")
    settings = get_settings()
    
    logger.info("Starting AI Research Copilot", env=settings.app_env)

    # Pre-warm connections
    from research_copilot.rag import get_retriever
    get_retriever()
    logger.info("Pinecone connection ready")


    yield

    await dispose_engine()      # ← clean DB shutdown
    logger.info("Shutting down")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="AI Research Copilot",
        description="Multi-agent system for research paper analysis",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ── CORS ──────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.app_env == "development" else [],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ───────────────────────────────────────────────────────
    app.include_router(papers_router)
    app.include_router(analysis_router)
    app.include_router(auth_router)

    # ── Health check ──────────────────────────────────────────────────
    @app.get("/health", tags=["System"])
    async def health():
        return {"status": "ok", "env": settings.app_env}

    return app


app = create_app()