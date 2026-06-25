# AI Handoff - TOI OLT Manager

## Project Summary

TOI OLT Manager is a FastAPI and Next.js application for multi-OLT inventory, ZTE C300 read-only monitoring, snapshot-based initial import, ONU discovery and controlled provisioning workflows.

## Resume With Codex

1. Open the repository root in Codex.
2. Ask Codex to read `AGENTS.md` and the mandatory files listed below before changing code.
3. State the exact scope and whether real OLT access is authorized. No authorization is assumed.
4. Ask for tests and frontend build verification appropriate to the change.
5. Require the AI context and changelog to be updated before handoff.

## Resume With an API Tool

Include `AGENTS.md` and the mandatory context files in the API request before the task specification. Give the tool repository access only, keep secrets in environment variables, and explicitly disable network or OLT access unless the current operation requires and authorizes it. Require a final response with changed files, tests, build result and unresolved risks.

## Read First

1. `ai-context/00_PROJECT_CONTEXT.md`
2. `ai-context/01_PROJECT_HISTORY.md`
3. `ai-context/03_IMPORTACION_OLT.md`
4. `ai-context/04_DEVELOPMENT_RULES.md`
5. `ai-context/05_TODO.md`
6. `ai-context/07_DECISIONS.md`
7. `ai-context/08_KNOWN_ISSUES.md`
8. `ai-context/09_ROADMAP.md`
9. `docs/EFO_MODELO_TERRITORIAL_FTTH.md`
10. `docs/EFO_GOBIERNO_DE_CATALOGOS.md`
11. `docs/EFO_ARQUITECTURA_OPERATIVA_ADMIN_OLT_TOI.md`
12. `docs/EFO_OBSERVABILIDAD_Y_CONOCIMIENTO_OPERATIVO.md`

Also read `ai-context/02_ARCHITECTURE.md` for architectural work and `ai-context/06_CHANGELOG_AI.md` for recent implementation history.

For territorial reconstruction (P4.x), the central in-memory orchestration lives in:

- `backend/app/services/territorial_reconstruction_engine.py` — **Territorial Reconstruction Engine (TRE)** infrastructure.
  - Provides reusable DTOs and contracts:
    - `TerritorialCandidate` (generic territorial candidate with `state` and `evidence_score`).
    - `TerritorialEvidence` (source/description/weight/metadata for confidence scoring).
    - `TerritorialCandidateState` (`NEW`, `EXISTS`, `REVIEW`, `BLOCKED`, `MERGE`).
    - `ConfidenceEvaluator`, `ConflictDetector`, `ReportGenerator` protocols.
    - `TerritorialReconstructionEngine` generic orchestrator for building candidates and reports.
  - Purely in-memory and **preview-only**: no DB writes, no endpoints, no Apply, no Telnet.
  - Designed to be reused by P4.2 (NAP/ODN/ODB), P4.3 (NapPorts) and P4.4 (ONU/ProvisioningPlan reassignment) without duplicating confidence/conflict logic.
46 | Read-only territorial previews (P4.4) and audit center (P4.5) are exposed via:

- `backend/app/api/routes/territorial.py` — router `territorial` (prefijo `/admin/territorial`).
  - `GET /api/v1/admin/territorial/zones/preview` → `ZoneReconstructionPreview`.
    - Delegates to `ZoneReconstructionPreviewService.preview()` (solo SELECT + cálculo en memoria).
  - `GET /api/v1/admin/territorial/naps/preview` → `NapReconstructionPreview`.
    - Delegates to `NapReconstructionPreviewService.preview()` (solo SELECT + cálculo en memoria).
  - `GET /api/v1/admin/territorial/audit-center` → `TerritorialAuditCenter`.
    - Delegates to `TerritorialAuditCenterService.build()`, que consume ambos previews en memoria para calcular un resumen consolidado por OLT, issues críticos y recomendaciones.
  - Todos estos endpoints son **exclusivamente de lectura**: no realizan apply, no escriben en BD y no acceden a OLTs reales.
  - Ambos endpoints son **exclusivamente de lectura**: no realizan apply, no escriben en BD y no acceden a OLTs reales.

## Rules Never To Omit

- Do not access a real OLT without explicit authorization for that task.
- Import and monitoring are read-only and every real command is audited.
- Never infer permission from saved credentials.
- Never commit `.env`, API keys, OLT credentials, real running-config exports or sensitive logs.
- Keep drivers, parsers, services and API routes separated.
- Scope imported and operational records by `olt_id`; do not mix OLT inventories.
- Preserve manual records and unrelated user changes.
## Last Known State

- Alembic head: `0036_operational_governance`.
- The V1 demo login is removed. Authentication requires local `ADMIN_USERNAME` and `ADMIN_PASSWORD_HASH` values and returns HTTP 503 while unconfigured.
- Generate an initial administrator with `python -m app.scripts.create_initial_admin --username <name>` inside the backend environment.
- Initial ZTE import persists and validates a complete running-config snapshot before parsing.
- Preview does not create definitive inventory; confirmation reuses the same validated snapshot.
- Local test suite: `tests/test_initial_import_service.py` sigue dependiendo de `psycopg` al inicializar el engine PostgreSQL global; en este entorno sin el driver instalado la colección falla incluso con `DATABASE_URL` apuntando a SQLite en memoria.
- El resto de tests históricos no se han vuelto a ejecutar en este entorno; el último estado conocido es 98 tests pasando al 2026-06-20.
Frontend production build and rebuilt containers returned successfully on 2026-06-20; the backend image was rebuilt successfully after the authentication change.
76 | - Frontend territorial audit console: página `/territorial-audit` en Next.js que consume `GET /api/v1/admin/territorial/audit-center` y muestra un dashboard de solo lectura con resumen por OLT, estados territoriales, niveles de confianza, issues críticos y recomendaciones, sin exponer acciones de apply ni formularios de escritura.
77 |   - La consola incorpora filtros de auditoría (por OLT, status, severidad, tipo de issue y búsqueda libre) y un drill-down visual por OLT que expone issues filtrados, recomendaciones relacionadas y conteos principales en modo estrictamente read-only.
- Secret scanning CI workflow `security-scans` ejecuta Gitleaks en push/pull_request con `gitleaks.toml` y publica un SARIF.
- No real OLT access was performed for the snapshot refactor or this handoff preparation.
- Parser de descripciones ZTE ajustado para aceptar `zone` con espacios/guiones y evitar falsos `SIN_ZONA`; tests dedicados pasan (`pytest tests/test_zte_onu_description_parser.py`).
84 | ### Operational Governance – Sprint 0 / 0.5 (Usuarios, Roles, Permisos, Auditoría)
85 | 
86 | - Se introdujo una base de gobierno operativo sin cambiar el mecanismo actual de login (sigue dependiendo de `ADMIN_USERNAME`/`ADMIN_PASSWORD_HASH`):
87 |   - Modelo `User` (usuarios internos) con campos de identidad operativa: `username`, `full_name`, `email`, `status`, `is_active`, `last_login_at`, `created_at/updated_at`, referencias a usuario creador/modificador y `notes`.
88 |   - Modelos `Role`, `Permission`, `UserRole` y `RolePermission` para representar:
89 |     - Roles operativos (`ADMIN`, `TECNICO`, `MONITOR`, `AUDITOR`) sembrados por migración.
90 |     - Permisos desacoplados (`OLT.READ`, `OLT.ADOPT`, `ONU.READ`, `ONU.UPDATE`, `AUDIT.READ`, `USER.READ`, `USER.UPDATE`).
91 |     - Execution Policy por rol/permiso con valores `FULL`, `READ_ONLY`, `REVIEW`, `DENY` y flag `requires_supervisor_approval` preparado para futuros flujos de aprobación.
92 |   - Tabla `OperationId` y servicio `OperationIdService` que generan identificadores reutilizables de operación con formato estable `OP-YYYYMMDD-HHMMSS-XXXX`, pensados para Import, Snapshot, Provisioning, Recovery, Scheduler, CLI, etc.
93 |   - Extensión del modelo `EventLog` para soportar Audit Trail y bitácora operativa con campos opcionales: `operation_id`, `user_id`, `user_name`, `role_code`, `origin`, `result`, `action`, `duration_ms`, `reason`, `error`.
94 |   - Servicio `EventService` actualizado para seguir aceptando la firma histórica mínima (`event_type`, `entity_type`, `entity_id`, `description`) y, opcionalmente, el contexto extendido de auditoría.
95 |   - Servicios de infraestructura Sprint 0.5:
96 |     - `OperatorContextService` para resolver de forma controlada la identidad del operador (creando o reutilizando `User` y rol `ADMIN` para el administrador actual) a partir del subject del token sin activar aún autorización por permisos.
97 |     - `OperationLogService` como helper ligero sobre `OperationIdService` + `EventService` para registrar operaciones con eventos de inicio/éxito/error enriquecidos con `operation_id`, identidad operativa y metadatos de resultado, reutilizable en Import, Snapshot, Provisioning, Scheduler y CLI.
  - Servicio `EventService` actualizado para seguir aceptando la firma histórica mínima (`event_type`, `entity_type`, `entity_id`, `description`) y, opcionalmente, el contexto extendido de auditoría.
- Nueva migración Alembic `0036_operational_governance` que:
  - Crea las tablas `users`, `roles`, `permissions`, `user_roles`, `role_permissions`, `operation_ids`.
  - Extiende `event_logs` con las columnas de contexto y FK opcional a `users`.
  - Siembra los cuatro roles base y un conjunto mínimo de permisos, y define asignaciones de Execution Policy por rol:
    - `ADMIN`: `FULL` en todos los permisos sembrados.
    - `TECNICO`: `FULL` en lecturas ONU/OLT y `REVIEW` en `OLT.ADOPT`.
    - `MONITOR`: `READ_ONLY` en `OLT.READ`, `ONU.READ`, `AUDIT.READ`.
    - `AUDITOR`: `READ_ONLY` en `OLT.READ`, `ONU.READ`, `AUDIT.READ`, `USER.READ`.
- Se añadieron tests unitarios de infraestructura:
  - `tests/test_operation_id_service.py`: verifica formato `OP-YYYY-XXXXXXXX` y persistencia de `OperationId` en SQLite en memoria.
  - `tests/test_event_service.py`: asegura compatibilidad hacia atrás de `EventService.record` y ejercicio del contexto extendido de auditoría.
- `python -m compileall backend/app` ejecutado sin errores tras los cambios, y `pytest tests/test_operation_id_service.py tests/test_event_service.py -q` con 3 tests pasando usando `DATABASE_URL=sqlite+pysqlite:///:memory:`.
- La vista de importación inicial (`/importacion-inicial`) ahora consume `GET /import/jobs/{job_id}` para mostrar el estado del import job y del snapshot asociado, advertencias agregadas y conteos reales de ONUs/VLANs/perfiles/puertos PON/uplinks/NAPs/zonas, manteniendo los pasos visuales existentes y sin introducir WebSockets ni endpoints de eventos.
- No real OLT access was performed for the snapshot refactor or this handoff preparation.
- Parser de descripciones ZTE ajustado para aceptar `zone` con espacios/guiones y evitar falsos `SIN_ZONA`; tests dedicados pasan (`pytest tests/test_zte_onu_description_parser.py`).

### ZTE C300 Telnet driver – running-config y confirmación de prompt

- El driver `ZteC300V125P3TelnetDriver.show_running_config` captura `show running-config` con un timeout mínimo de 120 segundos y valida la presencia de un prompt final estable en la salida.
- La fase de confirmación extra mediante envío de línea vacía (`PHASE_PROMPT_CONFIRMATION`) se ha simplificado: si `_extract_prompt(output)` devuelve un prompt válido, se considera éxito suficiente y no se fuerza una segunda lectura que pueda provocar `EOF received from OLT` pese a snapshot completo.
- Se mantiene el logging por fases (`PHASE_LOGIN`, `PHASE_DISABLE_PAGING`, `PHASE_RUNNING_CONFIG_READ` y un log `PHASE_PROMPT_CONFIRMATION skipped` cuando el prompt ya viene confirmado en el output).
- Los tests `tests/test_zte_c300_phased_logging.py` validan tanto el caso de éxito con un único prompt como la propagación de `DriverCommandError` cuando el error ocurre durante la lectura del running-config.

## Recommended Next Task

Completar la rotación de los valores JWT/crypto/DB de desarrollo por secretos gestionados para despliegue y extender el escaneo de secretos a pre-commit hooks antes del rollout a producción.
Como siguiente línea documental relacionada con ONU, modelo operacional y provisión controlada, consultar también:

- `docs/EFO_MODELO_OPERACIONAL_ONU.md` — modelo operacional de ONU por OLT (OnuType, OnuServiceModeTemplate, Onu, ProvisioningPlan).
- `docs/EFO_NORMALIZACION_MODELO_ONU.md` — normalización de `service_mode_code`, modos simples (`router`/`bridge`/`transparent`/`unknown`) y modelo estructurado esperado desde `pon-onu-mng`.
- `docs/EFO_CALIDAD_DATOS_Y_GOBIERNO_OLT.md` — calidad documental, catálogos técnicos y gobierno de OLT.
 - `docs/EFO_MODELO_TERRITORIAL_FTTH.md` — modelo territorial FTTH por OLT.
 - `docs/EFO_GOBIERNO_DE_CATALOGOS.md` — gobierno de catálogos, clasificación global/técnico/territorial/operativo, invariantes arquitectónicas y roadmap OSS FTTH.

Además, durante la auditoría operacional de ONUs en `OLT-PCM-ZTE-01` se confirmó que los prefijos `NAP` / `ODN` forman parte de la identidad canónica de planta externa:

- `NAP D01` y `ODN D01` son entidades distintas que coexisten en la misma OLT (lo mismo para `D2`, `D3`, `D4`, `F7`).
- No se permite normalización que elimine los prefijos `NAP` / `ODN` / `ODB` ni que colapse ambas entidades bajo un identificador sin prefijo (por ejemplo, `D01`).
- Esta regla está documentada en las EFO de Calidad de Datos y Normalización de Modelo ONU para aplicarse en futuras fases de catálogo NAP por OLT y saneamiento operacional.
- `docs/EFO_CALIDAD_DATOS_Y_GOBIERNO_OLT.md` — calidad documental, catálogos técnicos y gobierno de OLT.
