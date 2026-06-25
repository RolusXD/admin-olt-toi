# TOI OLT Manager - Project Context

## Purpose

TOI OLT Manager is an internal OSS application for multi-OLT inventory, ZTE C300 monitoring, initial configuration import, ONU discovery and controlled provisioning workflows.

## Current Scope

- Production and laboratory OLT separation.
- ZTE C300 V1.2.5P3 Telnet driver.
- Initial import from `show running-config` with preview and confirmation.
- Read-only monitoring of cards, PON ports, uplinks, ONU state and optical power.
- Unauthorized ONU discovery.
- Provisioning plans, validation, preflight and controlled execution.
15 | - Internal FTTH catalogs: VLANs, profiles, ONU types, zones, NAPs and NAP ports.
16 |   - La identidad canónica de NAP/ODN/ODB conserva siempre su prefijo (`NAP`, `ODN`, `ODB`); por ejemplo, `NAP D01` y `ODN D01` son entidades distintas que pueden coexistir en la misma OLT y no deben colapsarse bajo `D01`.

## Safety Baseline

Monitoring and import operations are read-only. Never execute configuration commands unless the user explicitly requests a controlled provisioning execution and the plan has passed every required state.

Forbidden implicit commands include `write`, `save`, `reboot`, `reload`, `reset`, `delete` and `erase`.

## Runtime

- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- API docs: http://localhost:8000/docs
- PostgreSQL and Redis run through Docker Compose.
- Current Alembic head: `0036_operational_governance`.

## AI Continuity

- Root instructions: `AGENTS.md`.
- Cross-tool handoff: `AI_HANDOFF.md`.
- Every coding tool must complete the mandatory context gate before changing code and update TODO/changelog after material work.
- No API keys, private keys, real OLT credentials or production Telnet exports were found in the tracked project audit on 2026-06-20.
- The V1 hardcoded demo login was removed. Authentication now requires `ADMIN_USERNAME` and a Passlib `pbkdf2_sha256` hash in `ADMIN_PASSWORD_HASH`.
- Login fails closed with HTTP 503 until the administrator environment variables are configured locally.

## Known Production Identity

- Real OLT: `OLT-PCM-ZTE-01`, database id `3`, environment `production`.
- Historical laboratory OLT: `OLT-LAB-ZTE-01`, environment `lab`.
- Incomplete test OLT `PCM-1`, id `7`, is `cancelled` and hidden from the operational list by default.
