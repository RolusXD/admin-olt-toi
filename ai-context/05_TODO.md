# TODO

## Security And AI Handoff

- Configure `ADMIN_USERNAME` and `ADMIN_PASSWORD_HASH` through deployment secrets before enabling login in each environment.
- Rotate the placeholder JWT, crypto and database development values before a production deployment.
- ~~Add automated secret scanning to CI and pre-commit checks.~~
  - ✅ Gitleaks configurado en `security-scans` (CI) y documentado en README para ejecución local.
  - ⚠️ Pendiente evaluar integración en pre-commit hooks en una tarea posterior.
- Re-run tracked-file credential audits before every production handoff.

## Before More Production Provisioning

- Perform a human review of generated CLI for each new ONU model and service mode.
- Add explicit operator identity and immutable execution audit metadata.
- Define a documented recovery procedure for partially executed plans.
- Expand controlled execution tests for disconnects between command blocks.

## Import Quality

- Continue refining ambiguous NAP names without silently merging distinct names.
- Add review tooling for `SIN_ZONA`, partial descriptions and technician notes.
  - ✅ Parser de descripciones ZTE ajustado para no degradar zonas válidas (`zone_Lagunas`, variantes con espacios o guiones) y reducir falsos `SIN_ZONA`.
- Add a report for legacy incomplete metadata grouped by OLT and category.

## Operations

- Add retention policies for command logs, power history and raw snapshots.
- Review Celery schedules and concurrency before enabling unattended production polling.
- Add health and backup monitoring for PostgreSQL and Redis.

## UX and QA

- Complete visual browser regression checks for desktop and mobile operational pages.
- Add end-to-end tests for the five-step OLT import wizard using mocked read-only APIs.
- Review accessibility labels and keyboard navigation in dense tables and forms.
- [x] Endurecer confirmación de importación inicial para rechazar jobs en estados no válidos y mejorar el feedback de progreso en la etapa Preview.
  - ✅ UI de importación inicial ahora consume `GET /import/jobs/{job_id}` para mostrar estado real del job/snapshot, advertencias y conteos consolidados sin requerir WebSockets.
