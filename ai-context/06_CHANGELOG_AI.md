# AI Changelog

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
