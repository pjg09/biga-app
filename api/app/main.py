from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import agendatorio, auth, pae, students

app = FastAPI(title="BIGA API", debug=settings.debug)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(agendatorio.router)
app.include_router(students.router)
app.include_router(pae.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
