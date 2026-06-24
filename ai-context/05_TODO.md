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
