import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from api.auth import router as auth_router
from api.contratistas import router as contratistas_router
from api.presupuestos import router as presupuestos_router
from api.reclamos import router as reclamos_router
from api.whatsapp import router as whatsapp_router
from core.database import Base, engine
from core.storage import UPLOADS_DIR
from models import contratista, foto_reclamo, presupuesto, reclamo, usuario  # noqa: F401 - registra los modelos antes de create_all

# Zona horaria UTC-3 (Argentina)
ART = timezone(timedelta(hours=-3))


class ARTFormatter(logging.Formatter):
    """Formatter que usa UTC-3 para los timestamps."""
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=ART)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime("%Y-%m-%d %H:%M:%S")


# Configurar logging con timestamp en UTC-3
fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
datefmt = "%Y-%m-%d %H:%M:%S"

formatter = ARTFormatter(fmt, datefmt=datefmt)
logging.basicConfig(level=logging.INFO, format=fmt, datefmt=datefmt)
logging.root.handlers[0].setFormatter(formatter)

# Configurar uvicorn loggers para que usen el mismo formato
for logger_name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
    uv_logger = logging.getLogger(logger_name)
    uv_logger.handlers = []
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    uv_logger.addHandler(handler)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR, check_dir=False), name="uploads")

app.include_router(auth_router)
app.include_router(reclamos_router)
app.include_router(contratistas_router)
app.include_router(presupuestos_router)
app.include_router(whatsapp_router)

@app.get("/")
def read_root():
    return {"status": "success", "message": "Backend is running"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/privacy", response_class=HTMLResponse)
def privacy_policy():
    return """
    <!DOCTYPE html>
    <html lang="es">
    <head><meta charset="UTF-8"><title>Política de Privacidad - InfraBot</title></head>
    <body style="font-family: Arial, sans-serif; max-width: 700px; margin: 40px auto; padding: 20px;">
        <h1>Política de Privacidad</h1>
        <p><strong>Última actualización:</strong> Agosto 2026</p>
        <h2>1. Información que recopilamos</h2>
        <p>InfraBot recopila la siguiente información cuando usás nuestro servicio:</p>
        <ul>
            <li>Nombre y dirección de correo electrónico (al registrarte)</li>
            <li>Número de teléfono (al completar tu perfil)</li>
            <li>Mensajes enviados a través de WhatsApp para gestionar reclamos</li>
        </ul>
        <h2>2. Uso de la información</h2>
        <p>Utilizamos tu información exclusivamente para:</p>
        <ul>
            <li>Gestionar reclamos de infraestructura escolar</li>
            <li>Comunicarnos contigo sobre el estado de tus reclamos</li>
            <li>Autenticar tu identidad en la plataforma</li>
        </ul>
        <h2>3. Compartir información</h2>
        <p>No compartimos tu información personal con terceros, excepto cuando sea necesario para el funcionamiento del servicio (ej: Meta/WhatsApp para la comunicación).</p>
        <h2>4. Seguridad</h2>
        <p>Protegemos tu información mediante cifrado y prácticas de seguridad estándar de la industria.</p>
        <h2>5. Contacto</h2>
        <p>Para consultas sobre privacidad, contactanos a través de la plataforma.</p>
    </body>
    </html>
    """
