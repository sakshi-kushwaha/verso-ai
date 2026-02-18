import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from config import EMBEDDINGS_DIR, AUDIO_CACHE_DIR
from database import init_db
from routers.audio import router as audio_router
from routers.onboarding import router as onboarding_router
from routers.upload import router as upload_router
from routers.feed import router as feed_router
from routers.flashcards import router as flashcards_router
from routers.chat import router as chat_router
from routers.auth import router as auth_router
import pipeline

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


@asynccontextmanager
async def lifespan(app: FastAPI):
    EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)
    AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    init_db()
    # Store the running event loop so background threads can schedule async broadcasts
    pipeline._event_loop = asyncio.get_running_loop()
    yield


app = FastAPI(title="Verso API", lifespan=lifespan)

# CORS — allow frontend dev server and production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global error handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": str(exc)},
    )


app.include_router(audio_router)
app.include_router(onboarding_router)
app.include_router(upload_router)
app.include_router(feed_router)
app.include_router(flashcards_router)
app.include_router(chat_router)
app.include_router(auth_router)


@app.get("/health")
def health():
    return {"status": "ok"}


# Serve frontend static files (built React app)
if os.path.exists(STATIC_DIR):
    bg_images_dir = os.path.join(STATIC_DIR, "bg-images")
    if os.path.exists(bg_images_dir):
        app.mount("/bg-images", StaticFiles(directory=bg_images_dir), name="bg-images")

    app.mount("/assets", StaticFiles(directory=os.path.join(STATIC_DIR, "assets")), name="assets")

    @app.get("/{full_path:path}")
    def serve_frontend(full_path: str):
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))
