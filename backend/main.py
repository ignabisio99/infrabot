from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.contratistas import router as contratistas_router
from api.presupuestos import router as presupuestos_router
from api.reclamos import router as reclamos_router
from core.database import Base, engine
from models import contratista, presupuesto, reclamo  # noqa: F401 - registra los modelos antes de create_all


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(reclamos_router)
app.include_router(contratistas_router)
app.include_router(presupuestos_router)

@app.get("/")
def read_root():
    return {"status": "success", "message": "Backend is running"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}
