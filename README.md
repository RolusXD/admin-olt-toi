# TOI OLT Manager

Sistema OSS para administrar OLTs, ONUs, Zonas, NAPs/ODN, monitoreo GPON, aprovisionamiento y backups de configuracion para TOI Internet.

## Stack

- Backend: Python 3.12, FastAPI, SQLAlchemy 2.x, Alembic, Pydantic, Celery, Loguru.
- Frontend: NextJS, React, TypeScript, TailwindCSS y componentes UI locales estilo shadcn.
- Base de datos: PostgreSQL.
- Infraestructura: Docker Compose, Redis para tareas Celery.
- Autenticacion: JWT base para V1.

## Ejecutar

```bash
docker compose up --build
```

En otra terminal, aplicar migraciones:

```bash
docker compose exec backend alembic upgrade head
```

## Administrador inicial

El login no incluye credenciales predeterminadas. Genere localmente el usuario y hash del administrador:

```bash
docker compose exec backend python -m app.scripts.create_initial_admin --username admin
```

Copie `ADMIN_USERNAME` y `ADMIN_PASSWORD_HASH` a su archivo local `.env`, que no debe versionarse, y recree backend y worker. La contraseña sólo se solicita de forma interactiva y no se guarda en el repositorio.

La carga opcional de datos OLT de ejemplo requiere definir localmente `SEED_OLT_USERNAME` y `SEED_OLT_PASSWORD` antes de ejecutar `python -m app.seed`.

Servicios:

- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- Swagger: http://localhost:8000/docs
- Health: http://localhost:8000/health

## Arquitectura

- `backend/app/api`: rutas HTTP.
- `backend/app/models`: modelos SQLAlchemy.
- `backend/app/schemas`: contratos Pydantic.
- `backend/app/repositories`: persistencia aislada.
- `backend/app/services`: reglas de negocio.
- `backend/app/drivers`: drivers de equipos GPON.
- `backend/app/tasks`: Celery.
- `frontend/src/app`: aplicacion NextJS.
- `frontend/src/components`: dashboard, modulos y UI.
- `frontend/src/services`: cliente API.

## Driver V1

El driver `zte_c300_v125p3_telnet` implementa `DeviceDriver` con:

- `connect`
- `disconnect`
- `execute`
- `backup`
- `health_check`

Wrappers incluidos:

- `show card`
- `show gpon onu state`
- `show gpon onu detail-info`
- `show pon power onu-rx`
- `show pon power onu-tx`
- `show gpon onu uncfg`
- `show running-config`
- `show version`

## Operacion CLI

Endpoints nuevos:

- `POST /api/v1/olts/{olt_id}/telnet-test`: prueba Telnet, ejecuta `show version-running` con fallback a `show version`, ejecuta `show card` y devuelve datos estructurados.
- `POST /api/v1/olts/{olt_id}/sync-onus`: lee ONUs desde CLI, actualiza estado online/offline, guarda historico RX/TX y registra eventos `LOS`, `DyingGasp` y `Offline`.

El driver mantiene transportes separados para poder migrar desde `telnetlib` a `telnetlib3` o `pexpect` sin tocar servicios ni API. Los parsers ZTE estan en `backend/app/drivers/zte/c300_v125p3_telnet/parsers.py`.

## Limites deliberados de V1

No incluye CRM, facturacion, cobranza, contratos ni suspensiones por mora. La arquitectura deja preparado el crecimiento a VSOL, Huawei, EPON, XGSPON e integraciones ERP/Mikrowisp sin mezclarlas en esta version.
