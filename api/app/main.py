from fastapi import FastAPI

from app.core.config import settings
from app.routers import agendatorio, auth, students

app = FastAPI(title="BIGA API", debug=settings.debug)

app.include_router(auth.router)
app.include_router(agendatorio.router)
app.include_router(students.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
