# infrabot-utn

Sistema de gestión de reclamos de infraestructura escolar con bot de WhatsApp integrado.

## Stack

- **Backend:** FastAPI + SQLAlchemy + PostgreSQL
- **Frontend:** React 19 + Vite + Mantine UI + React Router
- **Autenticación:** cookies HttpOnly con JWT + Google OAuth 2.0 + confirmación por email (Gmail SMTP)
- **WhatsApp:** Meta Cloud API (webhooks + mensajes interactivos con botones)
- **IA:** LangGraph + proveedor configurable (mock / OpenAI / Gemini)
- **Colas y workers:** Redis (cola de mensajes de WhatsApp) + tareas en background
- **Infraestructura:** Docker Compose (Postgres, Redis, backend, frontend, Adminer)

## Funcionalidades principales

- **Reclamos por WhatsApp:** carga guiada paso a paso, con fotos, videos y notas de voz. El bot valida la escuela contra el padrón oficial.
- **Motor de IA:** clasifica el reclamo (categoría y prioridad), detecta duplicados, estima el costo con referencias históricas ajustadas por inflación y audita presupuestos. Asiste, no decide.
- **Gestión de presupuestos:** los administradores convocan contratistas (individualmente o por listas) que reciben la solicitud por WhatsApp y email, y cargan su presupuesto desde un portal propio.
- **Coordinación de visitas:** al aprobar un presupuesto, el bot coordina la fecha de la visita entre contratista y escuela, y envía recordatorios el día antes y el mismo día.
- **Ciclo de estados con trazabilidad:** cada reclamo tiene un historial completo de estados (creado → presupuestado → en evaluación → aprobado → coordinación → visita → ejecución → finalizado).
- **Dashboard:** KPIs, gráficos y reclamos estancados.
- **Roles diferenciados:** administradores (gestión completa) y contratistas (portal acotado a sus solicitudes y presupuestos).

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
| `AI_PROVIDER` | Motor de IA: `mock` (por defecto, sin costo), `openai` o Gemini |
| `OPENAI_API_KEY` | API key de OpenAI o de Gemini (según el proveedor) |
| `OPENAI_MODEL` | Modelo a usar (ej: `gpt-4o-mini`, `gemini-3.5-flash-lite`) |
| `AI_BASE_URL` | URL base del proveedor (OpenAI o el endpoint compatible de Gemini) |

Las demás variables vienen con valores por defecto para desarrollo local. La IA arranca
en modo `mock` (heurísticas deterministas, sin llamadas ni costo), así que el sistema
funciona sin configurar ninguna API key.

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
- **Adminer (visor de la base):** http://localhost:8082 (servidor `db`, usuario y contraseña del `.env`)

## Configurar el bot de WhatsApp

El bot necesita que Meta pueda enviar mensajes a tu backend. El webhook se configura en
Meta apuntando al entorno **de producción** (dominio con HTTPS), una sola vez.

### 1. Configurar el webhook en Meta

1. Andá a https://developers.facebook.com/apps
2. Seleccioná la app **InfraBot**
3. En el menú lateral, hacé clic en **WhatsApp**
4. Andá al **Paso 2: Configurar webhooks**
5. Completá:
   - **URL de devolución de llamada:** `https://infrabot.site/webhook/whatsapp`
   - **Token de verificación:** el mismo que pusiste en `WHATSAPP_VERIFY_TOKEN` en el `.env`
6. Hacé clic en **Verificar y guardar**
7. Suscribí el campo **messages** en Webhook fields

### 2. Probar en producción

Mandá un mensaje de WhatsApp al número de prueba. El bot responde con un menú de botones interactivos.

### Probar el bot en local (sin Meta)

En local no hace falta túnel ni webhook: usá el **Simulador de WhatsApp** de la app
(`/whatsapp/simular`), que conversa con el mismo bot en tu máquina sin pasar por Meta ni Redis.

**Comandos disponibles:**

| Comando | Descripción |
|---------|-------------|
| `nuevo` | Crear un reclamo paso a paso |
| `ver #<id>` | Ver detalle de un reclamo |
| `buscar <escuela>` | Buscar reclamos por escuela |
| `recientes` | Ver los últimos 5 reclamos |
| `cancelar` | Cancelar operación en curso |
| `ayuda` | Mostrar menú de botones |

## Motor de IA

El sistema usa un motor de IA con proveedor intercambiable. Arranca en modo **`mock`**:
devuelve resultados heurísticos deterministas, sin llamar a ninguna API ni generar costo.
El sistema es 100% funcional en este modo, ideal para desarrollo y demos sin credenciales.

### Qué hace la IA

Al crear un reclamo, un pipeline (LangGraph) lo procesa en tres pasos: **clasificación**
(categoría + prioridad), **detección de duplicados** y **estimación de costo** (con
referencias históricas ajustadas por inflación del IPC de INDEC). Además audita los
presupuestos que cargan los contratistas, transcribe notas de voz, analiza fotos y
sugiere contratistas. Todas las decisiones quedan registradas en la tabla `recomendacion_ia`.

> La IA **asiste**: nunca inventa un precio ni toma la decisión final. Genera información
> de referencia para que el responsable compare y decida.

### Activar IA real (opcional)

Para usar un modelo real en vez del mock, configurá en el `.env`:

**Opción A — Google Gemini (tiene tier gratuito):**

```
AI_PROVIDER=openai
OPENAI_API_KEY=tu_api_key_de_gemini
OPENAI_MODEL=gemini-3.5-flash-lite
AI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
```

La API key se obtiene en [aistudio.google.com](https://aistudio.google.com) → "Get API key".
Gemini expone un endpoint compatible con OpenAI, por eso `AI_PROVIDER=openai`. El tier
gratuito tiene límites por cantidad de requests (no cobra dinero); ver
[rate limits](https://ai.google.dev/gemini-api/docs/rate-limits).

**Opción B — OpenAI (de pago por uso):**

```
AI_PROVIDER=openai
OPENAI_API_KEY=sk-tu_clave
OPENAI_MODEL=gpt-4o-mini
AI_BASE_URL=https://api.openai.com/v1
```

La API key se obtiene en [platform.openai.com](https://platform.openai.com) → API Keys.

Después de cambiar el `.env`, reiniciá el backend: `docker compose up -d backend`.

## Padrón de escuelas

El sistema valida las escuelas contra un padrón oficial (CSV en `backend/data/instituciones.csv`).
**Se carga automáticamente al arrancar el backend** si la tabla está vacía — no hay que
correr nada a mano. Tras un `seed.py --reset`, se vuelve a cargar sola en el próximo arranque.

Para forzar una recarga o cargar un CSV actualizado (con más escuelas), existe un script.
Matchea por identificador, así actualiza sin duplicar:

```bash
docker compose exec backend python scripts/importar_instituciones.py
```

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

- El webhook de WhatsApp apunta a producción (`https://infrabot.site`). En local se usa el simulador.
- Para números argentinos, la API de Meta requiere el formato sin el 9 (ej: `541125654565`). El bot hace esta conversión automáticamente.
- **Redis** procesa los mensajes de WhatsApp de forma asíncrona (el webhook responde rápido y un worker procesa en background). Si Redis no está disponible, el sistema degrada de forma elegante y procesa los mensajes de forma inline, sin perderlos.
- El backend levanta **tareas en background** al arrancar: cola de WhatsApp, recordatorios de visitas y seguimiento a contratistas. No dependen de cron externo, funcionan igual en local y deployado.
- La IA está en modo `mock` por defecto. Con ese modo no se llama a ninguna API ni se genera costo, y todas las features funcionan con resultados heurísticos.

## Enlaces útiles

- [FastAPI](https://fastapi.tiangolo.com/)
- [SQLAlchemy](https://docs.sqlalchemy.org/)
- [React](https://react.dev/)
- [Mantine](https://mantine.dev/)
- [Tabler Icons](https://tabler.io/icons)
- [Meta WhatsApp Cloud API](https://developers.facebook.com/docs/whatsapp/cloud-api)
- [Google OAuth](https://developers.google.com/identity/gsi/web/guides/overview)
- [LangGraph](https://langchain-ai.github.io/langgraph/)
- [Gemini API](https://ai.google.dev/gemini-api/docs)
- [OpenAI API](https://platform.openai.com/docs)
