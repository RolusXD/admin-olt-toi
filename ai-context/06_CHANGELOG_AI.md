# AI Changelog

## 2026-06-20 — Import Preview Job State

- Extendido el contrato `ImportJobRead` para incluir `snapshot_status`, `snapshot_warnings`, `parsed_summary`, `created_at` y `confirmed_at` a partir de `ImportJob` + `ConfigSnapshot` sin cambiar el parser ni la provisión.
- Actualizado `InitialImportService._job_to_dict` para serializar el estado del snapshot y aplanar las advertencias persistidas en `ConfigSnapshot.warnings` en una lista legible para UI.
- Añadido `ImportJob` al tipado frontend y un cliente `api.importJob(jobId)` que reutiliza `GET /import/jobs/{job_id}`.
- Ajustada la página `/importacion-inicial` para que, tras crear el preview, consulte el estado real del job/snapshot, muestre:
  - Estado del job
  - Estado del snapshot
  - Warnings reales (combinando validación, parser y `legacy_incomplete`)
  - Conteos reales de ONUs, VLANs, perfiles, PONs, uplinks, NAPs, zonas, warnings y errores críticos.
- Mantenidos los pasos visuales existentes del wizard y añadido un botón "Actualizar estado" que vuelve a llamar a `GET /import/jobs/{job_id}` sin WebSockets ni endpoints de eventos.
- Añadido un test de servicio que valida que `InitialImportService.get_job` devuelve un payload compatible con `ImportJobRead`, incluyendo `snapshot_status="parsed"` tras un preview exitoso.
- Ejecutado `pytest tests/test_initial_import_service.py` y `pytest` completos con `DATABASE_URL=sqlite+pysqlite:///:memory:`; 16/16 tests de importación inicial y 103/103 tests totales pasando tras ajustar la configuración de base de datos.

## 2026-06-20 — Configuración de base de datos amigable para tests

- Actualizado `backend/app/core/database.py` para resolver la URL de base de datos dando prioridad a la variable de entorno `DATABASE_URL` antes de usar el valor por defecto de `settings.database_url` (PostgreSQL).
- Con `DATABASE_URL=sqlite+pysqlite:///:memory:` ahora se inicializa un engine SQLite en memoria sin intentar importar el driver PostgreSQL `psycopg`, lo que permite ejecutar la suite de tests completa en entornos sin PostgreSQL instalado.
- Verificado que la compatibilidad con Docker/producción se mantiene al no definir `DATABASE_URL`, caso en el que se sigue utilizando la URL PostgreSQL por defecto.

## 2026-06-20

- Removed the hardcoded V1 `admin/Admin123!` login and replaced it with environment-backed username and `pbkdf2_sha256` password hash verification.
- Added an interactive initial-admin generator that prints environment values without persisting plaintext passwords.
- Removed hardcoded OLT credentials from the optional demo seed; seed credentials are now required through local environment variables.
- Removed demo login credentials from README and documented secure local administrator creation.
- Added five authentication/bootstrap tests; the complete local suite now passes 98 tests, Docker Compose configuration validates and the backend image builds successfully.
- Added root `AGENTS.md` with a mandatory context gate for Codex and API coding tools.
- Added `AI_HANDOFF.md` with resume instructions, safety rules, known state and recommended next task.
- Expanded repository ignore rules for secrets, OLT snapshots, Telnet exports and sensitive logs.
- Audited tracked files for API keys, private keys, tokens and real OLT credentials; none were found. Recorded the existing V1 demo login as an explicit security follow-up without changing authentication logic.
- Added persistent AI project context documentation under `/ai-context`.
- Refactored ZTE initial import to persist, checksum and validate a complete running-config snapshot before parsing.
- Added snapshot lifecycle states and structural ONU interface validation in migration `0033`.
- Added stable final-prompt confirmation and a 120-second running-config read timeout.
- Added complete/truncated snapshot tests and regression coverage for `zone_Lagunas`, NAP H5 and port 9.
- Added workflow `security-scans` con Gitleaks (CI push/pull_request) y documentación para ejecución local.
- Refined el parser de descripciones ZTE para aceptar zonas válidas con separadores `$`, espacios o guiones sin degradarlas a `SIN_ZONA`, manteniendo compatibilidad histórica.
- Añadidos tests parametrizados para `zone_Lagunas`, `zone Lagunas`, `zone-Lagunas` y variaciones con `_ descr`, asegurando que `zone_name` no arrastre tokens posteriores.
- `pytest tests/test_zte_onu_description_parser.py` pasó (6 tests).

## 2026-06-19

- Added the five-step `Agregar OLT e Importar` wizard.
- Scoped zones, NAPs and NAP ports by OLT in migration `0031`.
- Added OLT import lifecycle states and ONU technician notes in migration `0032`.
- Reduced fixture description warnings by separating technical warnings, inherited incomplete data and critical errors.
- Added `SIN_ZONA` per OLT and preserved original descriptions.
- Completed physical PON ports from GTGH/GTGHG card inventory.
- Added internal-only ONU observation editing.
- Marked incomplete OLT id 7 as cancelled and hid incomplete OLTs by default.
- Rebuilt backend, worker and frontend; local suite reached 90 passing tests.

## 2026-06-18

- Validated read-only monitoring and real ZTE command parsing.
- Added ONU discovery, environment separation, technical catalogs and import auditing.
- Implemented provisioning dry run, validation, preflight and controlled execution safeguards.
- Completed plan 19 management block and post-execution inventory reconciliation.
