from fastapi import FastAPI
from app.core.config import settings

app = FastAPI(title="BIGA API", debug=settings.debug)


@app.get("/health")
async def health():
    return {"status": "ok"}
