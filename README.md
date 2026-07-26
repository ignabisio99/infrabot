# infrabot-utn

## Primeros Pasos

Para ejecutar este proyecto localmente:

1. Clona el repositorio.
2. Crea un archivo `.env` tomando como base el `.env.example`.
3. Ejecutá con Docker Compose:
   ```bash
   docker compose up
   ```

Una vez levantado, los servicios quedan disponibles en:

- Frontend: http://localhost:3000
- Backend (API): http://localhost:8000
- Documentación interactiva de la API (Swagger UI): http://localhost:8000/docs

## Datos de ejemplo

La BD arranca vacía. Para cargar datos de prueba (contratistas, reclamos y presupuestos):

```bash
docker compose exec backend python seed.py
```

Si ya hay datos cargados, el script no hace nada. Para borrar todo y recargar:

```bash
docker compose exec backend python seed.py --reset
```

## Stack

- Backend: FastAPI + SQLAlchemy (ORM) + Postgres.
- Frontend: React 19 + Vite + Mantine + React Router.

## Enlaces útiles

- [FastAPI - Documentación](https://fastapi.tiangolo.com/)
- [SQLAlchemy - Documentación](https://docs.sqlalchemy.org/)
- [React - Documentación](https://react.dev/)
- [Mantine - Documentación de componentes](https://mantine.dev/)
- [Tabler Icons (React)](https://tabler.io/icons)
