from fastapi import FastAPI

from app.core.config import settings
from app.routers import auth

app = FastAPI(title="BIGA API", debug=settings.debug)

app.include_router(auth.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
