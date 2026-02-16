import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from config import EMBEDDINGS_DIR, AUDIO_CACHE_DIR
from routers.audio import router as audio_router

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


@asynccontextmanager
async def lifespan(app: FastAPI):
    EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)
    AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="Verso API", lifespan=lifespan)
app.include_router(audio_router)


@app.get("/health")
def health():
    return {"status": "ok"}


# Serve frontend static files (built React app)
if os.path.exists(STATIC_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(STATIC_DIR, "assets")), name="assets")

    @app.get("/{full_path:path}")
    def serve_frontend(full_path: str):
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))
