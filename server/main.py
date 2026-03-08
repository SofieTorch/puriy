from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from database.connection import engine
from routes import lines_router, recordings_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup: verify database connection
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    yield
    # Shutdown: cleanup if needed


app = FastAPI(
    title="Open Transit API",
    description="API for managing transit lines with geographic data",
    version="0.1.0",
    lifespan=lifespan
)

# CORS: allow any origin (mobile apps, WebViews, web clients).
# Native mobile apps don't enforce CORS; this mainly affects browsers and in-app WebViews.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # must be False when allow_origins is ["*"]
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(lines_router)
app.include_router(recordings_router)


@app.get("/")
def root():
    """Health check endpoint."""
    return {"status": "healthy", "service": "open-transit"}


@app.get("/health")
def health_check():
    """Detailed health check."""
    return {
        "status": "healthy",
        "database": "connected"
    }
