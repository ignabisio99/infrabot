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

Hacer `git commit` solo cuando el usuario lo pida explícitamente. Si solo pide ayuda con un mensaje de commit, dar el comando completo listo para copiar y pegar (ej. `git commit -m "..."`), no solo el mensaje. Nunca hacer `git push`: el push lo hace el usuario.

El pre-commit (`frontend/.husky/pre-commit`) corre lint-staged (`eslint --fix` y `prettier --write`) sobre los `.js`/`.jsx` en stage y después los tests del frontend relacionados, en el contenedor. Un error de eslint que `--fix` no resuelve (ej. `react-hooks/set-state-in-effect`) frena el commit aunque sea de código que ya estaba en el archivo, así que conviene revisarlo antes:

```sh
docker compose exec frontend pnpm exec eslint <archivos>
```

## Tests

```sh
docker compose exec backend python -m pytest
```

Correrlos ante cualquier cambio en `backend/api/dashboard.py` o `backend/schemas/dashboard.py`:
los tests de `backend/tests/test_dashboard.py` cubren las agregaciones (cortes por mes en
hora local, umbral de estancados, monto aprobado, ventanas de fechas) y ahí un error no se
nota mirando la pantalla — devuelve un número plausible pero equivocado.

Si el cambio altera el contrato de la respuesta (agregar, renombrar o sacar un campo de los
schemas), actualizar los tests en el mismo cambio.

Los tests necesitan Postgres: usan `date_trunc` y `timezone(...)`, así que corren contra la
base `infrabot_test` (se crea sola) y no contra SQLite.

### Frontend

```sh
docker compose exec frontend pnpm test
```

Vitest + Testing Library (jsdom). Los tests van al lado del archivo que prueban
(`*.test.jsx`, o `*.test.js` si no hay JSX) y renderizan con `render` de
`src/test/render.jsx`, que envuelve en `MantineProvider`.
Correrlos ante cambios en `src/components/ChangeStateModal.jsx` o en los modales de
reclamos/presupuestos que lo usan: el modal es compartido y un cambio pensado para una
entidad puede romper la otra.

## Stack

- Backend: FastAPI + SQLAlchemy (ORM) + Postgres.
- Frontend: React 19 + Vite + Mantine (`@mantine/core`, `@mantine/dates`, `@mantine/form`) + `@tabler/icons-react` + React Router.
