# AI Changelog

## 2026-06-21 — Fase A1: Estado estable para data_quality_status en import inicial

- Corregido `backend/app/services/initial_import_service.py` para:
  - Eliminar imports duplicados de `OnuDataQualityService`.
  - Restaurar la iteración sobre `parsed.uplinks` con `_upsert_uplink` y el contador `uplinks_upserted`, solucionando el `IndentationError` y manteniendo intacta la lógica histórica de importación ZTE.
  - Integrar `OnuDataQualityService` dentro de `_confirm_job` justo después del upsert de cada `Onu`, evaluando `onu.data_quality_status` sin bloquear la importación ni modificar otros flujos.
- Confirmado que `python -m compileall backend/app` se ejecuta sin errores tras los cambios.
- Añadido `tests/test_onu_data_quality_service.py` con pruebas unitarias mínimas que validan:
  - Respeto del estado manual `blocked`.
  - Clasificación `complete` cuando todos los campos críticos y recomendados están presentes.
  - Clasificación `needs_review` cuando sólo faltan campos recomendados (`external_id`, `auth_date`).
  - Clasificación `legacy_incomplete` cuando faltan uno o más campos críticos, incluyendo la distinción de zonas `SIN_ZONA`.
- Ejecutado `pytest tests/test_onu_data_quality_service.py -q`; 4/4 tests pasando.

## 2026-06-21 — Ajustes EFO Calidad de Datos y Gobierno OLT (documental)

- Actualizada `docs/EFO_CALIDAD_DATOS_Y_GOBIERNO_OLT.md` para dejar explícito que:
  - No se permite crear una `Onu` real con información incompleta.
  - El trabajo parcial de provisión debe guardarse exclusivamente como `ProvisioningPlan` en estado `draft`; el concepto de borrador aplica al plan, no a la entidad `Onu`.
  - La eliminación de una OLT en estado `preview_created` debe incluir snapshots, import jobs, previews, logs temporales y cualquier artefacto de importación asociado, con el objetivo de evitar residuos operativos.
  - `ProvisioningTemplate` puede ser global sólo si no contiene referencias técnicas específicas de una OLT (VLAN IDs, Zone IDs, Nap/NapPort IDs, Profile/SpeedProfile IDs u otras FKs por OLT) y se limita a estructura CLI genérica + placeholders.
- Añadida en `ai-context/05_TODO.md` la sección "Data Quality Roadmap (EFO – Fase A)" para preparar la implementación gradual de `data_quality_status`, evaluador de calidad documental y métricas de dashboard sin modificar todavía backend ni frontend.

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

## 2026-06-20 — Wizard de importación OLT robusto para `connection_tested`

- Ajustada la inicialización del wizard `OltImportWizard` en `frontend/src/app/olts/page.tsx` para que, cuando se abra sobre una OLT existente, el paso inicial sea siempre el 2 ("Test read-only").
- Eliminado el salto automático a `step=3` cuando `initial_import_status === "connection_tested"`, obligando a reejecutar `read-only-check` en el contexto del wizard antes de habilitar el botón "Ejecutar importacion inicial".
- Con este cambio se evita el estado bloqueado en el que una OLT `connection_tested` abría el wizard directamente en preview con `connection = null`, `connectionValidated = false` y el botón de preview deshabilitado.
- Ejecutado `npm run build` en `frontend`; la build Next.js/TypeScript completó con éxito confirmando que el cambio respeta el tipado y las rutas existentes.

## 2026-06-20 — Instrumentación EOF en Telnet para preview desde OLT

- Extendido `TelnetlibTransport.read_until_prompt` en `backend/app/drivers/transports.py` para capturar explícitamente `EOFError` de `telnetlib.expect` mientras se espera el prompt.
- Ante un EOF inesperado, ahora se acumulan los `chunks` recibidos, se sanea la salida con `_sanitize_cli_output` y se lanza un `DriverCommandError(command="show running-config", message="EOF received from OLT", output=<excerpt>)`.
- Esto permite que el endpoint `POST /olts/{id}/import/preview-from-telnet` entre en el bloque `except DriverCommandError` y, con `TELNET_DIAGNOSTIC_MODE=true`, devuelva `detail.diagnostic.output_excerpt` con un fragmento de la salida real justo antes del cierre de la sesión Telnet.
- Añadido el test `tests/test_telnet_eof_diagnostic.py` que valida que un cliente Telnet simulado que lanza `EOFError("telnet connection closed")` provoca un `DriverCommandError` con `command="show running-config"` y el mensaje esperado.
- Ejecutado `DATABASE_URL=sqlite+pysqlite:///:memory: pytest`; la suite completa pasó con 106/106 tests, confirmando que la instrumentación no rompe la lógica existente.

## 2026-06-20 — Logging por fases en driver ZTE C300 para preview Telnet

- Añadido logging estructurado por fases en `ZteC300V125P3TelnetDriver` (`backend/app/drivers/zte/c300_v125p3_telnet/driver.py`) para distinguir claramente:
  - `PHASE_LOGIN` (conexión y login inicial, incluyendo prompt detectado y tiempo transcurrido).
  - `PHASE_DISABLE_PAGING` (ejecución de `terminal length 0`, con prompt y un `output_excerpt` limitado).
  - `PHASE_RUNNING_CONFIG_READ` (ejecución de `show running-config`, con bytes leídos, prompt final y tiempo total).
  - `PHASE_PROMPT_CONFIRMATION` (envío de línea vacía posterior y confirmación del prompt final).
- Los logs incluyen `elapsed_seconds`, `command` y, cuando aplica, el `prompt` detectado y un extracto de salida, sin cambiar la lógica funcional ni el manejo de excepciones existente.
- Estas trazas permiten saber si un EOF o un `DriverCommandError` se producen durante la lectura del running-config o en la fase de confirmación del prompt.
- Añadido el test `tests/test_zte_c300_phased_logging.py` con un `FakeTelnetClient` que simula prompts y salida de `show running-config` para verificar que `show_running_config` sigue funcionando correctamente y que los errores se siguen propagando como `DriverCommandError`.
- Ejecutado `DATABASE_URL=sqlite+pysqlite:///:memory: pytest`; la suite completa pasó con 108/108 tests tras añadir estos tests adicionales.

## 2026-06-21 — Evitar falsos negativos en confirmación de prompt ZTE

- Ajustado `ZteC300V125P3TelnetDriver.show_running_config` para tratar un `show running-config` con prompt final estable como éxito suficiente sin requerir una confirmación extra del prompt mediante envío de línea vacía.
- Eliminada la lectura adicional que podía provocar `EOF received from OLT` pese a haber capturado un snapshot completo y válido; ahora se registra un log `PHASE_PROMPT_CONFIRMATION skipped` cuando el prompt ya se ha confirmado a partir del propio output.
- Actualizado `tests/test_zte_c300_phased_logging.py` para validar que `show_running_config` devuelve la salida cuando el script de Telnet sólo proporciona un prompt final estable, manteniendo el test de error cuando `DriverCommandError` se produce durante la fase de lectura.
- Ejecutado `DATABASE_URL=sqlite+pysqlite:///:memory: pytest -q`; la suite completa sigue pasando con 108/108 tests, confirmando que el cambio no rompe flujos de importación ni de monitoreo.

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
