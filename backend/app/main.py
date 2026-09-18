import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import init_db
from app.api import auth, spaces, projects, materials, tutor, learning, analytics, admin, demo

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("aiprof")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting AI.Prof backend service...")
    init_db()
    yield
    logger.info("Shutting down AI.Prof backend service...")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="AI.Prof — AI-Powered Learning & Growth Companion API",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Open in dev/demo; restrict in strict production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers under /api
app.include_router(auth.router, prefix="/api")
app.include_router(spaces.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
app.include_router(materials.router, prefix="/api")
app.include_router(tutor.router, prefix="/api")
app.include_router(learning.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(demo.router, prefix="/api")

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "service": "AI.Prof Backend",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
    }
