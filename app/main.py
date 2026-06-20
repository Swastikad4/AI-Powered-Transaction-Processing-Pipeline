"""
FastAPI application entry point.
Configures CORS, static files, router registration, and lifecycle hooks.
"""

from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.core.config import get_settings
from app.core.logging import setup_logging, get_logger
from app.core.database import engine, Base
from app.api.routes import router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    # Startup
    setup_logging()
    logger = get_logger("app.main")
    logger.info("starting_application", version=settings.APP_VERSION)

    # Create tables (use Alembic in production)
    Base.metadata.create_all(bind=engine)
    logger.info("database_tables_ready")

    # Ensure upload directory exists
    settings.upload_path
    logger.info("upload_directory_ready", path=str(settings.upload_path))

    print("\n" + "="*60)
    print(">>> Swagger UI (API Docs) available at: http://127.0.0.1:8000/docs")
    print("="*60 + "\n")

    yield

    # Shutdown
    logger.info("shutting_down_application")
    engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-powered transaction processing pipeline with Gemini AI enrichment",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(router)

# Static files (dashboard)
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/", include_in_schema=False)
async def serve_dashboard():
    """Serve the monitoring dashboard."""
    index_path = static_dir / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "AI Transaction Pipeline API", "docs": "/docs"}
