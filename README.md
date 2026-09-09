# infrabot-utn

Sistema de gestión de reclamos de infraestructura escolar con bot de WhatsApp integrado.

## Stack

- **Backend:** FastAPI + SQLAlchemy + PostgreSQL
- **Frontend:** React 19 + Vite + Mantine UI + React Router
- **Autenticación:** JWT + Google OAuth 2.0 + confirmación por email (Gmail SMTP)
- **WhatsApp:** Meta Cloud API (webhooks + mensajes interactivos con botones)
- **Infraestructura:** Docker Compose

## Cómo levantar el proyecto

### Requisitos previos

- [Docker](https://docs.docker.com/get-docker/) y Docker Compose instalados
- Cuenta de [Meta for Developers](https://developers.facebook.com/) con WhatsApp configurado
- Cuenta de [Google Cloud](https://console.cloud.google.com/) con OAuth configurado
- Cuenta de Gmail con [contraseña de aplicación](https://myaccount.google.com/apppasswords)

### 1. Clonar el repositorio

```bash
git clone <url-del-repo>
cd infrabot-utn
```

### 2. Configurar variables de entorno

```bash
cp .env.example .env
```

Editá el `.env` con tus valores:

| Variable | Descripción |
|----------|-------------|
| `SMTP_EMAIL` | Email de Gmail para enviar confirmaciones |
| `SMTP_PASSWORD` | Contraseña de aplicación de Gmail |
| `GOOGLE_CLIENT_ID` | Client ID de Google OAuth (Web application) |
| `WHATSAPP_TOKEN` | Access token de Meta (WhatsApp → API Setup) |
| `WHATSAPP_PHONE_ID` | Phone Number ID de Meta (WhatsApp → API Setup) |
| `WHATSAPP_VERIFY_TOKEN` | String que elijas para verificar el webhook |
| `NGROK_AUTHTOKEN` | Auth token de ngrok |
| `NGROK_DOMAIN` | Dominio estático de ngrok |

Las demás variables vienen con valores por defecto para desarrollo local.

### 3. Levantar los servicios

```bash
docker compose up --build
```

Las siguientes veces (si no cambiaron dependencias):

```bash
docker compose up
```

### 4. Acceder

- **Frontend:** http://localhost:3000
- **Backend (API):** http://localhost:8000
- **Swagger UI:** http://localhost:8000/docs

## Configurar el bot de WhatsApp

El bot necesita que Meta pueda enviar mensajes a tu backend. El túnel ngrok ya está incluido en el `docker-compose.yml` — se levanta automáticamente con `docker compose up`.

La URL del webhook es fija (dominio estático de ngrok) y se configura en Meta una sola vez.

### 1. Configurar el webhook en Meta

1. Andá a https://developers.facebook.com/apps
2. Seleccioná la app **InfraBot**
3. En el menú lateral, hacé clic en **WhatsApp**
4. Andá al **Paso 2: Configurar webhooks**
5. Completá:
   - **URL de devolución de llamada:** `https://<NGROK_DOMAIN>/webhook/whatsapp` (el valor de `NGROK_DOMAIN` en tu `.env`)
   - **Token de verificación:** el mismo que pusiste en `WHATSAPP_VERIFY_TOKEN` en el `.env`
6. Hacé clic en **Verificar y guardar**
7. Suscribí el campo **messages** en Webhook fields

Esto se hace una sola vez. Mientras los servicios estén corriendo con `docker compose up`, el webhook funciona.

### 2. Probar

Mandá un mensaje de WhatsApp al número de prueba. El bot responde con un menú de botones interactivos.

**Comandos disponibles:**

| Comando | Descripción |
|---------|-------------|
| `nuevo` | Crear un reclamo paso a paso |
| `ver #<id>` | Ver detalle de un reclamo |
| `buscar <escuela>` | Buscar reclamos por escuela |
| `recientes` | Ver los últimos 5 reclamos |
| `cancelar` | Cancelar operación en curso |
| `ayuda` | Mostrar menú de botones |

## Datos de ejemplo

La base de datos arranca vacía. Para cargar datos de prueba:

```bash
docker compose exec backend python seed.py
```

Para dejar el entorno limpio y recargar todo:

```bash
docker compose exec backend python seed.py --reset
```

`--reset` **recrea las tablas** a partir de los modelos, así que también es la forma de
poner al día una base que quedó desfasada después de un `git pull` que cambió un modelo
(`create_all` crea las tablas que faltan, pero nunca altera las que ya existen: sin esto
la base queda vieja en silencio hasta que una consulta falla con `UndefinedColumn`).

El seed deja un usuario administrador listo para entrar:

| Email | Contraseña |
|-------|-----------|
| `admin@infrabot.dev` | `Admin123!` |

Hace falta porque registrarse desde la UI no alcanza en una base nueva: la cuenta queda
sin confirmar (el mail de confirmación necesita `SMTP_EMAIL`/`SMTP_PASSWORD` en el `.env`)
y esperando la aprobación de un admin que todavía no existe. Si querés otras credenciales,
se cambian en las constantes `ADMIN_EMAIL` / `ADMIN_PASSWORD` de `backend/seed.py`.

> Si además cambió el `requirements.txt` o el `Dockerfile`, hay que reconstruir la imagen
> antes: `docker compose build backend && docker compose up -d`.

## Tests

El backend tiene tests de las agregaciones del dashboard:

```bash
docker compose exec backend python -m pytest
```

Corren contra una base aparte (`infrabot_test`) que se crea sola la primera vez, así que
no tocan los datos de desarrollo.

Para correr un archivo o un test puntual:

```bash
docker compose exec backend python -m pytest tests/test_dashboard.py
docker compose exec backend python -m pytest -k estancados
```

## Comandos útiles

```bash
# Ver logs de un servicio
docker compose logs -f backend

# Reiniciar un servicio (sin reconstruir)
docker compose restart backend

# Parar todo
docker compose down

# Reconstruir (necesario al cambiar dependencias)
docker compose up --build

# Borrar usuarios de la base de datos
docker compose exec db psql -U user -d infrabot -c "DELETE FROM usuario;"
```

## Notas

- La URL de ngrok es fija (dominio estático). Solo necesitás tener ngrok corriendo para recibir mensajes.
- Para números argentinos, la API de Meta requiere el formato sin el 9 (ej: `541125654565`). El bot hace esta conversión automáticamente.

## Enlaces útiles

- [FastAPI](https://fastapi.tiangolo.com/)
- [SQLAlchemy](https://docs.sqlalchemy.org/)
- [React](https://react.dev/)
- [Mantine](https://mantine.dev/)
- [Tabler Icons](https://tabler.io/icons)
- [Meta WhatsApp Cloud API](https://developers.facebook.com/docs/whatsapp/cloud-api)
- [Google OAuth](https://developers.google.com/identity/gsi/web/guides/overview)
- [ngrok](https://ngrok.com/docs)
