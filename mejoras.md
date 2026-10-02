# Mejoras del proyecto — InfraBot UTN

Análisis integral del proyecto con puntos de mejora, ordenados por prioridad real
considerando el alcance (proyecto final universitario, no una app comercial a gran
escala). Para cada punto se indica evidencia, impacto y una recomendación honesta.

> Convención de severidad:
> - **Alta**: impacto funcional o de seguridad real; conviene resolver.
> - **Media**: mejora de calidad o riesgo acotado.
> - **Baja / opcional**: solo relevante a escala enterprise; aceptable dejarlo para un TP.

---

## Vale la pena arreglar (impacto real, esfuerzo bajo)

### 3. `SECRET_KEY` con default hardcodeado — Severidad: Media
`backend/core/auth.py` define `SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-cambiar-en-produccion")`.
Si en producción no se setea la env, los JWT quedan firmados con una clave pública
conocida (permitiría falsificar tokens).

- Estado actual: en prod ya está seteada en el `.env` de la EC2 y en el compose.
- **Fix**: agregar un chequeo al arranque que aborte si `SECRET_KEY` no está definida
  (o es el default) cuando el entorno es producción, para evitar el error silencioso.

### 4. Uso de `print()` en vez de logging — Severidad: Baja
Errores de envío de WhatsApp/email y transiciones inválidas se emiten con `print()`,
sin nivel ni contexto estructurado (a efectos prácticos se pierden en el contenedor).

- Archivos: `backend/core/whatsapp_client.py`, `backend/core/whatsapp_handler.py`,
  `backend/services/coordinacion_visita.py`, `backend/services/estados_presupuesto.py`.
- **Fix**: reemplazar `print(...)` por `logger.info/warning/error(...)`.

---

## Mejora de calidad recomendada (si hay tiempo)

### 5. Faltan tests de lo más complejo — Severidad: Media
Existen tests del dashboard, comentarios y roles (`backend/tests/`), con un `conftest.py`
bien armado (Postgres de test, rollback por test, factories). Pero **no hay tests** de:
- La capa de IA: `duplicados.py`, `clasificacion.py`, `estimacion.py`, `grafo.py`, `agente.py`.
- El handler de WhatsApp (`whatsapp_handler.py`), la máquina de estados más frágil.
- Auth (`core/auth.py`, `dependencies.py`).
- Endpoints críticos (`reclamos.py`, `presupuestos.py`, `ai.py`, webhook).

Ventaja: ya existe un `MockProvider` determinista y un simulador (`whatsapp_sim.py`) que
harían estos tests baratos. Mayor retorno: testear el flujo de creación de reclamo y
`duplicados.buscar_duplicados`.

### 6. Código duplicado (tokenización / Jaccard) — Severidad: Baja
`_tokens` y `_jaccard` están copiados idénticos en `backend/services/ai/duplicados.py`
y `backend/services/ai/historicos.py`; hay otra variante en `backend/services/instituciones.py`.
- **Fix**: unificar en un módulo común (ej. `services/ai/texto.py`).

### 7. `whatsapp_handler.py` demasiado grande — Severidad: Baja
~1268 líneas: máquina de estados por strings (`conv["paso"]`) con ~15 pasos y muchas
funciones `_procesar_*`, más una cadena larga de `if texto in (...)` en `procesar_mensaje`.
Funciona, pero cuesta seguir y testear.
- **Fix**: separar el flujo de creación (ej. `services/whatsapp/flujo_creacion.py`) del
  router de comandos. Hay varios imports locales para romper ciclos, señal de que las
  fronteras de módulos podrían limpiarse.

---

## Opcional / solo importa a escala (aceptable dejarlo para el TP)

### 8. Sin migraciones (Alembic) — Severidad: Baja para el alcance
El esquema se crea con `Base.metadata.create_all()` y los cambios de columnas se manejan
con helpers `ALTER` manuales e idempotentes en `backend/core/database.py`
(`asegurar_columna_tipo_item`, `asegurar_columna_detalle_tarea`, `asegurar_tipo_usuario_inspector`).
Funciona, pero cada cambio de esquema requiere escribir otro helper con SQL crudo.
- **Solución "correcta"**: Alembic. Para el alcance del TP, los helpers alcanzan; migrar
  ahora es mucho esfuerzo para poco beneficio.

### 9. Faltan índices en la BD — Severidad: Baja
`models/reclamo.py`: `telefono_creador` y `nombre_escuela` no tienen `index=True`, pese a
que se filtran seguido (`_listar_recientes`, `_buscar_por_escuela`, `buscar_duplicados`).
Con pocos registros el impacto es nulo; agregar `index=True` es trivial si se quiere.

### 10. Webhook de WhatsApp sin validación de firma — Severidad: Baja (TP) / Media-Alta (prod real)
`backend/api/whatsapp.py` procesa el POST sin verificar el header `X-Hub-Signature-256`.
Cualquiera que conozca la URL podría inyectar mensajes falsos. Para una demo es aceptable;
en producción real habría que validar la firma con el app secret de Meta.

### 11. Health check superficial — Severidad: Baja
`GET /health` devuelve `{"status":"healthy"}` fijo, sin chequear DB ni Redis, así que
puede reportar "healthy" con la base caída. Suficiente para el TP; mejorable con un
chequeo real de dependencias.

### 12. Sin módulo central de settings / validación de env — Severidad: Baja
Las variables se leen con `os.getenv` y defaults dispersos. No hay validación de que las
requeridas estén presentes al arrancar (`DATABASE_URL` explotaría en runtime si falta).
- **Solución opcional**: un módulo de settings (ej. `pydantic-settings`) que valide al inicio.

---

## Lo que ya está bien (para no tocar)

- Passwords con **bcrypt**; JWT con `jti` + **blacklist** para logout real.
- Cookies **HttpOnly + Secure + SameSite**, HTTPS con Let's Encrypt.
- **CORS** con allowlist explícita; el simulador de WhatsApp exige autenticación.
- **Cola Redis** con persistencia AOF para no perder mensajes; reintentos con backoff
  ante 503 de Gemini; fallbacks en cadena en la capa de IA (nunca rompe el flujo).
- `apiClient.js` centraliza auth (401 global), normaliza errores y evita duplicación CRUD.
- `conftest.py` de tests bien diseñado (base de test aislada, rollback por test).

---

## Prioridad sugerida

1. Autorización admin en endpoints de IA (#1).
2. Validar `SECRET_KEY` / env requeridas al arranque (#3, #12 parcial).
3. Documentar restricción de 1 worker o mover estado a Redis (#2).
4. `print()` → logging (#4).
5. (Si hay tiempo) Tests del handler de WhatsApp y de `duplicados` (#5); deduplicar
   Jaccard (#6).

Los puntos 8-11 se pueden dejar documentados como "mejoras futuras": es válido y prolijo
mostrar en la defensa que se identificaron y se decidió conscientemente no abordarlos por
el alcance del proyecto.

Agregados por mi: Pagina donde se vean todos los administradores del sistema para su manejo y auditoria