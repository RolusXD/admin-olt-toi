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

### Observaciones recientes sobre NAP/ODN (documental)

- [ ] Incorporar en futuras fases de catálogo NAP por OLT y saneamiento operacional la regla confirmada en auditoría de que:
  - El prefijo forma parte de la identidad canónica de planta externa (`NAP`, `ODN`, `ODB`).
  - `NAP D01` y `ODN D01` son entidades distintas que coexisten en la misma OLT (idéntico para `D2`, `D3`, `D4`, `F7`).
  - No se permite normalización que elimine los prefijos ni que colapse ambos tipos bajo `D01`/`D2`/`F7`, etc.
  - Cualquier tooling de saneamiento debe tratar explícitamente estos prefijos como parte de la clave visible y de los índices internos.

## Modelo ONU y service_mode_code

- [x] Implementar parser estructurado de `pon-onu-mng` que produzca un modelo tipo `OnuPonOnuMngModel` alineado con `docs/EFO_NORMALIZACION_MODELO_ONU.md` (sin cambiar aún el esquema de BD).
  - Fase P2: `ParsedOnuManagementMode` extendido con `mode_simple`, `port_mode`, `service_vlans`, `allowed_vlans`, `native_vlan`, `wan_vlan_id`, `vlan_filter_rules` y `flows`; reglas de clasificación `router/bridge/transparent/unknown` implementadas sin introducir nuevos `service_mode_code`.
- [ ] Definir y poblar `OnuServiceModeTemplate` por OLT a partir de los modos reales observados en `OLT-PCM-ZTE-01` (router/bridge/transparente) respetando el scoping por `olt_id` (más allá de los tres modos históricos ya detectados automáticamente).
- [x] Integrar la normalización de `service_mode_code` (raw → normalizado) en la importación inicial, manteniendo ONUs no clasificadas en modo simple `unknown`.
  - Fase P2: `InitialImportService` ya persiste `service_mode_code` para todas las ONUs clasificadas por el parser (incluyendo casos bridge híbridos/trunk), reutilizando los valores compatibles `router_iphost`, `bridge_tag_internet`, `transparent_special` y `unknown`.

## Data Quality Roadmap (EFO – Fase A)

- Introducir `data_quality_status` en el modelo de ONU y un evaluador de calidad documental por OLT, siguiendo la EFO de "Calidad de Datos, Catálogos Técnicos y Gobierno de OLT".
  - ✅ Fase A1/A2: campo `data_quality_status` y servicio `OnuDataQualityService` implementados y aplicados durante la importación inicial sin bloquear provisión.
- Definir un primer conjunto de métricas y endpoints de sólo lectura para un dashboard básico de calidad (sin bloquear provisión existente).
  - ✅ Fase A2: endpoints de observabilidad `GET /olts/{id}/data-quality-summary` y `GET /onus/data-quality` implementados; dashboard visual se reserva para Fase B.
- Alinear con operaciones qué campos mínimos serán obligatorios para nuevas ONUs antes de activar validaciones duras en backend/frontend.

## Operations

- Add retention policies for command logs, power history and raw snapshots.
- Review Celery schedules and concurrency before enabling unattended production polling.
- Add health and backup monitoring for PostgreSQL and Redis.

### Sprint 0 – Gobierno Operativo (Usuarios, Roles, Permisos, Auditoría)

- [x] Introducir modelo de usuario operativo interno (`User`) sin cambiar aún el mecanismo de login por variables de entorno.
- [x] Definir modelo de roles operativos (`Role`) y tabla de asignación `UserRole` permitiendo que un usuario tenga múltiples roles.
- [x] Definir catálogo de permisos desacoplado de los roles (`Permission`) siguiendo ejemplos de EFO (ONU.READ, OLT.ADOPT, AUDIT.READ, USER.UPDATE, etc.).
- [x] Introducir tabla de cruce `RolePermission` con `execution_policy` (`FULL`/`READ_ONLY`/`REVIEW`/`DENY`) y flag `requires_supervisor_approval` preparado para futuras aprobaciones.
- [x] Implementar tabla `OperationId` y servicio `OperationIdService` para generar identificadores reutilizables de operación con formato `OP-YYYYMMDD-HHMMSS-XXXX`.
- [x] Extender `EventLog` y `EventService` para soportar Audit Trail y bitácora operativa con campos de contexto (operation_id, user_name, role_code, origin, result, action, duration_ms, reason, error).
- [ ] Integrar de forma progresiva `OperationIdService` y `EventService` en flujos clave (Import, Snapshot, Provisioning, Recovery, Scheduler, CLI) manteniendo la regla de "no romper nada" y añadiendo sólo registros adicionales.
  - [x] Introducir servicios de infraestructura `OperatorContextService` y `OperationLogService` para resolver identidad operativa y registrar operaciones con `operation_id` sin activar todavía autorización por permisos ni bloquear endpoints.
  - [x] Empezar a utilizar `OperationLogService` en flujos reales iniciales:
    - [x] Importación inicial (preview/confirm) envolviendo el servicio `InitialImportService` y registrando eventos `IMPORT_INITIAL`, `IMPORT_SNAPSHOT_CAPTURED` e `IMPORT_CONFIRMED` con `operation_id` compartido.
    - [x] Snapshot manual (backup de running-config en `OltService.backup`) con eventos `SNAPSHOT_MANUAL` y `BACKUP_CREATED` enriquecidos con identidad operativa cuando exista.
    - [x] Tareas de Scheduler (`sync_onu_states_task`, `sync_onu_power_task`) utilizando `OperationLogService` con `origin="SCHEDULER"` y rol `SYSTEM`.

## UX and QA

- Complete visual browser regression checks for desktop and mobile operational pages.
- Add end-to-end tests for the five-step OLT import wizard using mocked read-only APIs.
 - [x] Endurecer confirmación de importación inicial para rechazar jobs en estados no válidos y mejorar el feedback de progreso en la etapa Preview.
   - ✅ UI de importación inicial ahora consume `GET /import/jobs/{job_id}` para mostrar estado real del job/snapshot, advertencias y conteos consolidados sin requerir WebSockets.
 - [x] Añadir verificación visual/manual de la nueva sección de solo lectura "Comportamiento ONU" en la ficha de ONU, asegurando que:
    - ✅ Muestra modo ONU, VLAN WAN, perfiles UP/DOWN y flags básicos (DHCP source, IPHost, VEIP, VLAN filter, Loop Detect, WiFi) cuando existe `service_mode_code` y plantilla asociada.
    - ✅ Muestra el estado "Desconocido/importado" y la advertencia suave cuando no hay modo clasificado.
    - ✅ No ofrece controles de edición ni acciones que disparen Telnet desde esta vista.
    - No ofrece controles de edición ni acciones que disparen Telnet desde esta vista.

## Modelo Territorial FTTH / P4

- [ ] P4.1 – Reconstrucción de Zones por OLT (especialmente `OLT-PCM-ZTE-01`):
  - [x] Analizar `parsed_zone_name` y descripciones heredadas para proponer `Zone(olt_id, name, source, data_quality_status)` sin aplicar cambios.
  - [x] Generar un preview de catálogo de zonas por OLT (LAB, PCM) etiquetando la confianza de cada zona.
    - Implementado servicio de solo lectura `ZoneReconstructionPreviewService` que calcula:
      - Resumen por OLT (`ZoneReconstructionOltSummary`) con zonas existentes, zonas propuestas faltantes, ONUs con zone_id correcto, cruzado, sin zona, reasignables y bloqueadas.
      - Matriz ONU actual vs propuesta (`ZoneReconstructionOnuProposal`) usando `Onu.parsed_zone_name`, `Onu.zone_name`, `Onu.zone_id` y `Zone.olt_id`.
      - Niveles de confianza por ONU (`ALTA`/`MEDIA`/`BAJA`/`BLOQUEADO`) basados en frecuencia y origen (`parsed_zone_name` vs `zone_name`) respetando scoping por `olt_id`.
    - Para `OLT-PCM-ZTE-01` el preview propone explícitamente la zona `Lagunas` scopiada a PCM cuando aparece en `parsed_zone_name`, sin reutilizar la Zone `Lagunas` de LAB.

- [ ] P4.2 – Reconstrucción de NAP/ODN/ODB por OLT:
  - [ ] Separar NAP/ODN/ODB a partir de `parsed_nap_name`, `parsed_odn` y `odb_name`, respetando la identidad canónica con prefijos (`NAP`/`ODN`/`ODB`).
  - [ ] Proponer catálogo `Nap(olt_id, zone_id, type/prefix, canonical_name, display_name, capacity, splitter_type, data_quality_status)` por OLT sin tocar BD.
  - [ ] Reutilizar el Territorial Reconstruction Engine (TRE) para modelar candidatos territoriales (`TerritorialCandidate`) con `evidence_score` y estados (`NEW`/`EXISTS`/`REVIEW`/`BLOCKED`/`MERGE`) a partir de evidencias (`TerritorialEvidence`) sin aplicar cambios.
  - [x] Introducir una capa reutilizable de identidad territorial (`TerritorialIdentity` / `TerritorialNormalizer`) que centralice la normalización de nombres NAP/ODN/ODB/NapPort preservando prefijos y reglas canónicas documentadas en las EFO.

- [ ] P4.3 – Reconstrucción de NapPorts:
  - [ ] Inferir capacidad y puertos por NAP/ODN/ODB usando `capacity`, `splitter_type` y ocupación observada por ONUs.
  - [ ] Generar preview de `NapPort(olt_id, nap_id, port_number, status, onu_id opcional)` sin crear registros reales.
  - [ ] Integrar NapPort como dominio soportado por el TRE reutilizando evaluadores de confianza y detectores de conflicto específicos (solapamientos de puertos, ocupación ambigua) sin modificar BD.

- [ ] P4.4 – Preview de reasignación ONU/ProvisioningPlan:
  - [ ] Construir matriz `ONU actual vs propuesta` (Zone/Nap/NapPort LAB → PCM) con niveles de confianza (`alta`/`media`/`baja`/`bloqueado`).
  - [ ] Incluir en el preview los 454 ONUs PCM con `zone_id` cruzado, 169 con `nap_id` cruzado y los 27 `ProvisioningPlan` PCM con Zone/NAP cruzados.

- [ ] P4.5 – Apply controlado (diseño futuro):
  - [x] Implementar Centro de Auditoría Territorial de solo lectura (P4.5 – "audit center") que consolide los previews de Zones y NAP/ODN/ODB por OLT y exponga issues/recomendaciones sin tocar BD (`TerritorialAuditCenterService` + `GET /api/v1/admin/territorial/audit-center`).
  - [ ] Definir el flujo de aprobación humana y auditoría antes/después para aplicar reasignaciones territoriales.
  - [ ] Documentar validaciones duras para impedir que nuevas ONUs/planes vuelvan a usar Zones/NAPs/NapPorts de otra OLT.

## P5 – Consola Inteligente de Auditoría Territorial

- [x] Implementar página frontend `/territorial-audit` de solo lectura que consuma `GET /api/v1/admin/territorial/audit-center` y muestre:
  - Resumen ejecutivo por OLT y por estado (HEALTHY/NEEDS_REVIEW/DEGRADED/CRITICAL).
  - Tabla por OLT con métricas de Zones/NAPs/cross-OLT/review/blocked.
  - Resúmenes de estados territoriales y niveles de confianza.
  - Issues críticos y recomendaciones generadas por backend.
  - Accesos rápidos a los endpoints de preview territorial.
  - Sin botones de apply ni formularios de escritura.
  - Filtros superiores por OLT, status, severidad, tipo de issue y búsqueda libre (por `olt_code`, `entity_name`, `issue_type`, `message`, `recommendation`).
  - Drill-down visual por OLT que muestra issues filtrados, recomendaciones relacionadas y conteos principales sin requests de escritura.

## Arquitectura Base Finalizada

- [x] EFO Gobierno de Catálogos
  - `docs/EFO_GOBIERNO_DE_CATALOGOS.md` consolidada como constitución arquitectónica para clasificación de catálogos (global/técnico/territorial/operativo), gobierno de información, invariantes por `olt_id` y roadmap OSS FTTH.

## P6 – Arquitectura Operativa y Ciclo de Vida OLT

- [x] Definir arquitectura operativa de Admin OLT TOI como Sistema Operativo de OLTs, distinguiendo:
  - Estado observado (Observed State).
  - Estado aprobado (Desired State).
  - Estado histórico (Snapshots).
  - Inventario oficial.
  - → `docs/EFO_ARQUITECTURA_OPERATIVA_ADMIN_OLT_TOI.md`.

- [ ] P6.1 – Formalización de Desired/Observed State y Drift (nivel servicios/DTOs, sin cambiar esquema)
  - [ ] Definir en servicios internos y DTOs el modelo lógico de Desired State por OLT alineado con la nueva EFO (sin nuevas tablas).
  - [ ] Definir en servicios internos y DTOs el modelo lógico de Observed State por OLT como proyección unificada de snapshots + monitoreo.
  - [ ] Introducir un módulo de Drift Detection (sólo lectura) que clasifique diferencias según categorías: `SYNC`, `CONFIG_MISMATCH`, `MISSING_IN_OLT`, `MISSING_IN_SYSTEM`, `EXTRA_OBJECT`, `CONFLICT`, `UNMANAGED_OBJECT`.

- [ ] P6.2 – Inventario oficial y adopción de OLTs
  - [ ] Definir criterios formales para que una OLT pase a estado `ADOPTED` (cobertura de inventario, calidad de datos mínima, estado territorial saneado, etc.).
  - [ ] Diseñar tooling documental/operativo para declarar un corte de «inventario aprobado» por OLT sin cambiar aún el modelo físico.
  - [ ] Integrar la noción de OLT adoptada en reportes y consola de auditoría territorial (sólo lectura).

- [ ] P6.3 – Sincronización asistida y planes de saneamiento
  - [ ] Reutilizar Drift Detection para generar propuestas de saneamiento de inventario y/o configuración, siempre vía preview.
  - [ ] Diseñar previews de drift específicos (por OLT, por PON, por zona/NAP) que combinen información de P4.x y del modelo operacional ONU.
  - [ ] Documentar políticas de aceptación automática únicamente para cambios de bajo riesgo, manteniendo aprobación final humana.

- [ ] P6.4 – Provisioning operacional completo sobre inventario oficial
  - [ ] Alinear todos los flujos de alta/baja/cambio ONU con Desired State e invariantes de gobierno de catálogos.
  - [ ] Verificar que ningún flujo de provisión bypassa el inventario ni modifica la OLT sin snapshot + validación posterior.
  - [ ] Extender cobertura de tests (cuando proceda) para cubrir el ciclo Inventario → OLT → Snapshot → Validación (sin añadir nuevas acciones Telnet no autorizadas).

- [ ] P6.5 – Recuperación asistida desde inventario y snapshots
  - [ ] Documentar y prototipar flujos de recuperación completa de una OLT a partir de Desired State + snapshots históricos.
  - [ ] Documentar y prototipar flujos de recuperación parcial (por PON, por NAP, por conjunto de ONUs) como planes de provisión controlados.
  - [ ] Integrar vistas de simulación de recuperación en la consola de auditoría (sólo lectura).

- [ ] P6.6 – Multivendor operativo
  - [ ] Alinear el modelo lógico de Desired/Observed State y Drift para ZTE/VSOL/Huawei/FiberHome sin modificar el núcleo de inventario.
  - [ ] Definir contratos mínimos de drivers/parsers por vendor que proyecten su estado a los modelos comunes de esta EFO.

- [ ] P6.7 – Integración OSS FTTH ampliada
  - [ ] Alinear el modelo operativo de OLT con integraciones GIS, CRM y ERP ya previstas en el roadmap de gobierno de catálogos.
  - [ ] Definir qué partes del Desired State se exponen a sistemas externos como fuente canónica (por ejemplo, catálogo territorial y ONUs activas).

## P7 – Observabilidad y Conocimiento Operativo

- [ ] P7.1 – Observabilidad OLT
  - [ ] Definir métricas mínimas para estado, uptime, reinicios, CPU/memoria/temperatura, alarmas y tráfico por uplink a nivel de OLT (solo documentación y modelos conceptuales).
- [ ] P7.2 – Observabilidad PON
  - [ ] Diseñar el modelo de observabilidad de puertos PON (estado, ocupación, ONUs online/offline, errores, saturación y alertas de caída masiva) sin cambiar BD ni endpoints.
- [ ] P7.3 – Observabilidad ONU
  - [ ] Completar el diseño de fichas operativas ONU integrando estado actual, potencia, históricos, eventos, alarmas y drift, reutilizando el modelo operacional ONU.
- [ ] P7.4 – Históricos ópticos
  - [ ] Definir esquema conceptual de `power history` (ONU/PON/NAP/Zona) y su uso para diagnóstico, tendencias y planificación, sin introducir nuevas tablas físicas todavía.
- [ ] P7.5 – Alertas
  - [ ] Documentar reglas mínimas de alertas (OLT, PON, ONU, NAP/Zona), umbrales y prioridades, alineadas con la arquitectura operativa y sin ejecutar acciones de apply.
- [ ] P7.6 – Health Scores
  - [ ] Diseñar Health Scores explicables para OLT, PON, uplink, ONU, NAP/ODN/ODB y Zona, basados en métricas de observabilidad y sin lógica opaca.
- [ ] P7.7 – Knowledge Layer
  - [ ] Formalizar el modelo de conocimiento operativo (patrones de degradación, reincidencias por NAP/zona, PON próximas a saturación, OLTs con reinicios repetidos) a partir de históricos.
- [ ] P7.8 – Recomendaciones asistidas
  - [ ] Definir catálogos de recomendaciones y reglas de IA que traduzcan conocimiento operativo en sugerencias, manteniendo la prohibición de ejecutar cambios automáticamente.
- [ ] P7.9 – Integración Zabbix/SNMP
  - [ ] Planificar la integración documental de fuentes externas de monitoreo (Zabbix, SNMP u otras) como insumos de observabilidad sin cambiar aún el backend.
- [ ] P7.10 – Dashboard operativo
  - [ ] Diseñar dashboards operativos (NOC/operaciones) basados en métricas, alertas, Health Scores y conocimiento operativo, respetando la separación Observed/Desired State y sin añadir acciones de apply.
