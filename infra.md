# Infraestructura y Deploy — InfraBot

Guía para desplegar el proyecto en una EC2 de AWS, con build automático en
GitHub Actions e imágenes en GHCR.

## Recursos AWS

- **EC2**: (Infrabot (UTN - NACHO) — `i-0a96b3614b361687d`)
- **Key Pair (SSH)**: para entrar vos a la EC2 la primera vez (el `.pem` de AWS). (Infrabot(Nacho))
- **Security Group (SG)**: reglas de entrada (sg-06e0a0da55e821a7f (Infrabot (UTN - NACHO))):
  - `22/tcp` (SSH) — idealmente solo desde tu IP.
  - `80/tcp` (HTTP) — abierto (Let's Encrypt + redirect a HTTPS).
  - `443/tcp` (HTTPS) — abierto.
- **EIP**: IP pública fija asociada a la instancia (estable para DNS y webhook). (77.112.180.116 (UTN - Infrabot - Nacho))
- **IAM ROLE**: (Infrabot-UTN-Nacho)

## Dominio

Todo bajo un solo dominio `infrabot.site`. El nginx de borde rutea por path:
- `infrabot.site/` → **frontend** (SPA React).
- `infrabot.site/auth`, `/reclamos`, `/uploads`, `/webhook`, etc. → **backend** (FastAPI).

Ventaja: un solo certificado, sin CORS entre orígenes (frontend y backend comparten
origen). Los prefijos de la API están listados en `deploy/nginx/infrabot.conf`.

### DNS (en el registrador de infrabot.site)

Crear registros A apuntando a la **EIP** de la EC2:

| Tipo | Nombre | Valor        |
|------|--------|--------------|
| A    | `@`    | `<EIP>`      |
| A    | `www`  | `<EIP>`      |

## Arquitectura del deploy

```
push a main
   │
   ▼
GitHub Actions ──build──► imágenes backend + frontend ──► GHCR
   │
   └── SSH a la EC2 ──► docker compose -f docker-compose.prod.yml pull && up -d
                          │
   EC2 ───────────────────┤
                          ├─ nginx_edge (80/443, HTTPS con certbot)
                          ├─ frontend (nginx sirviendo el SPA)
                          ├─ backend (FastAPI, 1 worker)
                          ├─ db (postgres, volumen persistente)
                          └─ redis
```

El build ocurre en el runner de GitHub. La EC2 **solo baja imágenes**, no buildea.

## Secrets y variables en GitHub

Repo → Settings → Secrets and variables → Actions.

**Secrets:**

| Nombre            | Valor                                                        |
|-------------------|--------------------------------------------------------------|
| `EC2_HOST`        | la EIP de la EC2                                             |
| `EC2_USER`        | `ubuntu` (Ubuntu) o `ec2-user` (Amazon Linux)               |
| `EC2_SSH_KEY`     | contenido de la clave privada `infrabot_deploy`             |
| `DEPLOY_DIR`      | ruta del repo en la EC2, ej. `/home/ubuntu/infrabot-utn`    |
| `GHCR_TOKEN`      | PAT con scope `read:packages` (para que la EC2 baje imágenes)|
| `GOOGLE_CLIENT_ID`| client id de Google (build del frontend)                    |

**Variables:**

| Nombre         | Valor                   |
|----------------|-------------------------|
| `VITE_API_URL` | `https://infrabot.site` |

## Operar la app en la EC2

Todos los comandos se corren **conectado por SSH como `ubuntu`** y **parado en el
directorio de deploy**:

```bash
ssh -i "tu-clave.pem" ubuntu@<EIP>
cd /home/ubuntu/infrabot-utn
```

Siempre hay que pasar `-f docker-compose.prod.yml` (no es el compose por defecto).

### Ver logs

```bash
# Todos los servicios juntos, en vivo
docker compose -f docker-compose.prod.yml logs -f

# Un servicio puntual
docker compose -f docker-compose.prod.yml logs -f backend

# Últimas N líneas
docker compose -f docker-compose.prod.yml logs --tail 100 nginx
```

### Estado de los contenedores

```bash
docker compose -f docker-compose.prod.yml ps
```

### Reiniciar / actualizar

```bash
# Reiniciar un servicio sin bajar el resto
docker compose -f docker-compose.prod.yml restart backend

# Bajar imágenes nuevas de GHCR y recrear (lo que hace el deploy automático)
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

### Base de datos (seed / reset)

```bash
docker compose -f docker-compose.prod.yml exec backend python seed.py --reset
```

### Parar todo

```bash
docker compose -f docker-compose.prod.yml down
```

## Consola de base de datos (Adminer) — solo lectura

Adminer queda publicado en `https://infrabot.site/adminer/` (lo pasa el nginx de borde,
no abre ningún puerto nuevo; el acceso va cifrado por el mismo certificado del dominio).

No hay ningún botón ni link a esta URL dentro de la app: es un path que solo se accede
sabiéndolo. Además está protegido por **dos candados independientes**:

1. **Auth básica de nginx** sobre `/adminer/`: usuario y contraseña propios del path,
   independientes de la base de datos. Sin eso ni siquiera carga la pantalla de Adminer.
2. **Usuario de Postgres de solo lectura**: una vez dentro de Adminer, se entra con un
   usuario que solo puede consultar, nunca con `POSTGRES_USER`.

### Candado 1 — contraseña del path (auth básica de nginx)

Se genera un archivo `.adminer_htpasswd` dentro de `deploy/nginx/` (ese directorio se
monta en el nginx como `/etc/nginx/conf.d`). El archivo NO se commitea (está en
`.gitignore`). En la EC2, parado en el directorio de deploy:

```bash
# Reemplazá 'admin' por el usuario que quieras; pedirá la contraseña de forma interactiva.
docker run --rm -it httpd:2.4-alpine htpasswd -nB admin >> deploy/nginx/.adminer_htpasswd
```

Eso agrega una línea `usuario:hash_bcrypt` al archivo. Para recargar nginx:

```bash
docker compose -f docker-compose.prod.yml exec nginx nginx -s reload
# o, si no toma el archivo nuevo:
docker compose -f docker-compose.prod.yml restart nginx
```

Al entrar a `https://infrabot.site/adminer/`, el navegador pedirá ese usuario/contraseña
ANTES de mostrar Adminer. Para cambiar la clave, borrá la línea del archivo y volvé a
generarla.

### Candado 2 — usuario de Postgres de solo lectura

**Regla de oro:** dentro de Adminer, entrar SIEMPRE con el usuario de **solo lectura**,
nunca con `POSTGRES_USER`. Así, aunque alguien pase el primer candado, no puede modificar
ni borrar datos.

### Crear el usuario de solo lectura (una sola vez)

Conectado por SSH y parado en el directorio de deploy:

```bash
docker compose -f docker-compose.prod.yml exec db \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
```

Dentro de `psql`, ejecutar (reemplazá `una_clave_segura` por una contraseña propia):

```sql
-- 1) El rol de solo lectura.
CREATE ROLE lector LOGIN PASSWORD 'una_clave_segura';

-- 2) Puede conectarse y "ver" el esquema público, pero no crear objetos.
GRANT CONNECT ON DATABASE infrabot TO lector;   -- usar el nombre real de POSTGRES_DB
GRANT USAGE ON SCHEMA public TO lector;

-- 3) SELECT sobre todas las tablas y vistas existentes.
GRANT SELECT ON ALL TABLES IN SCHEMA public TO lector;

-- 4) Que también aplique a las tablas que se creen en el futuro
--    (p. ej. tras un seed --reset o una migración).
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO lector;

\q
```

Si `POSTGRES_DB` no es `infrabot`, cambiá ese nombre en el `GRANT CONNECT`.

### Usar Adminer

1. Abrir `https://infrabot.site/adminer/`.
2. Completar:
   - **Motor**: PostgreSQL
   - **Servidor**: `db`
   - **Usuario**: `lector`
   - **Contraseña**: la que definiste arriba
   - **Base de datos**: el valor de `POSTGRES_DB` (ej. `infrabot`)

El usuario `lector` solo puede consultar: cualquier INSERT/UPDATE/DELETE/DROP falla con
error de permisos. Para tareas de escritura se sigue usando `psql` con el usuario principal.

> Nota de seguridad: Adminer queda accesible por internet. El usuario de solo lectura
> acota el riesgo, pero si querés un candado extra podés sumar autenticación básica de
> nginx sobre el `location /adminer/` o restringir por IP con `allow`/`deny`.
