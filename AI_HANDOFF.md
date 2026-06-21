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

Also read `ai-context/02_ARCHITECTURE.md` for architectural work and `ai-context/06_CHANGELOG_AI.md` for recent implementation history.

## Rules Never To Omit

- Do not access a real OLT without explicit authorization for that task.
- Import and monitoring are read-only and every real command is audited.
- Never infer permission from saved credentials.
- Never commit `.env`, API keys, OLT credentials, real running-config exports or sensitive logs.
- Keep drivers, parsers, services and API routes separated.
- Scope imported and operational records by `olt_id`; do not mix OLT inventories.
- Preserve manual records and unrelated user changes.
## Last Known State

- Alembic head: `0033_complete_snapshots`.
- The V1 demo login is removed. Authentication requires local `ADMIN_USERNAME` and `ADMIN_PASSWORD_HASH` values and returns HTTP 503 while unconfigured.
- Generate an initial administrator with `python -m app.scripts.create_initial_admin --username <name>` inside the backend environment.
- Initial ZTE import persists and validates a complete running-config snapshot before parsing.
- Preview does not create definitive inventory; confirmation reuses the same validated snapshot.
- Local test suite: `tests/test_initial_import_service.py` sigue dependiendo de `psycopg` al inicializar el engine PostgreSQL global; en este entorno sin el driver instalado la colección falla incluso con `DATABASE_URL` apuntando a SQLite en memoria.
- El resto de tests históricos no se han vuelto a ejecutar en este entorno; el último estado conocido es 98 tests pasando al 2026-06-20.
- Frontend production build and rebuilt containers returned successfully on 2026-06-20; the backend image was rebuilt successfully after the authentication change.
- Secret scanning CI workflow `security-scans` ejecuta Gitleaks en push/pull_request con `gitleaks.toml` y publica un SARIF.
- No real OLT access was performed for the snapshot refactor or this handoff preparation.
- Parser de descripciones ZTE ajustado para aceptar `zone` con espacios/guiones y evitar falsos `SIN_ZONA`; tests dedicados pasan (`pytest tests/test_zte_onu_description_parser.py`).
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
