from fastapi import FastAPI

app = FastAPI(title="Verso API")


@app.get("/health")
def health():
    return {"status": "ok"}
