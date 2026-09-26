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
