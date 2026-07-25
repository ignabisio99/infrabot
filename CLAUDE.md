# infrabot-utn

## Entorno de desarrollo: Docker

Este proyecto corre con Docker Compose (`docker-compose.yml`), no directamente en el host. Los servicios son `db` (Postgres), `backend` (FastAPI) y `frontend` (Vite/React), cada uno con bind mount de su carpeta.

El frontend usa **pnpm** (no npm/yarn — ver `frontend/Dockerfile`, que instala pnpm vía corepack). No sugerir ni correr `npm install`, `pip install`, `npm run dev`, `uvicorn ...`, etc. directamente en el host. Siempre a través de los contenedores, por ejemplo:

```sh
docker compose up -d
docker compose exec frontend pnpm install <paquete>
docker compose exec frontend pnpm run <script>
docker compose exec backend pip install <paquete>
docker compose logs -f backend
```

Como los volúmenes montan `./backend` y `./frontend`, instalar un paquete dentro del contenedor actualiza `package.json`/`pnpm-lock.yaml`/`requirements.txt` en el host también.

## Git

Nunca hacer `git commit` ni `git push`. Cuando se pida ayuda con un mensaje de commit, dar el comando completo listo para copiar y pegar (ej. `git commit -m "..."`), no solo el mensaje — el usuario lo ejecuta (y el push) por su cuenta.

## Stack

- Backend: FastAPI + SQLAlchemy (ORM) + Postgres.
- Frontend: React 19 + Vite + Mantine (`@mantine/core`, `@mantine/dates`, `@mantine/form`) + `@tabler/icons-react` + React Router.
