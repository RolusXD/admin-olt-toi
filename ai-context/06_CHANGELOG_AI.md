# AI Changelog

## 2026-06-25 — Sprint 0.5: Integración de Gobierno Operativo + entorno VS Code/Pylance

- Entorno de desarrollo y tooling:
  - Añadido `.vscode/settings.json` en la raíz del repositorio configurando:
    - `python.analysis.extraPaths = ["backend"]` para que Pylance trate `backend` como raíz de paquetes y resuelva correctamente imports como `app.models.base` y `app.services.event_service` tanto en el backend como en `tests/` sin hacks adicionales.
    - `python.testing.pytestArgs = ["tests"]` y `python.testing.pytestEnabled = true` alineados con `pytest.ini`, evitando configuraciones ad-hoc en los tests.
  - Con esta configuración, los errores de Pylance "No se pudo resolver importación 'app.models.base' / 'app.models.entities' / 'app.services.*'" en `tests/test_event_service.py` y `tests/test_operation_id_service.py` desaparecen manteniendo los imports absolutos existentes.

- Backend – servicios de identidad operativa y bitácora:
  - Añadido `backend/app/services/operator_context_service.py` con:
    - `OperatorContext`: dataclass mínima (`user_id`, `user_name`, `role_code`, `origin`) para representar la identidad operativa del usuario actual sin mezclarla con JWT ni FastAPI.
    - `OperatorContextService`: servicio que resuelve un `OperatorContext` a partir del subject del token (por ahora el admin definido por `ADMIN_USERNAME`), aplicando reglas conservadoras:
      - Si existe un `User` con `username == subject`, se reutiliza.
      - Si no existe, crea un `User` activo con ese `username` y `full_name` igual al username.
      - Si existe un rol `ADMIN`, asegura exactamente un `UserRole` (`ADMIN`) asociado al usuario.
      - No implementa autorización por permisos; sólo identidad y rol lógico para enriquecer logs.
  - Añadido `backend/app/services/operation_log_service.py` con:
    - `OperationContext`: contexto de operación (`operation_id`, `started_at`, `operator`) para encadenar eventos bajo el mismo identificador.
    - `OperationLogService`: helper que combina `OperationIdService` y `EventService` para registrar operaciones con eventos enriquecidos:
      - `start(...)` genera un nuevo `OperationId`, registra un evento con `result="started"` y devuelve `OperationContext`.
      - `success(ctx, ...)` registra un segundo evento con `result="success"`, heredando `operation_id`, identidad de operador y calculando `duration_ms` (salvo que se pase explícito).
      - `error(ctx, ...)` registra un evento con `result="failed"` y campo `error` opcional.
      - Mantiene compatibilidad total con usos existentes de `EventService.record` al no modificar su firma.

- Backend – servicio de seguridad (JWT):
  - Extendida `backend/app/core/security.py` para introducir `decode_access_token(token: str) -> str`:
    - Usa `jose.JWTError` para capturar errores de firma/expiración y devuelve el `sub` (username) como string normalizado.
    - Lanza `ValueError` en caso de token inválido o sin `sub` no vacío; el manejo HTTP queda a cargo de las dependencias FastAPI.
    - Prepara el terreno para dependencias tipo `get_current_operator` sin mezclar detalles de JWT en servicios de dominio.

- Backend – formato de OperationId:
  - Actualizado `backend/app/services/operation_id_service.py` para cambiar el formato de los identificadores de operación antes de adopción masiva:
    - De `OP-YYYY-XXXXXXXX` (año + sufijo hex de 8 caracteres) a `OP-YYYYMMDD-HHMMSS-XXXX` (fecha y hora en UTC + sufijo hex de 4 caracteres en mayúsculas).
    - Mantiene la columna `code` como `String(32)` y la unicidad se sigue garantizando por la UNIQUE constraint en base de datos.
    - Documentado en el docstring el nuevo formato preferido para futuras integraciones (Import, Snapshot, Provisioning, Scheduler, CLI, etc.).

- Tests nuevos y actualizados (infraestructura Sprint 0.5):
  - `tests/test_operation_id_service.py`:
    - Actualizado para validar el nuevo formato `OP-YYYYMMDD-HHMMSS-XXXX` (4 secciones separadas por guiones, fecha de 8 dígitos, hora de 6 dígitos y sufijo hexadecimal de 4 caracteres).
  - `tests/test_operator_context_service.py`:
    - Verifica que `OperatorContextService.resolve("test-admin")` en una BD SQLite en memoria:
      - Crea un `User` con `username="test-admin"` cuando no existe.
      - Crea el vínculo `UserRole` con un rol `ADMIN` sembrado previamente y devuelve un `OperatorContext` con `role_code="ADMIN"` y `origin="api"`.
    - Verifica que, cuando el usuario y el vínculo `UserRole` ya existen, la resolución no crea duplicados y reutiliza el mismo `user_id`.
  - `tests/test_operation_log_service.py`:
    - Comprueba que `OperationLogService.start` + `success` generan un `OperationId` persistido y dos entradas en `EventLog` con el mismo `operation_id`, donde los resultados son `"started"` y `"success"` y los campos de identidad (`user_name`, `role_code`, `origin`) se copian correctamente desde `OperatorContext`.
    - Comprueba que `error` genera un par de eventos con resultados `"started"` y `"failed"` y que `error="boom"` se persiste en el evento de fallo.

- Documentación y contexto AI:
  - Actualizado `ai-context/05_TODO.md` en la sección *Sprint 0 – Gobierno Operativo* para:
    - Reflejar el nuevo formato oficial de `OperationId` (`OP-YYYYMMDD-HHMMSS-XXXX`).
    - Marcar como cumplida la introducción de servicios de infraestructura `OperatorContextService` y `OperationLogService` como base para integrar `OperationIdService`/`EventService` en flujos clave sin activar aún autorización por permisos ni bloquear endpoints.

- Verificación técnica:
  - Ejecutado `python -m compileall backend/app` sin errores tras introducir los nuevos servicios y el cambio de formato de `OperationId`.
  - Ejecutado `pytest tests/test_operation_id_service.py tests/test_event_service.py tests/test_operator_context_service.py tests/test_operation_log_service.py -q` con `DATABASE_URL=sqlite+pysqlite:///:memory:`; 7/7 tests pasando en ~0.7s.

## 2026-06-25 — Sprint 0.75: Primeros flujos reales con OperationLogService

- Backend – helper de contexto de operador para FastAPI:
  - Actualizado `backend/app/api/deps.py` para introducir:
    - `get_current_operator(db, authorization_header) -> OperatorContext` que:
      - Si no hay cabecera `Authorization` devuelve un operador lógico `anonymous` con rol `SYSTEM` y origen `api`.
      - Si hay `Authorization: Bearer <token>` decodifica el JWT con `decode_access_token` y resuelve un `OperatorContext` real mediante `OperatorContextService`.
      - Traduce errores de token inválido a HTTP 401 sin modificar el flujo de login existente.
    - Exporta explícitamente `DbSession`, `get_olt_or_404` y `get_current_operator` para uso en routers.

- Backend – integración de OperationLogService en Importación Inicial:
  - Extendida la firma de `InitialImportService` (`backend/app/services/initial_import_service.py`) para aceptar un parámetro `origin: str = "api"` y componer internamente un `OperationLogService` (`self.operation_log`).
  - Envolvieron los métodos principales del flujo de importación inicial con OperationLogService:
    - `create_preview_from_text(olt_id, raw_config, source="text", operator=None)`:
      - Registra un evento de inicio `IMPORT_INITIAL` (acción `IMPORT.INITIAL.PREVIEW`) al comenzar la operación.
      - Crea el `ConfigSnapshot` con estado `captured` y calcula checksum.
      - Registra un evento `IMPORT_SNAPSHOT_CAPTURED` con `operation_id`, identidad operativa (cuando existe) y `origin` coherente.
      - Genera el preview mediante `_create_preview_from_snapshot` y, en caso de éxito, registra `success` sobre el mismo `operation_id`. Ante error, registra `error` con descripción entendible y vuelve a propagar la excepción.
    - `create_preview_from_telnet(olt_id, operator=None)`:
      - Registra inicio `IMPORT_INITIAL` (Telnet) y envuelve la ejecución de `show running-config` (incluyendo casos `DriverTimeoutError` y `DriverCommandError`) para registrar errores de operación con el mismo `operation_id`.
      - Crea el snapshot `captured`, registra `IMPORT_SNAPSHOT_CAPTURED` y delega en `_create_preview_from_snapshot`.
      - Registra `success` o `error` de preview reutilizando el contexto `OperationContext`.
    - `confirm_import(import_job_id, operator=None)` y `confirm(olt, import_job_id, operator=None)` delegan en `_confirm_job(olt, job, operator=operator)`.
    - `_confirm_job(olt, job, operator=None)`:
      - Registra inicio `IMPORT_INITIAL_CONFIRM` con acción `IMPORT.INITIAL.CONFIRM` antes de validar snapshot y aplicar cambios.
      - Mantiene intacta la lógica de validación existente (estado del snapshot, checksum, validación estructural y errores críticos).
      - Tras completar importación y marcar `job.status="confirmed"` / `snapshot.status="confirmed"` / `olt.initial_import_status="confirmed"`:
        - Registra un evento `IMPORT_CONFIRMED` en `EventService` con `operation_id` del contexto, identidad operativa, `origin` y `action="IMPORT.INITIAL.CONFIRM"`.
        - Registra `success` en `OperationLogService` para `IMPORT_INITIAL_CONFIRM`, preservando compatibilidad con tests e invariantes actuales.
  - No se modificó la lógica de parseo ni de upsert de entidades (`Vlan`, `Onu`, `Zone`, `Nap`, etc.); los cambios se limitan a auditoría y envoltura.

- Backend – Snapshot manual como flujo de auditoría (backup):
  - Actualizado `backend/app/services/olt_service.py`:
    - `backup(olt: Olt, operator: OperatorContext | None = None) -> BackupFile` ahora:
      - Crea un `OperationLogService` con `origin` derivado del operador (por defecto `api`).
      - Registra inicio `SNAPSHOT_MANUAL` (acción `SNAPSHOT.MANUAL`) con descripción entendible para operador.
      - Ejecuta `driver.backup()` para obtener el running-config y captura errores registrando eventos `failed` sobre el mismo `operation_id`.
      - Persiste el archivo en `storage/backups/olt-{id}-running-config.txt` y crea un `BackupFile` como antes.
      - Registra un evento `BACKUP_CREATED` en `EventService` enriquecido con `operation_id`, `user_name`, `role_code`, `origin` y `action="SNAPSHOT.MANUAL"`.
      - Registra `success` en `OperationLogService` con descripción de snapshot manual completado.
  - El endpoint `POST /olts/{olt_id}/backup` sigue delegando en `OltService.backup(olt)` sin requerir explícitamente `get_current_operator`; futuras fases podrán extenderlo.

- Backend – Scheduler y OperationLogService:
  - Actualizado `backend/app/tasks/monitoring.py` para que las tareas automáticas utilicen OperationLogService con origen `SCHEDULER` y rol `SYSTEM`:
    - `sync_onu_states_task(olt_id)`:
      - Resuelve la OLT desde `SessionLocal`.
      - Construye un `OperatorContext(user_id=None, user_name="scheduler", role_code="SYSTEM", origin="SCHEDULER")`.
      - Usa `OperationLogService(db, origin="SCHEDULER")` para registrar `SCHEDULER_SYNC_ONU_STATES` (inicio/éxito/error) alrededor de la llamada a `OltCliService.sync_onus(olt)`.
    - `sync_onu_power_task(olt_id)`:
      - Mismo patrón, registrando eventos `SCHEDULER_SYNC_ONU_POWER` y envolviendo `OltCliService.sync_power(olt)`.
    - `poll_olt_power()` se mantiene como placeholder sin auditoría adicional.
  - De esta forma, las tareas automáticas generan Operation IDs con `origin="SCHEDULER"` y rol lógico `SYSTEM`, sin requerir usuario humano.

- Backend – integración de get_current_operator en rutas de OLT/import:
  - Actualizado `backend/app/api/routes/olts.py` para aprovechar `get_current_operator` en los endpoints de importación inicial:
    - `POST /olts/{id}/import/preview` ahora inyecta `operator=Depends(get_current_operator)` y llama a `InitialImportService(db).preview(olt, operator=operator)`.
    - `POST /olts/{id}/import/preview-from-telnet` (nueva variante principal) delega en `create_preview_from_telnet(olt_id, operator=operator)` y mantiene el modo diagnóstico previo (exponiendo un excerpt de CLI sólo cuando `settings.telnet_diagnostic_mode` está activo).
    - `POST /olts/{id}/import/preview-from-telnet` histórico se mantiene como alias (`initial_import_preview_from_telnet_legacy`) para compatibilidad, pero ya acepta también `operator=Depends(get_current_operator)`.
    - `POST /olts/{id}/import/confirm/{import_job_id}` ahora pasa `operator` a `InitialImportService.confirm(olt, import_job_id, operator=operator)` de modo que todos los eventos de confirmación de importación heredan identidad operativa y `operation_id`.
    - `POST /olts/{id}/import/preview-from-file` sigue usando `create_preview_from_text` sin operador explícito para mantener compatibilidad con flujos batch existentes; se documenta que la identidad operativa puede añadirse en una fase posterior.

- Tests y verificación:
  - `tests/test_initial_import_service.py` actualizado para seguir usando `InitialImportService(db_session)` con la nueva firma opcional (`origin="api"`), sin necesidad de pasar `operator` en los tests actuales:
    - Firmas como `create_preview_from_text(olt.id, raw_config)` y `confirm_import(preview["import_job_id"])` permanecen válidas y ejercen el nuevo código de auditoría sin requerir ajustes en las aserciones de dominio.
    - Se mantiene la compatibilidad con los contratos existentes de `ImportJobRead`, `ConfigSnapshot` y contadores de importación.
  - `tests/test_environments.py` ajustado para alinear imports con los modelos actuales, manteniendo la lógica de separación de entornos y conteo de ONUs.
  - Ejecutado `python -m compileall backend/app` sin errores tras introducir `get_current_operator`, la integración de OperationLogService en import/snapshot/Scheduler y los cambios en routers/tareas.
  - Intento de `DATABASE_URL=sqlite+pysqlite:///:memory: pytest tests/test_initial_import_service.py tests/test_operation_log_service.py tests/test_operator_context_service.py tests/test_operation_id_service.py tests/test_event_service.py tests/test_environments.py -q` falló en la fase de colección por falta del driver `psycopg`, coherente con el estado conocido documentado en `AI_HANDOFF.md`; los errores no están relacionados con los cambios de este Sprint.

## 2026-06-25 — Sprint 0: Gobierno Operativo (Usuarios, Roles, Permisos, Auditoría)

- Backend – modelos y migración:
  - Añadidos modelos SQLAlchemy en `backend/app/models/entities.py`:
    - `User`: usuarios internos con campos de identidad operativa (`username`, `full_name`, `email`, `status`, `is_active`, `last_login_at`, `created_at/updated_at`, referencias a usuario creador/modificador y `notes`).
    - `Role`: catálogo de roles operativos (`code`, `name`, `description`, `is_active`).
    - `Permission`: catálogo desacoplado de permisos lógicos (`code`, `name`, `description`, `category`, `is_active`).
    - `UserRole`: asignación de roles a usuarios (`user_id`, `role_id`, `assigned_at`, `assigned_by_user_id`) con restricción única `uq_user_roles_user_role`.
    - `RolePermission`: asignación de permisos a roles con Execution Policy (`execution_policy` = `FULL`/`READ_ONLY`/`REVIEW`/`DENY`, `requires_supervisor_approval`, `is_active`) y restricción `uq_role_permissions_role_permission`.
    - `OperationId`: secuencia global de identificadores de operación (`code` único con formato `OP-YYYY-XXXXXXXX`, `created_at`).
    - Extensión de `EventLog` para soportar Audit Trail/bitácora operativa con campos opcionales: `operation_id`, `user_id`, `user_name`, `role_code`, `origin`, `result`, `action`, `duration_ms`, `reason`, `error` y relación opcional `user`.
  - Actualizado `backend/app/models/__init__.py` para exportar los nuevos modelos (`User`, `Role`, `Permission`, `UserRole`, `RolePermission`, `OperationId`, `MonitoringExecution`).
  - Añadida migración Alembic `0036_operational_governance` que:
    - Crea las tablas físicas `users`, `roles`, `permissions`, `user_roles`, `role_permissions`, `operation_ids`.
    - Extiende `event_logs` con las columnas de contexto y FK opcional `user_id → users.id` (ondelete `SET NULL`).
    - Siembra los cuatro roles base requeridos por el Sprint 0: `ADMIN`, `TECNICO`, `MONITOR`, `AUDITOR`.
    - Siembra un conjunto mínimo de permisos: `OLT.READ`, `OLT.ADOPT`, `ONU.READ`, `ONU.UPDATE`, `AUDIT.READ`, `USER.READ`, `USER.UPDATE`.
    - Crea asignaciones iniciales de Execution Policy por rol/permiso:
      - `ADMIN`: `FULL` en todos los permisos sembrados.
      - `TECNICO`: `FULL` en `OLT.READ`, `ONU.READ`, `ONU.UPDATE` y `REVIEW` en `OLT.ADOPT`.
      - `MONITOR`: `READ_ONLY` en `OLT.READ`, `ONU.READ`, `AUDIT.READ`.
      - `AUDITOR`: `READ_ONLY` en `OLT.READ`, `ONU.READ`, `AUDIT.READ`, `USER.READ`.

- Backend – servicios de infraestructura operativa:
  - Añadido `backend/app/services/operation_id_service.py` con `OperationIdService.generate()` para emitir Operation IDs con formato `OP-YYYY-XXXXXXXX`, persistiendo el registro en `OperationId` y haciendo sólo `flush` (el `commit` queda a cargo de quien lo use).
  - Reescrito `backend/app/services/event_service.py` para convertirlo en servicio de bitácora operativa:
    - Mantiene compatibilidad con la firma histórica `record(event_type, entity_type, entity_id, description)`.
    - Añade parámetros opcionales de contexto de auditoría: `operation_id`, `user_id`, `user_name`, `role_code`, `origin`, `result`, `action`, `duration_ms`, `reason`, `error`.
    - Documenta explícitamente que no implementa aún workflows de aprobación ni lógica de permisos; sólo registra eventos enriquecidos.

- Tests nuevos (infraestructura Sprint 0):
  - `tests/test_operation_id_service.py`:
    - Crea una BD SQLite en memoria con `Base.metadata.create_all`.
    - Verifica que `OperationIdService.generate()` devuelve un registro con `code` que empieza por `OP-`, respeta la estructura `OP-YYYY-XXXXXXXX` (tres secciones separadas por guiones, año de 4 dígitos y sufijo hexadecimal de 8 caracteres) y se persiste correctamente.
  - `tests/test_event_service.py`:
    - `test_event_service_records_basic_event`: asegura que el uso mínimo histórico sigue funcionando, que el evento se persiste y que los campos extendidos quedan en `None` por defecto.
    - `test_event_service_records_extended_context`: registra un evento con todos los campos extendidos y valida que se persistan correctamente en `EventLog`.

- Documentación y contexto AI:
  - Actualizado `ai-context/00_PROJECT_CONTEXT.md` para reflejar el nuevo Alembic head `0036_operational_governance`.
  - Actualizado `ai-context/05_TODO.md` añadiendo la sección **"Sprint 0 – Gobierno Operativo (Usuarios, Roles, Permisos, Auditoría)"** con los ítems implementados (modelos, tablas y servicios) y dejando explícito como TODO futuro la integración progresiva de `OperationIdService`/`EventService` en flujos clave sin romper comportamiento existente.
  - Actualizado `AI_HANDOFF.md` en **Last Known State** con:
    - `Alembic head: 0036_operational_governance`.
    - Resumen de los modelos `User`/`Role`/`Permission`/`UserRole`/`RolePermission`/`OperationId`, la extensión de `EventLog` y el comportamiento de `EventService`.
    - Notas de verificación (`python -m compileall backend/app` sin errores y `pytest tests/test_operation_id_service.py tests/test_event_service.py -q` con 3 tests pasando usando SQLite en memoria).

- Verificación técnica:
  - Ejecutado `python -m compileall backend/app` sin errores después de añadir modelos, servicios y migración.
  - Ejecutado `DATABASE_URL=sqlite+pysqlite:///:memory: pytest tests/test_operation_id_service.py tests/test_event_service.py -q`; 3/3 tests pasando en ~0.9s.

## 2026-06-24 — P5.1 Filtros y drill-down en Consola de Auditoría Territorial (frontend)

- Frontend:
  - Extendida la página `/territorial-audit` (`frontend/src/app/territorial-audit/page.tsx`) para mejorar la experiencia de revisión **solo lectura** del `TerritorialAuditCenter` añadiendo:
    - Filtros superiores:
      - Por OLT (`olt_code`) mediante un selector derivado de `olt_summaries`.
      - Por `status` de OLT (`HEALTHY`, `NEEDS_REVIEW`, `DEGRADED`, `CRITICAL`).
      - Por severidad de issue (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
      - Por `issue_type` (lista deducida de `critical_issues`).
      - Búsqueda libre que aplica sobre `olt_code`, `entity_name`, `issue_type`, `message` y `recommendation`.
    - Lógica de filtrado en memoria usando `useState`/`useMemo` para mantener el endpoint backend como read-only sin introducir nuevos parámetros ni peticiones.
    - Tabla por OLT con filtros aplicados (por OLT y status) y estado vacío cuando no hay coincidencias.
    - Drill-down visual por OLT mediante botón "Ver detalle" que expande una fila y muestra:
      - Conteos principales para la OLT filtrada: issues filtrados, conteos por severidad `CRITICAL`/`HIGH` y suma de ONUs con Zone/NAP cruzados.
      - Listado compacto de issues de esa OLT que respetan los filtros globales de severidad/tipo/búsqueda, limitado a las primeras filas con indicador de overflow.
      - Recomendaciones relacionadas para la OLT (filtradas por búsqueda libre y heurística simple sobre `olt_code`/`olt_name`), indicando cuando sólo aplican recomendaciones generales.
    - Sección de Issues críticos actualizada para:
      - Aplicar los filtros por OLT, severidad, `issue_type` y búsqueda libre.
      - Mostrar contador `mostrando N de M issues` para dejar claro el efecto de filtros.
      - Mostrar estado vacío explícito cuando la combinación de filtros no devuelve issues.
    - Sección de Recomendaciones actualizada para:
      - Filtrar recomendaciones según la búsqueda libre cuando hay término de búsqueda.
      - Mantener la lista completa cuando no hay búsqueda activa.
      - Mostrar un mensaje de "No hay recomendaciones que coincidan" cuando el filtro deja la lista vacía.
    - UX adicional:
      - Botón "Limpiar filtros" que resetea todos los filtros, la búsqueda y el estado expandido de OLT.
      - Mensajes de estado vacío para tabla de OLTs, issues y recomendaciones cuando corresponda.
      - Mantenimiento del badge "SOLO LECTURA / SIN APPLY" y estilos existentes (`Panel`, `SummaryCard`, badges de estado/severidad) sin introducir nuevas dependencias.
- Documentación de handoff y contexto AI:
  - `AI_HANDOFF.md`: ampliada la sección de **Last Known State** para documentar que la consola `/territorial-audit` ahora incluye filtros de auditoría (OLT, status, severidad, tipo de issue, búsqueda libre) y un drill-down visual por OLT que expone issues filtrados, recomendaciones relacionadas y conteos principales, manteniéndose estrictamente en modo read-only.
  - `ai-context/05_TODO.md`: extendida la sección **P5 – Consola Inteligente de Auditoría Territorial** para reflejar que la página `/territorial-audit` ya incluye filtros superiores y drill-down visual por OLT, sin añadir acciones de apply ni formularios de escritura.
- Verificación:
  - Ejecutado `cd frontend && npm run build`; la build de Next.js/TypeScript completó correctamente, confirmando que los cambios en `/territorial-audit` respetan el tipado y las rutas existentes.
  - No se añadieron ni modificaron endpoints backend, esquemas Pydantic, migraciones de base de datos ni acciones de apply; todo el trabajo se limita al frontend y sigue siendo de solo lectura.

## 2026-06-21 — Fase A2: Observabilidad de calidad documental ONU

- Añadido el campo `Onu.data_quality_missing_fields` en el modelo (texto JSON) y la migración `0035_onu_data_quality_missing_fields` para persistir la lista de campos faltantes por ONU sin bloquear provisión.
- Extendido `OnuDataQualityService.evaluate` para:
  - Respetar `data_quality_status = "blocked"` y registrar `data_quality_missing_fields=[]`.
  - Calcular `missing_fields` por ONU (críticos + recomendados) y persistirlos como JSON en `data_quality_missing_fields` junto con el estado `complete/needs_review/legacy_incomplete`.
- Implementados endpoints de sólo lectura para observabilidad de calidad documental:
  - `GET /olts/{id}/data-quality-summary` (schema `OltDataQualitySummary`): devuelve `total_onus`, conteos por estado (`complete`, `needs_review`, `legacy_incomplete`, `blocked`) y `quality_score` (% de ONUs `complete`).
  - `GET /onus/data-quality` (schema `OnuDataQualityRead`): listado filtrable por `olt_id`, `status` (data_quality_status), `zone` y `nap`, con los `missing_fields` reconstruidos a partir de `data_quality_missing_fields`.
- Añadidos modelos de esquema en `backend/app/schemas/entities.py`:
  - `OltDataQualitySummary` para el resumen por OLT.
  - `OnuDataQualityRead` para filas centradas en calidad documental.
- Añadidos tests:
  - `tests/test_onu_data_quality_service.py` ampliado para verificar la persistencia de `data_quality_missing_fields` en todos los estados (`complete`, `needs_review`, `legacy_incomplete`, `blocked`).
  - `tests/test_api_data_quality.py` que ejerce directamente `olt_data_quality_summary` y `list_onus_data_quality` sobre una base SQLite en memoria, validando conteos por estado y filtros por `status`.
- Ejecutado `python -m compileall backend/app` sin errores tras los cambios.
- Ejecutado `DATABASE_URL=sqlite+pysqlite:///:memory: pytest tests/test_onu_data_quality_service.py tests/test_api_data_quality.py -q`; 6/6 tests pasando, confirmando Fase A2 estable en servicio y API interna.

## 2026-06-22 — Fase P1: Sección "Comportamiento ONU" en ficha ONU (solo lectura)

- Backend:
  - Extendido el esquema `OnuRead` en `backend/app/schemas/entities.py` para incluir un bloque opcional `behavior: OnuBehaviorRead | None`, que resume el comportamiento ONU efectivo sin modificar el modelo de base de datos.
  - Añadido el modelo `OnuBehaviorRead` como DTO de solo lectura con los campos:
    - `mode_label`, `mode_code`, `vlan_id`, `vlan_name`, `speed_profile_up`, `speed_profile_down`,
      `dhcp_source`, `use_iphost`, `use_veip`, `use_vlan_filter`, `use_loop_detect`, `disable_wifi`, `speed_profile_code`.
  - Actualizado `GET /onus/{id}` en `backend/app/api/routes/onus.py` para, sin tocar provisioning ni Telnet:
    - Resolver el modo a partir de `Onu.service_mode_code` y `OnuServiceModeTemplate` (`olt_id` + `mode_code`), mapeando:
      - `router_iphost` → `Router`, `bridge_tag_internet` → `Bridge`, `transparent_special` → `Transparente`.
    - Enriquecer la información con:
      - `Vlan` (nombre opcional asociado a `Onu.vlan`).
      - `SpeedProfile` (cuando `speed_profile_up/down` coinciden con un perfil combinado), para exponer `speed_profile_code`.
    - Adjuntar dinámicamente `onu.behavior = OnuBehaviorRead(...)` respetando compatibilidad con clientes anteriores que no esperen el campo.
- Frontend:
  - Actualizado `frontend/src/types/index.ts` para que el tipo `Onu` incluya el campo opcional `behavior` alineado con `OnuBehaviorRead`.
  - Extendida la página de detalle `frontend/src/app/onus/[id]/page.tsx` para mostrar una nueva sección "Comportamiento ONU" dentro del panel principal de la ficha ONU:
    - Cuando existe `behavior`:
      - Muestra Modo ONU (etiqueta amigable), `VLAN WAN / servicio` (id + nombre), perfiles de subida y bajada,
        `DHCP source`, flags de `IPHost`, `VEIP`, `VLAN Filter`, `Loop Detect`, `WiFi deshabilitado`, `Código de modo` y, si aplica, `Perfil combinado`.
    - Cuando no existe `behavior` (p.ej. `service_mode_code` nulo o sin plantilla activa):
      - Muestra un bloque estático "Desconocido/importado" con una advertencia suave indicando que el comportamiento fue importado o no pudo clasificarse completamente.
    - La sección es estrictamente de solo lectura; no se han añadido controles de edición ni acciones que disparen Telnet.
- Verificación:
  - Ejecutado `python -m compileall backend/app` sin errores.
  - Ejecutado `pytest`; 114 tests pasando, confirmando que los cambios en esquema y endpoint son compatibles con la suite existente.
  - Ejecutado `cd frontend && npm run build`; build de Next.js/TypeScript completada correctamente, incluyendo la ruta dinámica `/onus/[id]`.

## 2026-06-23 — Normalización documental de `service_mode_code` y modelo ONU

- Añadido `docs/EFO_NORMALIZACION_MODELO_ONU.md` como especificación formal para la normalización del modelo ONU y `service_mode_code`, definiendo:
  - Modos simples de servicio (`router`, `bridge`, `transparent`, `unknown`) como proyección de `service_mode_code`.
  - Separación conceptual entre Modo ONU (comportamiento / `OnuServiceModeTemplate`), Modo WAN (VLAN principal), Modo Puerto y catálogo de VLANs por OLT.
  - Modelo estructurado esperado desde el parser de `pon-onu-mng` (`OnuPonOnuMngModel`) como DTO intermedio, sin cambiar el esquema de BD.
  - Reglas de clasificación basadas en patrones típicos observados en ONUs representativas (1215, 1217, 1218, 1227) del running-config de `OLT-PCM-ZTE-01`.
  - Atribución clara de responsabilidades entre `Onu`, `OnuType`, `OnuServiceModeTemplate` y `ProvisioningPlan`.
  - Confirmación documental de que VLANs, Zonas, NAPs, Tipos ONU y Modos ONU (`OnuServiceModeTemplate`) son siempre específicos de una OLT.
- Actualizado `ai-context/05_TODO.md` con una nueva sección "Modelo ONU y service_mode_code" para planificar:
  - La implementación de un parser estructurado de `pon-onu-mng` alineado con la nueva EFO.
  - La definición y poblamiento de `OnuServiceModeTemplate` por OLT a partir de los modos reales observados.
  - La integración de la normalización `service_mode_code_raw → service_mode_code` en la importación inicial, manteniendo ONUs no clasificadas en modo simple `unknown`.

## 2026-06-23 — Fase P2: Parser estructurado `pon-onu-mng` y clasificación de modos ONU

- Documentación:
  - Actualizado `docs/EFO_MODELO_OPERACIONAL_ONU.md` para alinear los modos ONU simples con la EFO de normalización:
    - Modos simples oficiales: `router`, `bridge`, `transparent`, `unknown` (expuestos como `Router / Bridge / Transparente / Desconocido` en UI).
    - "Híbrido" deja de ser un modo ONU principal y pasa a ser un concepto de configuración avanzada dentro de `OnuServiceModeTemplate` y modo de puerto.
  - Actualizado `docs/EFO_NORMALIZACION_MODELO_ONU.md` para:
    - Dejar explícito que "Híbrido" **no** es un quinto modo simple y siempre se proyecta a `router`, `bridge`, `transparent` o `unknown`.
    - Aclarar que `access`, `hybrid`, `trunk`, `transparent` son **modos de puerto**, no valores de `service_mode_code`.
    - Reforzar que los ejemplos ONU 1215/1217/1218/1227 son casos de auditoría histórica ilustrativos, no definiciones normativas.

- Parser estructurado `pon-onu-mng`:
  - Extendida la dataclass `ParsedOnuManagementMode` en `backend/app/drivers/zte/c300_v125p3_telnet/zte_onu_management_mode_parser.py` para incluir campos estructurados adicionales sin cambiar el esquema de BD:
    - `mode_simple`: proyección normalizada (`router` / `bridge` / `transparent` / `unknown`).
    - `port_mode`: modo principal de puerto (`access` / `tag` / `hybrid` / `trunk` / `transparent` / `unknown`).
    - `service_vlans`: lista de VLANs de servicio detectadas a partir de `flow ... vid X`, bindings `gemport` y `switchport vlan ... tag vport 1`.
    - `allowed_vlans`: VLANs permitidas por puerto a partir de `vlan port eth_* vlan A,B,C`.
    - `native_vlan`: VLAN nativa en modos híbridos a partir de `vlan port eth_* mode hybrid def-vlan X`.
    - `wan_vlan_id`: VLAN WAN principal priorizando `vlan-filter iphost ... vid X` y usando `vlan_id` de respaldo.
    - `vlan_filter_rules`: lista de reglas `{iphost_index, priority, vlan_id}` para `vlan-filter iphost ...`.
    - `flows`: lista de flujos `{id, priority, vlan_id, gemport_id, mode}` extraídos de `flow`/`gemport`.
  - Implementadas funciones auxiliares para calcular estos campos sin impactar la API externa ni el modelo de BD:
    - `_port_mode`, `_vlan_filter_rules`, `_flows_and_service_vlans`, `_allowed_vlans_and_native_vlan`.

- Reglas de clasificación de modo ONU (compatibles con históricos):
  - Ajustado `_parse_block` para aplicar las reglas oficiales de la Fase P2 sin introducir nuevos `service_mode_code`:
    - `transparent_special` cuando `vlan_mode == "transparent"`.
    - `router_iphost` cuando hay `iphost`, `vlan-filter` y `dhcp_source == "from-onu"`.
    - `bridge_tag_internet` cuando **no** hay `iphost`, hay `veip` y `dhcp_source == "from-internet"`, independientemente de si el puerto está en `tag`, `hybrid` o `trunk`.
    - `unknown` cuando ningún patrón aplica.
  - `mode_simple` se deriva directamente de `mode_code` (`router`, `bridge`, `transparent`, `unknown`), garantizando que no existan modos simples adicionales.

- Casos reales cubiertos por tests unitarios:
  - Actualizado `tests/test_zte_onu_management_mode_parser.py` para añadir casos estructurados basados en bloques reales de auditoría:
    - **Bridge Hybrid – Nodo Matilde** (`gpon-onu_1/2/10:111`):
      - `mode_simple = "bridge"`, `mode_code = "bridge_tag_internet"`.
      - `port_mode = "hybrid"`, `native_vlan = 700`, `allowed_vlans = [21, 200]`.
      - `service_vlans = [21, 200, 700]`, `dhcp_source = "from-internet"`, `has_veip = True`, `has_iphost = False`.
    - **Bridge Trunk – Centro de Salud** (`gpon-onu_1/2/13:4`):
      - `mode_simple = "bridge"`, `mode_code = "bridge_tag_internet"`.
      - `port_mode = "trunk"`, `allowed_vlans = [700, 735, 835]`.
      - `service_vlans = [200, 700, 735, 835]` (VLAN 200 detectada en flows), `dhcp_source = "from-internet"`.
    - **Router con VLAN distinta a 200** (`gpon-onu_1/2/5:29`):
      - `mode_simple = "router"`, `mode_code = "router_iphost"`.
      - `wan_vlan_id = 602` (desde `vlan-filter iphost 1 ... vid 602`).
      - `service_vlans = [602, 605]`, `has_iphost = True`, `has_veip = True`, `has_vlan_filter = True`, `dhcp_source = "from-onu"`.
    - **Bridge Trunk con loop-detect** (`gpon-onu_1/2/20:7`):
      - `mode_simple = "bridge"`, `mode_code = "bridge_tag_internet"`.
      - `port_mode = "trunk"`, `loop_detect_enabled = True`, `dhcp_source = "from-internet"`.
  - Confirmado que los tests históricos siguen pasando y que los nuevos casos refuerzan las reglas de clasificación sin cambiar `SERVICE_MODE_DEFINITIONS`.

- Bug `description zone_Lagunas_authd_YYYYMMDD`:
  - Añadidos tests en `tests/test_zte_onu_description_parser.py` para garantizar que:
    - `description zone_Lagunas_authd_20260225` y `$$$$zone_Lagunas_authd_20260225` producen `zone_name = "Lagunas"` y `auth_date = 2026-02-25`.
    - Esto se logra únicamente mediante ajustes al parser de descripción ya existente (sin tocar el modelo de datos), asegurando compatibilidad con descripciones mínimas de auditoría.

- TODO / AI context y verificación:
  - Actualizado `ai-context/05_TODO.md` en la sección "Modelo ONU y service_mode_code" para marcar como completadas:
    - La implementación del parser estructurado `pon-onu-mng` alineado con `EFO_NORMALIZACION_MODELO_ONU`.
    - La integración de la normalización `service_mode_code` en la importación inicial, manteniendo `unknown` para casos no clasificables pero persisitiendo `service_mode_code` cuando el parser sí clasifica.
  - Ejecutado `python -m compileall backend/app` sin errores.
  - Ejecutado `pytest tests/test_zte_onu_management_mode_parser.py tests/test_zte_onu_description_parser.py -q`; 16/16 tests pasando, confirmando que el parser extendido y los nuevos casos de auditoría son estables.

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

## 2026-06-23 — Fase P3: Ficha Operacional ONU (solo lectura)

- Backend:
  - Extendido `OnuBehaviorRead` en `backend/app/schemas/entities.py` para alinearlo con las EFO de Modelo Operacional ONU y Normalización:
    - Nuevos campos expuestos en el bloque `behavior` (solo lectura, no persistente):
      - Identidad de modo: `service_mode_code`, `mode_simple` (`router`/`bridge`/`transparent`/`unknown`), `mode_label` (Router/Bridge/Transparente/Desconocido).
      - Plantilla: `template_name`, `mode_code`.
      - WAN y perfiles: `vlan_id`, `vlan_name`, `speed_profile_up`, `speed_profile_down`, `speed_profile_code`.
      - Comportamiento operativo: `dhcp_source`, `use_iphost`, `use_veip`, `use_vlan_filter`, `use_loop_detect`, `disable_wifi`.
      - Calidad documental: `data_quality_status`, `data_quality_missing_fields`.
      - Advertencias suaves: `warnings` (por ejemplo, ausencia de plantilla).
  - Reescrito `GET /onus/{onu_id}` en `backend/app/api/routes/onus.py` para construir el bloque `behavior` de forma puramente de lectura, sin tocar provisioning ni Telnet:
    - Mapeo explícito `service_mode_code → mode_simple / mode_label`:
      - `router_iphost` → `router` / `Router`.
      - `bridge_tag_internet` → `bridge` / `Bridge`.
      - `transparent_special` → `transparent` / `Transparente`.
      - `None`/`""`/`"unknown"` → `unknown` / `Desconocido/importado`.
    - Resolución opcional de plantilla `OnuServiceModeTemplate` por (`olt_id`, `mode_code`) sólo cuando existe y está activa:
      - Si la plantilla está presente → se rellenan `template_name`, `mode_code`, flags (`dhcp_source`, `use_iphost`, `use_veip`, `use_vlan_filter`, `use_loop_detect`, `disable_wifi`).
      - Si **no** existe plantilla para el `service_mode_code` informado → se degrada `mode_simple` a `unknown`, `mode_label` a `Desconocido/importado` y se añade un aviso suave en `warnings` sin lanzar errores.
    - Enriquecimiento WAN/perfiles sin consultas adicionales a la OLT:
      - `Vlan`: búsqueda por (`Vlan.olt_id`, `Vlan.vlan_id`) para exponer `vlan_name` cuando existe.
      - `SpeedProfile`: búsqueda por (`SpeedProfile.olt_id`, `upstream_profile_name`, `downstream_profile_name`) para exponer `speed_profile_code` cuando coincide con un perfil combinado.
    - Calidad documental:
      - Reconstrucción de `data_quality_missing_fields` como lista de strings a partir de `Onu.data_quality_missing_fields` (JSON), manteniendo `data_quality_status`.
  - Confirmado que todo el cálculo se hace en base de datos local y DTOs; no se añaden comandos Telnet, migraciones ni modificaciones de datos.
- Tests backend:
  - Añadido `tests/test_onu_behavior_api.py` con una base SQLite en memoria que comprueba los casos mínimos requeridos:
    - ONU `router_iphost` con plantilla:
      - `mode_simple = "router"`, `mode_label = "Router"`, `template_name = "Router IPHost"`, `dhcp_source = "from-internet"`, `use_iphost = True`, flags VEIP/VLAN filter/Loop detect/WiFi coherentes, `data_quality_status = "complete"`, `warnings = []`.
    - ONU `bridge_tag_internet` con plantilla:
      - `mode_simple = "bridge"`, `mode_label = "Bridge"`, `template_name = "Bridge Internet"`, `use_iphost = False`, `dhcp_source = "none"`.
    - ONU `transparent_special` con plantilla:
      - `mode_simple = "transparent"`, `mode_label = "Transparente"`, `template_name = "Transparent Special"`.
    - ONU sin `service_mode_code`:
      - `service_mode_code is None`, `mode_simple = "unknown"`, `mode_label = "Desconocido/importado"`, sin plantilla ni warnings.
    - ONU con `service_mode_code` pero sin plantilla:
      - `service_mode_code = "router_iphost"`, `mode_simple = "unknown"`, `mode_label = "Desconocido/importado"`, `template_name is None`, y `warnings` contiene el aviso de plantilla ausente.
- Frontend:
  - Actualizado el tipo `Onu` en `frontend/src/types/index.ts` para reflejar el nuevo contrato de `behavior`, incluyendo:
    - `service_mode_code`, `mode_simple`, `mode_label`, `template_name`, `mode_code`, `vlan_id`, `vlan_name`, `speed_profile_up/down`, `speed_profile_code`, `dhcp_source`, `use_iphost`, `use_veip`, `use_vlan_filter`, `use_loop_detect`, `disable_wifi`, `data_quality_status`, `data_quality_missing_fields`, `warnings`.
  - Ajustada la ficha de detalle `frontend/src/app/onus/[id]/page.tsx`:
    - Sección "Comportamiento ONU" permanece en modo solo lectura, sin controles de edición ni acciones que disparen Telnet.
    - Cuando `behavior` es `null` o `mode_simple === "unknown"`:
      - Se muestra el aviso textual requerido: "ONU importada sin clasificación operacional. Requiere saneamiento manual.".
    - Layout de la sección actualizado para mostrar exactamente los campos pedidos:
      - "Modo ONU" → `behavior.mode_label`.
      - "Plantilla" → `behavior.template_name ?? behavior.mode_code ?? onu.service_mode_code ?? "-"`.
      - "VLAN WAN" → `vlan_id` + nombre si existe.
      - "Perfil subida" / "Perfil bajada" → perfiles UP/DOWN desde `behavior` o, en su defecto, desde `onu`.
      - "DHCP Source", "IPHost", "VEIP", "VLAN Filter", "Loop Detect", "WiFi deshabilitado".
      - "Estado de calidad documental" → `behavior.data_quality_status` o `onu.description_parse_status` como respaldo.
- Verificación técnica:
  - Ejecutado `python -m compileall backend/app` sin errores después de los cambios en schemas y rutas.
  - Ejecutado `DATABASE_URL=sqlite+pysqlite:///:memory: pytest`; 125 tests pasando, incluyendo la nueva suite `tests/test_onu_behavior_api.py`.
  - Ejecutado `cd frontend && npm run build`; build de Next.js/TypeScript completada correctamente, confirmando que el tipo `Onu.behavior` y la ficha `/onus/[id]` son coherentes.


## 2026-06-21 — Ajustes EFO Calidad de Datos y Gobierno OLT (documental)

- Actualizada `docs/EFO_CALIDAD_DATOS_Y_GOBIERNO_OLT.md` para dejar explícito que:
  - No se permite crear una `Onu` real con información incompleta.
  - El trabajo parcial de provisión debe guardarse exclusivamente como `ProvisioningPlan` en estado `draft`; el concepto de borrador aplica al plan, no a la entidad `Onu`.
  - La eliminación de una OLT en estado `preview_created` debe incluir snapshots, import jobs, previews, logs temporales y cualquier artefacto de importación asociado, con el objetivo de evitar residuos operativos.
  - `ProvisioningTemplate` puede ser global sólo si no contiene referencias técnicas específicas de una OLT (VLAN IDs, Zone IDs, Nap/NapPort IDs, Profile/SpeedProfile IDs u otras FKs por OLT) y se limita a estructura CLI genérica + placeholders.
- Añadida en `ai-context/05_TODO.md` la sección "Data Quality Roadmap (EFO – Fase A)" para preparar la implementación gradual de `data_quality_status`, evaluador de calidad documental y métricas de dashboard sin modificar todavía backend ni frontend.

## 2026-06-24 — Regla canónica NAP/ODN (documental)

- Origen: auditoría operacional de ONUs en `OLT-PCM-ZTE-01` utilizando el inventario histórico de SmartOLT.
- Hallazgo: se confirmó que los prefijos `NAP` y `ODN` forman parte de la identidad canónica de planta externa y **no** son intercambiables:
  - `NAP D01` y `ODN D01` son entidades distintas que coexisten en la misma OLT.
  - Lo mismo aplica a `NAP D2`/`ODN D2`, `NAP D3`/`ODN D3`, `NAP D4`/`ODN D4`, `NAP F7`/`ODN F7`.
- Documentación actualizada (sin cambios de código, esquema ni datos):
  - `docs/EFO_CALIDAD_DATOS_Y_GOBIERNO_OLT.md`: nueva sección **"Identidad canónica de NAPs"** reforzando que el prefijo (`NAP`/`ODN`/`ODB`) forma parte de la clave, los pares NAP/ODN mencionados son entidades distintas dentro de la misma OLT y no se permite normalización que elimine prefijos ni colapse ambos tipos bajo `D01`/`D2`/`F7`, etc.
  - `docs/EFO_NORMALIZACION_MODELO_ONU.md`: nueva sección **"2.bis. Normalización de nombres de NAP y ODN"** que:
    - Define que la identidad canónica incluye siempre el prefijo.
    - Permite sólo normalizaciones de formato (espacios/guiones/subrayados, mayúsculas/minúsculas) manteniendo el prefijo.
    - Prohíbe expresamente transformaciones `NAP D4 → ODN D4`, `ODN D4 → NAP D4` o `NAP/ODN D4 → D4` durante importación, auditoría o saneamiento.
  - `AI_HANDOFF.md`: sección **Last Known State** extendida con una observación explícita sobre la regla canónica NAP/ODN para futuros handoffs de IA.
  - `ai-context/00_PROJECT_CONTEXT.md`: ámbito de "Internal FTTH catalogs" actualizado para indicar que la identidad canónica de NAP/ODN/ODB conserva siempre su prefijo (ej. `NAP D01` ≠ `ODN D01`).
  - `ai-context/05_TODO.md`: añadida subsección **"Observaciones recientes sobre NAP/ODN (documental)"** con un TODO abierto para incorporar esta regla en futuras fases de catálogo NAP por OLT y saneamiento operacional.
- Impacto futuro previsto:
  - La regla será insumo directo para P3.7 (catálogo NAP por OLT y saneamiento operacional), evitando colisiones entre NAP/ODN al diseñar claves, parsers y tooling de normalización.
  - No se han realizado cambios en código de parsers, endpoints, migraciones ni datos; el trabajo de esta fecha es exclusivamente documental.

## 2026-06-24 — EFO Modelo Territorial FTTH

- Añadido `docs/EFO_MODELO_TERRITORIAL_FTTH.md` como especificación formal del **modelo territorial FTTH por OLT**, definiendo:
  - Jerarquía canónica `OLT → Zona → NAP/ODN/ODB → NapPort → ONU` sin cruces entre OLTs.
  - Alcance territorial (Zones, NAPs, ODN, ODB, NapPorts, relaciones ONU ↔ Zone/Nap/NapPort y ProvisioningPlan ↔ Zone/Nap), excluyendo catálogos técnicos ya saneados por OLT (VLANs, OnuTypes, SpeedProfiles, ProfileCatalogs, PonPorts, OnuServiceModeTemplate).
  - Principios obligatorios: todo objeto territorial pertenece a una OLT; no existen Zones/NAPs/NapPorts globales; ONUs y ProvisioningPlans nunca pueden apuntar a territoriales de otra OLT; si falta el objeto territorial para esa OLT debe quedar como `NULL` o candidato pendiente, nunca reutilizar otro `olt_id`.
  - Identidad canónica de NAP/ODN/ODB: `prefix/type` obligatorio (`NAP`/`ODN`/`ODB`) + `code/suffix` normalizado (`D01`, `D2`, `H5`, `C4 A`, etc.), con `canonical_name = prefix + code_normalizado`, `display_name` para texto heredado y `description/notes` para conservar documentación larga, prohibiendo transformaciones como `NAP D4 → D4`, `ODN D4 → D4`, `NAP D4 → ODN D4` o `ODN D4 → NAP D4`.
  - Modelo conceptual recomendado para `Zone`, `Nap` (unificando NAP/ODN/ODB con `type/prefix`) y `NapPort`, marcado explícitamente como diseño conceptual sin crear migraciones ni tocar BD.
  - Estado actual P3.6.x documentado: Zones/NAPs/NapPorts sólo existen para `OLT-LAB-ZTE-01`; `OLT-PCM-ZTE-01` carece de catálogo territorial propio; 454 ONUs PCM con `zone_id` cruzado, 169 ONUs PCM con `nap_id` cruzado y 27 `ProvisioningPlan` PCM con `zone_id`/`nap_id` cruzados, mientras el resto de catálogos técnicos por OLT está sano.
  - Flujo P4 de reconstrucción territorial (P4.1 Zones por OLT, P4.2 NAP/ODN/ODB por OLT, P4.3 NapPorts, P4.4 preview de reasignación ONU/ProvisioningPlan, P4.5 apply controlado) con énfasis en previews, niveles de confianza, revisión humana y auditoría antes/después.
  - Reglas de confianza (`alta`/`media`/`baja`/`bloqueado`), reglas para futuras importaciones (lookups territoriales siempre filtrados por `olt_id`, creación de candidatos pendientes o `NULL + needs_review` en lugar de reutilizar catálogos de otra OLT) y tests conceptuales futuros para asegurar invariantes territoriales y preservación de prefijos `NAP`/`ODN`/`ODB`.
- Actualizado `AI_HANDOFF.md` para incluir `docs/EFO_MODELO_TERRITORIAL_FTTH.md` en la sección **Read First** y referenciarlo como línea documental clave sobre modelo territorial FTTH y plan P4 de reconstrucción PCM/LAB.
- Actualizado `ai-context/05_TODO.md` añadiendo la sección **"Modelo Territorial FTTH / P4"** con tareas planificadas para P4.1–P4.5 (reconstrucción conceptual de Zones/NAP/ODN/ODB/NapPorts por OLT, matriz ONU actual vs propuesta y diseño de apply controlado), sin cambios de código, esquema ni datos.
 
## 2026-06-24 — EFO Arquitectura Operativa Admin OLT TOI

- Documentación:
  - Añadido `docs/EFO_ARQUITECTURA_OPERATIVA_ADMIN_OLT_TOI.md` como especificación formal de la **arquitectura operativa definitiva** de Admin OLT TOI, definiendo:
    - Filosofía del sistema como **Sistema Operativo de OLTs administradas**, separando claramente inventario aprobado (Desired State), estado observado (Observed State), snapshots históricos e inventario oficial.
    - Ciclo de vida conceptual de una OLT (`REGISTERED`, `CONNECTED`, `SNAPSHOTTED`, `PREVIEW_READY`, `UNDER_REVIEW`, `ADOPTED`, `SYNCHRONIZED`, `SUSPENDED`, `RETIRED`) sin modificar el modelo actual de BD, alineado con los estados existentes de import (`draft`, `connection_tested`, `preview_created`, `confirmed`).
    - Capas operativas: Snapshot → Parser → Preview → Inventario Deseado → Observed State → Drift → Provisioning → Auditoría, consolidando flujos ya existentes de snapshot/import, previews territoriales y provisión controlada bajo un mismo modelo.
    - Definición detallada de Desired State (qué representa, qué objetos contiene, cómo se mantiene y qué puede modificarlo) y Observed State (qué es, cómo se obtiene, qué representa y qué no representa).
    - Tratamiento formal de snapshots (running-config, startup-config, comandos adicionales, periodicidad, inmutabilidad, versionado) como base de Observed State e insumo de recuperación.
    - Alcance del inventario oficial, enumerando entidades técnicas, territoriales y de servicio (OLT, PON, ONU, VLAN, perfiles, OnuType, ServiceMode, Zone, Nap, NapPort, ProvisioningPlan, etc.) en coherencia con `EFO_GOBIERNO_DE_CATALOGOS` y `EFO_MODELO_TERRITORIAL_FTTH`.
    - Flujo estándar de sincronización Inventario ↔ OLT (Snapshot → Comparación → Preview → Validación → Aprobación → Inventario/Provisioning) prohibiendo que el estado observado sobreescriba inventario directamente.
    - Modelo de Drift Detection con categorías `SYNC`, `CONFIG_MISMATCH`, `MISSING_IN_OLT`, `MISSING_IN_SYSTEM`, `EXTRA_OBJECT`, `CONFLICT`, `UNMANAGED_OBJECT` como base conceptual para futuras vistas y planes de saneamiento.
    - Estrategias de recuperación (reemplazo de OLT, pérdida de startup-config, running-config no guardado, recuperación completa/parcial y reconstrucción desde inventario) tratadas como provisión controlada con snapshots y auditoría.
    - Rol del Provisioning: altas/bajas ONU, cambios de VLAN/profile/modo/territorio y su pipeline obligatorio **Inventario → OLT → Snapshot → Validación**.
    - Rol de Auditoría (quién/cuándo/qué cambió/snapshot origen/destino/CLI generado/resultado) como capa transversal a todas las operaciones.
    - Criterios de compatibilidad multivendor (ZTE, VSOL, Huawei, FiberHome) basados en un modelo lógico común de Desired/Observed State y drift, desacoplado de drivers/parsers específicos.
    - Papel de la IA como asistente (clasificación, reconstrucción, auditoría, anomalías, generación de CLI) bajo la restricción explícita de no ejecutar cambios ni modificar inventario sin aprobación humana.
    - Lista extensa de invariantes operativas (no modificar snapshots, no editar inventario crítico directamente, scoping estricto por OLT, no reutilizar catálogos territoriales entre OLTs, preservar prefijos NAP/ODN/ODB, preview antes de apply, toda ejecución de CLI ligada a `ProvisioningPlan`, etc.).
    - Roadmap **P6.x** para completar el ciclo operativo (P6.1 Desired/Observed/Drift, P6.2 adopción de OLTs, P6.3 sincronización asistida, P6.4 provisión sobre inventario oficial, P6.5 recuperación, P6.6 multivendor operativo, P6.7 integración OSS FTTH).
- AI handoff y contexto:
  - Actualizado `AI_HANDOFF.md` para incluir `docs/EFO_ARQUITECTURA_OPERATIVA_ADMIN_OLT_TOI.md` en la sección **Read First** como lectura obligatoria para trabajos arquitectónicos y operativos sobre OLTs.
  - Actualizado `ai-context/05_TODO.md` añadiendo la sección **"P6 – Arquitectura Operativa y Ciclo de Vida OLT"**, que organiza las próximas fases P6.1–P6.7 alrededor del nuevo modelo de Desired/Observed State, drift, adopción de OLTs, sincronización asistida, recuperación y multivendor operativo, sin introducir por ahora cambios de código, esquema ni endpoints.
- Verificación:
  - Trabajo limitado a documentación (`docs/EFO_ARQUITECTURA_OPERATIVA_ADMIN_OLT_TOI.md`, `AI_HANDOFF.md`, `ai-context/05_TODO.md`).
  - No se modificaron modelos, migraciones, endpoints backend ni frontend; no se ejecutaron tests ni comandos Telnet.

## 2026-06-24 — EFO Observabilidad y Conocimiento Operativo

- Documentación:
  - Añadido `docs/EFO_OBSERVABILIDAD_Y_CONOCIMIENTO_OPERATIVO.md` como especificación formal de la **capa de Observabilidad y Conocimiento Operativo** de Admin OLT TOI, definiendo:
    - Objetivo de la capa para mostrar al personal técnico el estado real y el histórico operativo de OLTs, PON ports, uplinks, ONUs, NAP/ODN/ODB y Zonas, sin modificar inventario ni Desired State automáticamente.
    - Separación en cinco capas lógicas: **Inventory**, **Configuration**, **Operations**, **Knowledge** y **Automation**, aclarando que Inventory no cambia automáticamente, Operations se actualiza continuamente con datos observados, Knowledge se construye a partir de históricos y Automation sólo propone acciones sin ejecutarlas sin aprobación.
    - Modelo de observabilidad por dominio:
      - **OLT**: estado online/offline, uptime, último reinicio y causa probable, CPU/memoria/temperatura, fuente de energía, alarmas activas, eventos recientes, estado de tarjetas/slots, estado de PON ports y uplinks, tráfico por uplink, histórico de tráfico y disponibilidad.
      - **PON**: estado del puerto, ONUs registradas y online/offline, ocupación, potencia TX/RX agregada, errores, eventos asociados, histórico de cambios, saturación/sobreocupación y alertas por caída masiva de ONUs.
      - **Uplinks**: estado físico, velocidad negociada, tráfico actual e histórico, errores/drops, flaps, utilización pico, disponibilidad y alertas por saturación/caída.
      - **ONU**: estado online/offline, uptime, última caída/reconexión, RX/TX actuales e históricos, distancia/atenuación estimada, cambios de potencia, alarmas (dying gasp, LOS), degradación óptica, flapping, modo router/bridge observado, VLAN/perfil observados y comparación contra Desired Configuration (drift).
    - Definición de **históricos** a mantener (power/status/uptime/traffic/alarm/event/config snapshot/drift history) y sus usos para diagnóstico, auditoría, tendencias, recuperación y planificación.
    - Catálogo de **alertas mínimas** para OLT (offline, reboot, running/startup divergente, alta CPU/memoria/temperatura, uplink caído, tráfico saturado), PON (caída masiva de ONUs, puerto down, ocupación crítica), ONU (offline, flapping, RX bajo, degradación progresiva, dying gasp, pérdida de potencia, diferencia contra configuración deseada) y NAP/Zona (múltiples ONUs degradadas, múltiples caídas en la misma zona, patrones de falla recurrente).
    - Análisis de **tendencias** (degradación óptica por ONU/NAP/Zona, crecimiento de ocupación PON y tráfico uplink, frecuencia de reinicios OLT y de caídas por zona, clientes críticos afectados) como base para planificación y priorización.
    - Modelo de **Health Scores** explicables para OLT, PON, Uplink, ONU, NAP/ODN/ODB y Zona, con factores ejemplo (estado actual, RX/TX, tendencias ópticas, eventos, flapping, alarmas, drift, disponibilidad, uptime, uso de recursos, estado de uplinks/PONs).
    - Definición de la **Knowledge Layer** como capa que transforma datos operativos e históricos en conocimiento estructurado (ONU con degradación gradual, NAP con múltiples incidencias, zonas con cortes recurrentes, PON próximo a saturación, uplink con picos frecuentes, OLT con reinicios repetidos) sin ejecutar cambios.
    - Catálogo de **recomendaciones asistidas** posibles (revisar empalme/conector/NAP/energía de zona, planificar expansión PON, aumentar uplink, revisar configuración ONU, guardar running-config a startup-config, ejecutar snapshot de verificación, revisar drift), dejando claro que la IA o automatización sólo recomienda y no ejecuta cambios.
    - Fuentes de datos de observabilidad (Telnet/SSH CLI read-only, SNMP, Zabbix, tareas Celery, ConfigSnapshot, eventos internos, resultados de provisioning, notas manuales) tratadas exclusivamente como insumos de observación.
    - Diseño de **fichas operativas** para OLT, ONU y NAP/Zona con secciones recomendadas (identidad, estado actual, inventario vs configuración observada, históricos, eventos, alarmas, drift, recomendaciones).
    - Invariantes específicas de observabilidad (observabilidad no modifica inventario, métricas operativas no cambian Desired State, alertas no ejecutan provisioning, IA no ejecuta cambios, todo cambio requiere flujo aprobado, históricos no se sobrescriben, eventos trazables, drift respaldado por evidencia, Health Scores explicables, datos operativos no cambian catálogos).
    - Roadmap **P7.x** para Observabilidad y Conocimiento Operativo (P7.1 OLT, P7.2 PON, P7.3 ONU, P7.4 Históricos ópticos, P7.5 Alertas, P7.6 Health Scores, P7.7 Knowledge Layer, P7.8 Recomendaciones asistidas, P7.9 Integración Zabbix/SNMP, P7.10 Dashboard operativo), marcado como guía conceptual sin implementación inmediata.
- AI handoff y contexto:
  - Actualizado `AI_HANDOFF.md` para incluir `docs/EFO_OBSERVABILIDAD_Y_CONOCIMIENTO_OPERATIVO.md` en la sección **Read First** como lectura obligatoria para trabajos relacionados con observabilidad, métricas operativas, knowledge y recomendaciones asistidas.
  - Actualizado `ai-context/05_TODO.md` añadiendo la sección **"P7 – Observabilidad y Conocimiento Operativo"** con tareas planificadas P7.1–P7.10 alineadas con la nueva EFO, manteniendo explícito que se trata de diseño conceptual sin cambios de código, esquemas ni endpoints en esta fase.
- Verificación:
  - Trabajo limitado a documentación (`docs/EFO_OBSERVABILIDAD_Y_CONOCIMIENTO_OPERATIVO.md`, `AI_HANDOFF.md`, `ai-context/05_TODO.md`).
  - No se modificaron modelos, migraciones, endpoints backend ni frontend; no se ejecutaron tests ni comandos Telnet; no se accedió a OLTs reales.

## 2026-06-24 — EFO Gobierno de Catálogos

- Añadido `docs/EFO_GOBIERNO_DE_CATALOGOS.md` como documento arquitectónico de referencia permanente para el gobierno de catálogos en Admin OLT TOI, definiendo:
  - Objetivo y principios fundamentales (un dato tiene un único propietario, un catálogo pertenece a un único dominio, ningún objeto pertenece simultáneamente a varias OLTs, los datos operativos no reemplazan inventario, importaciones descubren información, confirmación consolida, cambios auditables, automatización reversible, preview antes de apply y primacía de calidad de datos sobre automatización).
  - Clasificación oficial de catálogos en cuatro familias: **Globales** (vendors, modelos ONU globales, tipos de splitter/conectores, tecnologías), **Técnicos por OLT** (VLANs, GponProfiles, SpeedProfiles, ProfileCatalogs, OnuTypes, PonPorts, OltUplinks, OnuServiceModeTemplates, ProvisioningTemplates), **Territoriales** (Zones, NAP/ODN/ODB, NapPorts) y **Operativos** (OnuStatus, OnuBehavior, power history, alarmas, eventos, AUTHD, DataQuality, ConfigSnapshot, ImportJob, metadatos de snapshot).
  - Propiedad y gobierno de cada catálogo mediante una tabla conceptual (dominio, propietario, global/OLT, versionado, historial, autoimport, preview/apply, observaciones), alineada con las EFO previas de calidad de datos, modelo ONU y modelo territorial.
  - Ciclo de vida por familia (Global: crear/actualizar/obsoleto/eliminar; Técnico: importar/validar/versionar/activar/reemplazar; Territorial: descubrir/revisar/preview/confirmar/operar/expandir; Operativo: generar/actualizar/historial/caducar/eliminar).
  - Reglas de aislamiento (global sin `olt_id` ni FKs a catálogos por OLT; técnico y territorial siempre con `olt_id`; territoriales nunca compartidos ni reutilizados; datos operativos ligados a ONU/OLT/Snapshot/Evento/ImportJob sin cambiar inventario).
  - Reglas de importación y eliminación (qué puede crearse automáticamente, qué requiere preview, qué requiere revisión humana, qué nunca debe crearse automáticamente; prohibiciones como eliminar Zone con NAPs, NAP con ONUs, VLAN/SpeedProfile usados, Snapshot confirmado o catálogos territoriales históricos).
  - Reglas de evolución al agregar nuevas OLTs (crear estructuras vacías, nunca copiar Zones/NAPs/NapPorts, importar catálogos técnicos desde snapshots y reconstruir territoriales vía preview) y hacia un OSS FTTH multi-vendor/multi-ciudad.
  - Matriz de gobierno adicional marcando para cada catálogo si es global/OLT/operativo, versionado, con historial, si requiere preview/apply, si es autoimportable, reconstruible y auditable.
  - Invariantes arquitectónicas obligatorias (igualdades de `olt_id` entre ONU/Zone/Nap/NapPort/ProvisioningPlan, resolución siempre filtrando por `olt_id`, no reutilizar objetos territoriales, snapshots antes de importar, preview antes de apply, parser determinista, preservación de prefijos NAP/ODN/ODB y que datos operativos no sobreescriben inventario).
  - Principios OSS FTTH y roadmap arquitectónico asociado: P4 (Modelo Territorial FTTH), P5 (GIS), P6 (Inventario de Planta Externa), P7 (CRM/ERP), P8 (OSS FTTH completo).
- Actualizado `AI_HANDOFF.md` para incluir `docs/EFO_GOBIERNO_DE_CATALOGOS.md` en **Read First** y referenciarlo explícitamente como documento de gobierno de catálogos, clasificación global/técnico/territorial/operativo, invariantes arquitectónicas y roadmap OSS FTTH.
- Actualizado `ai-context/05_TODO.md` añadiendo la sección **"Arquitectura Base Finalizada"** con el ítem completado **EFO Gobierno de Catálogos**, marcando `docs/EFO_GOBIERNO_DE_CATALOGOS.md` como constitución arquitectónica para todo trabajo futuro sobre catálogos.

## 2026-06-24 — P4.2 Infraestructura del Territorial Reconstruction Engine (TRE)

- Añadido `backend/app/services/territorial_reconstruction_engine.py` como núcleo genérico **en memoria** para reconstrucción territorial FTTH (P4.x) sin modificar la BD ni exponer endpoints nuevos:
  - Definidos DTOs internos reutilizables independientes de SQLAlchemy/BD:
    - `TerritorialCandidateState`: estados comunes para candidatos territoriales (`NEW`, `EXISTS`, `REVIEW`, `BLOCKED`, `MERGE`).
    - `TerritorialEvidence`: contenedor de evidencias (`source`, `description`, `weight`, `metadata`) usado para cálculo de confianza.
    - `TerritorialCandidate[TId, TRaw]`: candidato territorial genérico con `candidate_id`, clave lógica `key`, `state`, `evidence_score` (0–100), lista de evidencias, conflictos y `payload` específico de dominio.
  - Definidos contratos/protocolos para separar responsabilidades:
    - `ConfidenceEvaluator[TRaw]`: mapea reglas de EFO a `(evidence_score, TerritorialCandidateState)` sin tocar BD.
    - `ConflictDetector[TId, TRaw]`: anota conflictos en candidatos (colisiones NAP/ODN/ODB, cruces entre OLTs, solapamientos de NapPorts).
    - `ReportGenerator[TId, TRaw]`: construye resúmenes y vistas detalladas a partir de candidatos para ser proyectados luego a DTOs Pydantic/APIs de solo lectura.
  - Implementado `TerritorialReconstructionEngine[TId, TRaw, TReport]` como orquestador genérico para P4.x:
    - `build_candidates(items)`: recibe tuplas `(existing_id, key, raw, evidences)` y devuelve `TerritorialCandidate` con `evidence_score` clipeado a 0–100 y estado validado, opcionalmente llamando a `ConflictDetector`.
    - `generate_report(candidates)`: delega en `ReportGenerator` para producir estructuras de resumen/detalle serializables.
  - El módulo documenta explícitamente que:
    - No ejecuta `INSERT/UPDATE/DELETE` ni `commit` y no invoca Telnet ni parsers; sólo consume evidencias ya calculadas (por ejemplo `parsed_nap_name`, `parsed_odn`, `odb_name`).
    - Está diseñado para reutilizarse en P4.2 (NAP/ODN/ODB), P4.3 (NapPorts) y P4.4 (reasignación ONU/ProvisioningPlan), evitando duplicar lógica de scoring de confianza o detección de conflictos.
- Actualizado `AI_HANDOFF.md` para documentar el TRE como punto central de orquestación territorial en `Read First`, incluyendo un resumen de sus DTOs/contratos y el carácter exclusivamente de preview.
- Actualizado `ai-context/05_TODO.md` en la sección **"Modelo Territorial FTTH / P4"** para exigir que P4.2 (NAP/ODN/ODB) y P4.3 (NapPorts) reutilicen el TRE (`TerritorialCandidate`, `TerritorialEvidence`, estados `NEW/EXISTS/REVIEW/BLOCKED/MERGE`) sin modificar la BD, consolidando el motor como infraestructura oficial para P4.x.

## 2026-06-24 — P4.2 Infraestructura de Identidad Territorial

- Añadido `backend/app/services/territorial_identity.py` como capa genérica de **identidad territorial** que centraliza la normalización de nombres NAP/ODN/ODB/NapPort y zonas sin tocar BD:
  - Definido `TerritorialObjectType` con los tipos lógicos `ZONE`, `NAP`, `ODN`, `ODB`, `NAP_PORT`.
  - Definido DTO inmutable `TerritorialIdentity` con:
    - `olt_id`, `zone_name`, `object_type`.
    - `code`, `canonical_name`, `display_name`, `notes`.
    - `identity_score` (0–100) y `raw_value`.
    - `reasons: list[str]` para explicar decisiones (`explicit_prefix`, `normalized_separator`, `notes_extracted`, `default_type_applied`, `missing_prefix`, `invalid_format`, `empty_value`).
  - Implementado `TerritorialNormalizer` con métodos:
    - `normalize_zone(raw, olt_id)` → `TerritorialIdentity | None` que descarta valores vacíos/`SIN_ZONA` y normaliza espacios.
    - `normalize_territorial_object(raw, olt_id, zone_name=None, default_type=None)` → `TerritorialIdentity | None` que:
      - Preserva prefijos `NAP`/`ODN`/`ODB` y aplica normalización permitida (`ODN C4_A` → `ODN C4 A`, `ODN H5------COOPERATIVA` → `ODN H5` con `notes="COOPERATIVA"`).
      - Respeta las prohibiciones documentadas (no colapsar `NAP D4`/`ODN D4` bajo `D4`, no cambiar NAP↔ODN).
      - Permite inferencia manual vía `default_type` para valores sin prefijo (`"D4"` + `default_type=NAP` → `NAP D4` con `identity_score=75` y razón `default_type_applied`), devolviendo `None` si no hay `default_type`.
    - `normalize_nap_port(raw, olt_id, zone_name=None)` → `TerritorialIdentity | None` que extrae el primer número como código de puerto (`NAP_PORT {n}`) para uso futuro en P4.3.
- Añadido `tests/test_territorial_identity.py` con casos mínimos que verifican:
  - `"ODN H5------COOPERATIVA"` → `object_type=ODN`, `code="H5"`, `canonical_name="ODN H5"`, `notes="COOPERATIVA"`, `identity_score=90`, razones `explicit_prefix` y `notes_extracted`.
  - `"ODN C4_A"` → `canonical_name="ODN C4 A"`, `identity_score=100`, razón `normalized_separator`.
  - `"nap d4"` → `canonical_name="NAP D4"` con prefijo y código normalizados.
  - `"odb_ODN_H5------COOPERATIVA"` → identidad ODN H5 (prefijo ODN preferido) con notas `COOPERATIVA`.
  - `"D4"` sin `default_type` → `None`; con `default_type=NAP` → `canonical_name="NAP D4"`, `identity_score=75` y razón `default_type_applied`.
  - `"NAP D4"` y `"ODN D4"` producen identidades distintas (`object_type` y `canonical_name` diferentes).
  - Valores vacíos/`SIN_ZONA` devuelven `None` tanto en `normalize_territorial_object` como en `normalize_zone`.
- Actualizado `ai-context/05_TODO.md` en la sección **"Modelo Territorial FTTH / P4"** para marcar como completado el punto de "Introducir una capa reutilizable de identidad territorial" y vincularla con P4.2/P4.3 como infraestructura de normalización para el TRE.

## 2026-06-24 — P4.3 Preview de reconstrucción NAP/ODN/ODB por OLT

- Añadidos DTOs de sólo lectura en `backend/app/schemas/entities.py` para la preview NAP/ODN/ODB:
  - `NapReconstructionCatalogProposal`: entrada de catálogo consolidado por OLT/zona/tipo con `canonical_name`, `display_name`, `code`, `notes`, `identity_score`, `evidence_score`, `state`, `confidence`, `reasons`, `source_fields` y `supporting_onu_ids`.
  - `NapReconstructionOnuProposal`: fila ONU actual vs propuesta con contexto actual (`current_nap_id`, `current_nap_name`, `current_nap_olt_id`, `current_nap_olt_code`), fuentes (`parsed_nap_name`, `parsed_odn`, `odb_name`) y propuesta (`proposed_zone_name`, `proposed_object_type`, `proposed_canonical_name`, `proposed_olt_id`, `state`, `confidence`, `identity_score`, `evidence_score`, `reasons`).
  - `NapReconstructionOltSummary`: resumen agregado por OLT (`total_onus`, `existing_naps`, conteos de catálogo propuesto por estado y métricas ONU: `onus_with_nap_id`, `onus_with_cross_olt_nap`, `onus_without_nap_id`, `onus_reassignable`, `onus_blocked`).
  - `NapReconstructionPreview`: raíz de respuesta con `summaries`, `catalog_proposals` y `onus`.
- Añadido servicio de sólo lectura `NapReconstructionPreviewService` en `backend/app/services/nap_reconstruction_preview_service.py` que implementa el preview NAP/ODN/ODB por OLT sin modificar la BD ni añadir endpoints:
  - Carga `Olt`, `Zone`, `Nap`, `Onu` desde la BD (SELECT puros) y construye identidades territoriales mediante `TerritorialNormalizer` a partir de:
    - `Onu.parsed_odn`, `Onu.odb_name` (prioridad A, prefijo explícito ODN/ODB).
    - `Onu.parsed_nap_name` (prioridad B/C, prefijo explícito o, si no hay, `default_type=NAP` de forma conservadora).
  - Refuerza reglas EFO:
    - Prefijos `NAP`/`ODN`/`ODB` preservados en `canonical_name` (p.ej. `NAP D4` ≠ `ODN D4`).
    - Nunca reutiliza NAPs de otra OLT: cuando `Onu.nap_id` apunta a `Nap` de LAB, lo marca como `cross_olt_nap` y propone siempre candidatos para `olt_id` de la ONU.
  - Agrupa candidatos en `NapCandidatePayload` por `(olt_id, zone_name, object_type, canonical_name)` incluyendo:
    - `identity: TerritorialIdentity` (score y razones de normalización).
    - `existing_nap_id` cuando ya existe un Nap equivalente en esa OLT.
    - `supporting_onu_ids` y `source_fields` (`parsed_nap_name`, `parsed_odn`, `odb_name`).
  - Usa `TerritorialReconstructionEngine[int, NapCandidatePayload, Dict]` con `NapConfidenceEvaluator` para:
    - Calcular `evidence_score` agregando `identity_score` + número de ONUs + fuentes.
    - Producir estados `NEW` / `EXISTS` / `REVIEW` / `BLOCKED` según reglas mínimas:
      - `EXISTS` cuando hay `existing_nap_id` y score ≥ 75.
      - `REVIEW` cuando se aplicó `default_type` o score < 75.
      - `NEW` cuando score alto sin NAP existente.
      - `BLOCKED` cuando score 0.
    - Mapear `evidence_score` a etiquetas de confianza (`ALTA`/`MEDIA`/`BAJA`/`BLOQUEADO`).
  - Proyecta candidatos a `NapReconstructionCatalogProposal` y anota en `NapReconstructionOnuProposal` el estado final (`state`, `confidence`, `evidence_score`, `identity_score`).
  - Construye resúmenes `NapReconstructionOltSummary` por OLT sin escribir nada en BD.
- Añadido `tests/test_nap_reconstruction_preview_service.py` con casos mínimos que validan las reglas pedidas:
  - Caso A (ODN explícito): 2 ONUs PCM con `parsed_odn="ODN_H5------COOPERATIVA"` → candidato `ODN H5` para PCM con `state="NEW"`, `confidence="ALTA"`, `notes="COOPERATIVA"`, `exists_in_olt=False`.
  - Caso B (NAP sin prefijo): ONU con `parsed_nap_name="D4"` → candidato `NAP D4` con `state="REVIEW"` y `confidence` `MEDIA`/`BAJA`, nunca `ALTA`.
  - Caso C (NAP LAB cruzado): ONU PCM con `nap_id` apuntando a Nap LAB → `onus_with_cross_olt_nap` incrementado para PCM; la propuesta siempre usa `proposed_olt_id == olt_pcm.id`.
  - Caso D (NAP D4 vs ODN D4): ONUs con `parsed_nap_name="NAP D4"` y `parsed_odn="ODN D4"` → catálogo incluye dos entradas distintas (`("NAP", "NAP D4")`, `("ODN", "ODN D4")`).
  - Caso E (ruido documental): `parsed_nap_name="D1_Calle_Chiquito_Cliente_Garaje"` → candidato en estado `REVIEW` o `BLOCKED`, nunca `NEW` con confianza `ALTA`.
  - Caso F (Nap existente): Nap PCM "ODN H5" existente y ONU con `parsed_odn="ODN_H5------COOPERATIVA"` → candidato con `exists_in_olt=True`, `existing_nap_id` correcto, `state="EXISTS"`.
- Verificación:
  - Ejecutado `python -m compileall backend/app` sin errores (incluyendo `schemas.entities` y `nap_reconstruction_preview_service`).
  - Ejecutado `pytest tests/test_nap_reconstruction_preview_service.py tests/test_territorial_identity.py -q`; 14/14 tests pasando en ~0.76s, confirmando que la infraestructura de identidad territorial y el preview NAP/ODN/ODB funcionan en modo sólo lectura y respetan las EFO.

## 2026-06-24 — P4.4 API Read-Only de Reconstrucción Territorial

- Añadido router `backend/app/api/routes/territorial.py` con endpoints de sólo lectura para exponer los previews territoriales existentes:
  - `GET /api/v1/admin/territorial/zones/preview` (response_model=`ZoneReconstructionPreview`):
    - Llama a `ZoneReconstructionPreviewService.preview()` y devuelve su resultado tal cual.
    - Documentado en OpenAPI como operación de preview estrictamente read-only (sin apply, sin escrituras, sin Telnet).
  - `GET /api/v1/admin/territorial/naps/preview` (response_model=`NapReconstructionPreview`):
    - Llama a `NapReconstructionPreviewService.preview()` y devuelve su resultado tal cual.
    - Igualmente documentado como operación sólo lectura sobre datos ya importados.
- Registrado el router `territorial` en `backend/app/api/router.py` con prefijo `/admin/territorial` bajo `api_router.include_router(territorial.router)`.
- Añadido test de API `tests/test_territorial_preview_api.py` que verifica:
  - `GET /api/v1/admin/territorial/zones/preview` devuelve 200 y un objeto con claves `summaries`, `catalog_proposals` y `onus`.
  - `GET /api/v1/admin/territorial/naps/preview` devuelve 200 y un objeto con las mismas claves principales.
- Verificación técnica:
  - Ejecutado `python -m compileall backend/app` sin errores (incluyendo `api/router.py` y `api/routes/territorial.py`).
  - Intento de `pytest tests/test_territorial_preview_api.py -q` falló en importación por falta de driver `psycopg` al inicializar el engine PostgreSQL global en este entorno, consistente con el estado conocido documentado en `AI_HANDOFF.md`; el fallo no se debe al nuevo router, que no realiza escrituras ni cambia el modelo de datos.

## 2026-06-24 — P4.1 Preview de reconstrucción de Zones por OLT

- Añadido servicio de solo lectura `ZoneReconstructionPreviewService` en `backend/app/services/zone_reconstruction_preview_service.py` que implementa la preview de reconstrucción de Zones por OLT (Fase P4.1) sin modificar datos ni crear migraciones:
  - Carga `Olt`, `Zone` y `Onu` desde la BD y calcula en memoria:
    - Un resumen por OLT (`ZoneReconstructionOltSummary`) con:
      - `total_onus`.
      - `zones_existing` (nombres de Zones actuales por OLT).
      - `zones_missing_proposed` (nombres de Zones candidatos por OLT derivados de `parsed_zone_name`/`zone_name` que aún no existen en esa OLT).
      - Conteos de ONUs con `zone_id` correcto, `zone_id` cruzado (Zone.olt_id != Onu.olt_id), sin zona, reasignables y bloqueadas.
    - Una matriz ONU actual vs propuesta (`ZoneReconstructionOnuProposal`) que expone por ONU:
      - Identidad de ONU (interface, serial, customer_name, olt_id/olt_code).
      - Zone actual (`current_zone_id`, `current_zone_name`, `current_zone_olt_id`, `current_zone_olt_code`, `current_zone_olt_name`).
      - Propuesta territorial (`proposed_zone_name`, `proposed_zone_olt_id`, `proposed_zone_olt_code`, `proposed_zone_olt_name`).
      - Nivel de confianza (`confidence` = `ALTA`/`MEDIA`/`BAJA`/`BLOQUEADO`).
      - `reasons` textuales (`from_parsed_zone_name`, `from_zone_name_field`, `cross_olt_zone_detected`, `no_zone_evidence`, etc.).
  - Niveles de confianza implementados según la EFO Modelo Territorial FTTH:
    - `ALTA`: `parsed_zone_name` claro y repetido en varias ONUs de la misma OLT.
    - `MEDIA`: `parsed_zone_name` presente pero con baja frecuencia (1 sola ONU).
    - `BAJA`: sólo `zone_name` estructurado sin evidencia fuerte de repetición.
    - `BLOQUEADO`: sin evidencia territorial (`zone_id` nulo y sin `parsed_zone_name`/`zone_name` relevantes).
  - Respeta scoping estricto por `olt_id`: la propuesta de zona siempre se formula como `(olt_id = Onu.olt_id, name = candidate)` sin reutilizar Zones de otra OLT, incluso cuando el nombre coincide.
  - Caso específico `OLT-PCM-ZTE-01`:
    - Cuando ONUs PCM tienen `parsed_zone_name == "Lagunas"` y sólo existe `Zone("Lagunas")` en LAB, el preview:
      - Incluye `"Lagunas"` en `zones_missing_proposed` de PCM.
      - Mantiene `"Lagunas"` únicamente en `zones_existing` de LAB.
      - Propone para cada ONU PCM afectada `proposed_zone_name = "Lagunas"` y `proposed_zone_olt_id = olt_pcm.id`, cumpliendo la regla "no reutilizar Zone Lagunas de LAB".
- Añadidos DTOs de esquema en `backend/app/schemas/entities.py` para exponer la preview:
  - `ZoneReconstructionOltSummary`.
  - `ZoneReconstructionOnuProposal`.
  - `ZoneReconstructionPreview`.
- Añadidos tests unitarios en `tests/test_zone_reconstruction_preview_service.py` usando SQLite en memoria que validan:
  - `test_pcm_lagunas_zone_is_proposed_for_pcm_not_reusing_lab_zone`: garantiza que la zona `Lagunas` se propone como faltante en PCM (`zones_missing_proposed`) sin reutilizar la Zone de LAB, y que las ONUs PCM tienen `proposed_zone_olt_id == olt_pcm.id`.
  - `test_existing_pcm_zone_is_treated_as_correct`: una ONU PCM apuntando a una Zone `Lagunas` propia de PCM se contabiliza como `onus_with_correct_zone` y no se marca como reasignable.
  - `test_cross_olt_zone_is_detected_and_marked_reassignable`: detecta `zone_id` cruzado PCM→LAB, incrementa `onus_with_cross_olt_zone` y `onus_reassignable` para PCM y añade `cross_olt_zone_detected` en `reasons`.
  - `test_onu_without_any_zone_information_is_blocked`: una ONU sin `zone_id`, `zone_name` ni `parsed_zone_name` se marca con `confidence == "BLOQUEADO"` y razón `no_zone_evidence`.
- Verificación técnica:
  - Ejecutado `python -m compileall backend/app` sin errores (compilación exitosa de `schemas.entities` y `zone_reconstruction_preview_service`).
  - Ejecutado `DATABASE_URL=sqlite+pysqlite:///:memory: pytest tests/test_zone_reconstruction_preview_service.py -q`; 4/4 tests pasando, confirmando que el servicio de preview de Zones funciona en modo solo lectura y respeta el scoping por OLT definido en las EFO.

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
