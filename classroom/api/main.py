"""FastAPI application entry point – classroom LMS."""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from config import get_settings

settings = get_settings()

# ── routers ────────────────────────────────────────────────────
from routers.auth import router as auth_router
from routers.classes import router as classes_router
from routers.class_files import router as class_files_router
from routers.assignments import router as assignments_router
from routers.sessions import router as sessions_router
from routers.submissions import router as submissions_router
from routers.progress import (
    router as progress_router,
    notif_router,
    admin_router,
)
from routers.lessons import router as lessons_router
from routers.quizzes import router as quizzes_router
from routers.my_files import router as my_files_router, shared_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create upload directories on startup
    for subdir in ("class", "user", "shared_tmp"):
        path = os.path.join(settings.upload_dir, subdir)
        os.makedirs(path, exist_ok=True)
    yield


limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="HeyStat Classroom API",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS ───────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── mount routers ─────────────────────────────────────────────
app.include_router(auth_router,         prefix="/api/v1")
app.include_router(classes_router,      prefix="/api/v1")
app.include_router(class_files_router,  prefix="/api/v1")
app.include_router(assignments_router,  prefix="/api/v1")
app.include_router(sessions_router,     prefix="/api/v1")
app.include_router(submissions_router,  prefix="/api/v1")
app.include_router(progress_router,     prefix="/api/v1")
app.include_router(notif_router,        prefix="/api/v1")
app.include_router(admin_router,        prefix="/api/v1")
app.include_router(lessons_router,      prefix="/api/v1")
app.include_router(quizzes_router,      prefix="/api/v1")
app.include_router(my_files_router,     prefix="/api/v1")
app.include_router(shared_router,       prefix="/api/v1")


@app.get("/api/v1/health")
async def health():
    return {"status": "ok", "service": "classroom-api"}
