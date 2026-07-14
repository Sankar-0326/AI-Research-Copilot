from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from research_copilot.api.routes.papers import router as papers_router
from research_copilot.api.routes.analysis import router as analysis_router
from research_copilot.api.routes.auth import router as auth_router
from research_copilot.config import get_settings
from research_copilot.logging import setup_logging, get_logger
from research_copilot.db import dispose_engine

# ── LangSmith setup — must happen before any langchain import ─────────────
import os
from dotenv import load_dotenv
load_dotenv()   # loads .env into os.environ immediately

def setup_langsmith():
    """
    Explicitly set LangSmith env vars from settings into os.environ.
    LangChain reads these directly from os.environ — not from Pydantic settings.
    """
    settings = get_settings()

    if not settings.langsmith_api_key:
        return   # skip if no key provided

    os.environ["LANGSMITH_TRACING"]       = "true"
    os.environ["LANGSMITH_ENDPOINT"]      = settings.langsmith_endpoint or "https://api.smith.langchain.com"
    os.environ["LANGSMITH_API_KEY"]       = settings.langsmith_api_key
    os.environ["LANGSMITH_PROJECT"]       = settings.langsmith_project or "research-copilot"
    

    import structlog
    logger = structlog.get_logger("langsmith")
    logger.info(
        "langsmith_tracing_enabled",
        project=settings.langsmith_project,
        endpoint=settings.langsmith_endpoint,
    )

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

    setup_langsmith()
    
    logger.info("Starting AI Research Copilot", env=settings.app_env)

    # ── Pre-warm Pinecone only if a system key exists ─────────────────
    # In user-key-only mode this is skipped — each user's retriever
    # initializes lazily on their first request
    if settings.pinecone_api_key:
        from research_copilot.rag import get_retriever
        get_retriever()
        logger.info("pinecone_prewarm_complete")
    else:
        logger.info(
            "pinecone_prewarm_skipped",
            reason="no system key — user keys initialize on first request",
        )



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
        allow_credentials=True,    # ← required for cookies
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