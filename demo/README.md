# Demo independiente (servidor propio + Tailscale Funnel)

Despliegue aparte de la EC2, con una app de Meta propia y su número de prueba. No lo usa
el workflow de GitHub Actions: ese solo copia `docker-compose.prod.yml` y `deploy/`.

## Levantar

```sh
cd demo
cp .env.example .env   # completar
docker compose up -d --build
docker compose exec backend python seed.py
sudo tailscale funnel --bg --https=10000 http://127.0.0.1:8088
```

En el seed, los teléfonos de escuelas y contratistas que se usen en la demo tienen que
ser los celulares dados de alta en el número de prueba. Los demás, con prefijo `sim`.

## Meta

App → WhatsApp → Configuración:

- URL de callback: `https://<maquina>.<tailnet>.ts.net:10000/webhook/whatsapp`
- Token de verificación: el `WHATSAPP_VERIFY_TOKEN` del `.env`
- Suscribir el campo `messages`

Si Meta rechaza el puerto 10000, pasar Infrabot al 443 de Funnel y actualizar `APP_URL` y
la URL de callback.

## Operar

```sh
docker compose logs -f backend
docker compose ps
docker compose down
```

Para mudarlo a otro servidor: los mismos archivos y el mismo `.env` (cambia `APP_URL`), y
en Meta solo la URL de callback.
