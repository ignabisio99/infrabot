# infrabot-utn

Sistema de gestión de reclamos de infraestructura escolar.

## Stack

- **Backend:** FastAPI + SQLAlchemy + PostgreSQL
- **Frontend:** React 19 + Vite + Mantine UI + React Router
- **Autenticación:** JWT + Google OAuth 2.0 + confirmación por email (Gmail SMTP)
- **Infraestructura:** Docker Compose

## Cómo levantar el proyecto

### Requisitos previos

- [Docker](https://docs.docker.com/get-docker/) y Docker Compose instalados

### 1. Clonar el repositorio

```bash
git clone <url-del-repo>
cd infrabot-utn
```

### 2. Configurar variables de entorno

Copiá el archivo de ejemplo y completá con tus valores:

```bash
cp .env.example .env
```

Editá el `.env` y configurá:

| Variable | Descripción |
|----------|-------------|
| `SMTP_EMAIL` | Email de Gmail para enviar confirmaciones |
| `SMTP_PASSWORD` | Contraseña de aplicación de Gmail ([cómo generarla](https://myaccount.google.com/apppasswords)) |
| `GOOGLE_CLIENT_ID` | Client ID de Google OAuth ([consola de Google Cloud](https://console.cloud.google.com/apis/credentials)) |

Las demás variables vienen con valores por defecto que funcionan para desarrollo local.

### 3. Levantar los servicios

```bash
docker compose up --build
```

La primera vez tarda unos minutos porque descarga imágenes y construye los contenedores. Las siguientes veces:

```bash
docker compose up
```

### 4. Acceder

- **Frontend:** http://localhost:3000
- **Backend (API):** http://localhost:8000
- **Swagger UI:** http://localhost:8000/docs

## Datos de ejemplo

La base de datos arranca vacía. Para cargar datos de prueba:

```bash
docker compose exec backend python seed.py
```

Para borrar todo y recargar:

```bash
docker compose exec backend python seed.py --reset
```

## Comandos útiles

```bash
# Ver logs de un servicio específico
docker compose logs -f backend

# Reiniciar un servicio (sin reconstruir)
docker compose restart backend

# Parar todo
docker compose down

# Reconstruir (necesario al cambiar dependencias)
docker compose up --build
```

## Enlaces útiles

- [FastAPI](https://fastapi.tiangolo.com/)
- [SQLAlchemy](https://docs.sqlalchemy.org/)
- [React](https://react.dev/)
- [Mantine](https://mantine.dev/)
- [Tabler Icons](https://tabler.io/icons)
- [Google OAuth - Guía](https://developers.google.com/identity/gsi/web/guides/overview)
