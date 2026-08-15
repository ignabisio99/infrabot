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
| `WHATSAPP_VERIFY_TOKEN` | String que elijas para verificar el webhook (ej: `infrabot-verify-token`) |

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

El bot necesita que Meta pueda enviar mensajes a tu backend. Para desarrollo local, necesitás un túnel HTTPS.

### 1. Instalar Cloudflare Tunnel

```bash
curl -sSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o cloudflared
chmod +x cloudflared
sudo mv cloudflared /usr/local/bin/
```

### 2. Levantar el túnel

```bash
cloudflared tunnel --url http://localhost:8000
```

Te da una URL tipo `https://xxx-xxx-xxx.trycloudflare.com`. Esta URL cambia cada vez que levantás el túnel.

### 3. Configurar el webhook en Meta

1. Andá a https://developers.facebook.com/apps
2. Seleccioná la app **InfraBot**
3. En el menú lateral, hacé clic en **WhatsApp**
4. Andá al **Paso 2: Configurar webhooks**
5. Completá:
   - **URL de devolución de llamada:** `https://<tu-url-cloudflare>/webhook/whatsapp`
   - **Token de verificación:** el mismo que pusiste en `WHATSAPP_VERIFY_TOKEN` en el `.env`
6. Hacé clic en **Verificar y guardar**
7. Suscribí el campo **messages** en Webhook fields

### 4. Probar

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

Para borrar todo y recargar:

```bash
docker compose exec backend python seed.py --reset
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

- El access token de Meta (WHATSAPP_TOKEN) expira cada 24hs en modo desarrollo. Renovalo desde Meta → WhatsApp → API Setup.
- La URL de Cloudflare cambia cada vez que reiniciás el túnel. Actualizá el webhook en Meta cuando eso pase.
- Para números argentinos, la API de Meta requiere el formato sin el 9 (ej: `541131772043`). El bot hace esta conversión automáticamente.

## Enlaces útiles

- [FastAPI](https://fastapi.tiangolo.com/)
- [SQLAlchemy](https://docs.sqlalchemy.org/)
- [React](https://react.dev/)
- [Mantine](https://mantine.dev/)
- [Tabler Icons](https://tabler.io/icons)
- [Meta WhatsApp Cloud API](https://developers.facebook.com/docs/whatsapp/cloud-api)
- [Google OAuth](https://developers.google.com/identity/gsi/web/guides/overview)
- [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)
