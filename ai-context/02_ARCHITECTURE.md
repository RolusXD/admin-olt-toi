# Architecture

## Backend Layers

- `backend/app/api/routes`: HTTP transport and response mapping.
- `backend/app/services`: business workflows and transaction boundaries.
- `backend/app/repositories`: reusable persistence operations.
- `backend/app/models`: SQLAlchemy entities and relationships.
- `backend/app/schemas`: Pydantic request and response contracts.
- `backend/app/drivers`: device transport, command policy and parsing.
- `backend/app/tasks`: Celery monitoring tasks.

API routes must not contain CLI parsing or substantial business logic. Drivers must not own database workflows.

## ZTE Driver

The ZTE C300 driver lives in `backend/app/drivers/zte/c300_v125p3_telnet`. Transport is encapsulated so Telnet implementation changes do not affect services.

Dedicated parsers handle running config, cards, ONU states, unauthorized ONUs, interfaces, descriptions and ONU management modes.

## Frontend

- Next.js App Router under `frontend/src/app`.
- Shared shell and controls under `frontend/src/components`.
- Typed API client under `frontend/src/services/api.ts`.
- Shared contracts under `frontend/src/types/index.ts`.

Operational pages default to production and confirmed OLTs. Laboratory or incomplete records require explicit filters.

## Data Ownership

OLT-specific data must carry `olt_id`; imported records also preserve `olt_code_snapshot` where supported. Do not reuse zones, NAPs, VLANs, profiles, ONU types or ports across OLTs unless a future catalog is explicitly designed as shared.

## Deployment

Use `scripts/rebuild-containers.ps1`. It validates Compose, builds backend/worker/frontend, applies Alembic migrations and recreates services.

