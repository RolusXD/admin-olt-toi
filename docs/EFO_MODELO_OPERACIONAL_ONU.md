# Especificación Funcional Oficial

## Modelo Operacional de ONU por OLT

Versión: 1.0  
Fecha: 2026-06-22  
Ámbito: Proyecto TOI OLT Manager (ZTE C300)

---

## 1. Objetivo

Definir el **modelo operacional de ONU** en TOI OLT Manager sin duplicar módulos existentes, respetando que **toda entidad técnica pertenece a una OLT** y reutilizando los catálogos ya implementados.

Este modelo describe cómo se relacionan:

- `OnuType` – **hardware / capacidades físicas de la ONU** por OLT.
- `OnuServiceModeTemplate` – **plantilla de comportamiento ONU** (modo de servicio) por OLT.
- `Onu` – **estado actual** de una ONU detectada/importada/provisionada.
- `ProvisioningPlan` – **estado objetivo** de provisión para una ONU nueva o existente.

No introduce nuevas tablas de catálogo globales; se apoya en las existentes, todas **scoped por `olt_id`**.

---

## 2. Principios y reglas de diseño

### 2.1. No duplicar módulos existentes

1. `OnuType` ya representa el **hardware y capacidades físicas** de la ONU.
   - Campos relevantes: `ethernet_ports`, `wifi_ports`, `pots_ports`, `rf_ports`, `max_iphost`, `max_tcont`, `max_gemport`, `capability_mode`, etc.
   - Se importa desde `show running-config` por OLT y se mantiene scoped por `olt_id`.

2. `OnuServiceModeTemplate` ya representa el **modo de servicio / comportamiento ONU** por OLT.
   - Tabla: `onu_service_mode_templates`.
   - Campos clave: `olt_id`, `mode_code`, `name`, `description`, `vlan_mode`, `dhcp_source`, `use_iphost`, `use_veip`, `use_vlan_filter`, `use_loop_detect`, `disable_wifi`, `template_body`, `default_for_provisioning`.
   - Se alimenta inicialmente a partir de la importación (`SERVICE_MODE_DEFINITIONS` + `ParsedOnuManagementMode`).

3. `ProvisioningPlan` ya es el **artefacto de planificación y provisión controlada**.
   - Contiene `olt_id`, `service_mode_code`, `vlan`, `speed_profile_*`, `onu_type`, `zone_id`, `nap_id`, `nap_port`, `generated_cli`, etc.
   - Es la **única vía autorizada** para dar de alta ONUs nuevas en inventario.

> **Decisión:** No crear nuevos catálogos de capacidades ONU ni nuevos catálogos de modos de servicio. Toda evolución debe reutilizar y extender `OnuType` y `OnuServiceModeTemplate`.

### 2.2. Todo objeto técnico pertenece a una OLT

Se refuerza la regla de la EFO de Calidad de Datos:

> **Toda entidad técnica (VLAN, Zona, NAP, Tipo ONU, Perfil, Modo de servicio, Plantilla de comportamiento) pertenece a una única OLT.**

Implicaciones concretas para el modelo operacional ONU:

- `OnuType` siempre lleva `olt_id` y `olt_code_snapshot`.
- `OnuServiceModeTemplate` siempre lleva `olt_id`; un plan **no puede** usar una plantilla de otra OLT.
- `ProvisioningPlan` siempre lleva `olt_id` y sólo puede referenciar:
  - VLANs (`Vlan`),
  - Zonas (`Zone`), NAPs (`Nap`), puertos NAP (`NapPort`),
  - Tipos ONU (`OnuType`),
  - Perfiles (`SpeedProfile`, `ProfileCatalog`),
  - Modos de servicio (`OnuServiceModeTemplate`),
  cuyo `olt_id` coincide con el del plan.

No se permite crear catálogos globales para:

- VLANs, Zonas, NAPs, Tipos ONU, Perfiles, Modos de servicio, ni plantillas de comportamiento ONU.
- La única excepción global controlada sigue siendo `ProvisioningTemplate` (estructura CLI genérica por vendor/model), sin referencias a catálogos específicos de OLT.

---

## 3. Diferenciación funcional de entidades

### 3.1. `OnuType` — Hardware y capacidades

Representa el **modelo físico de ONU** conocido por una OLT:

- Cantidad de puertos LAN (`ethernet_ports`).
- Presencia de WiFi (`wifi_ports`), CATV (`rf_ports`), VoIP (`pots_ports`).
- Límites técnicos: `max_iphost`, `max_tcont`, `max_gemport`, `max_switch_perslot`, `max_flow_perswitch`.
- Modo de capacidad de fábrica: `capability_mode` (p.ej. `bridging`).

`OnuType` **no contiene** comportamiento lógico de provisión (DHCP, VLAN filter, flows, etc.); es exclusivamente un catálogo técnico de capacidades.

### 3.2. `OnuServiceModeTemplate` — Comportamiento operacional por OLT

Representa **cómo se comporta una ONU** bajo un determinado *modo de servicio* para una OLT concreta:

- `mode_code` (por ejemplo: `bridge_tag_internet`, `router_iphost`, `transparent_special`).
- `vlan_mode` (tag / transparent / untag).
- `dhcp_source` (from-internet / from-onu / none).
- Flags de gestión: `use_iphost`, `use_veip`, `use_vlan_filter`, `use_loop_detect`, `disable_wifi`.
- `template_body`: cuerpo CLI parametrizado que define el bloque `pon-onu-mng` y comandos relacionados.

Es, en la práctica, la **plantilla de comportamiento ONU** por OLT y modo. No debe duplicarse en otro catálogo.

### 3.3. `Onu` — Estado actual de la ONU

`Onu` describe la **ONU que existe hoy en la OLT**:

- Identidad: `olt_id`, `serial_number`, `onu_interface`, `onu_type` (string vinculado a `OnuType`), `vlan`.
- Perfiles efectivos: `speed_profile_up`, `speed_profile_down`.
- Ubicación: `zone_id`, `nap_id`, `nap_port`.
- Estado operativo: `status`, `signal_status`, `rx_power`, `tx_power`.
- Información de calidad documental: `data_quality_status`, `data_quality_missing_fields`.
- Modo de servicio histórico: `service_mode_code` (`bridge_tag_internet`, `router_iphost`, etc.), importado desde el running-config o establecido en provisión.

### 3.4. `ProvisioningPlan` — Estado objetivo

`ProvisioningPlan` define **qué queremos que sea una ONU** tras la provisión controlada:

- `olt_id`, `unauthorized_onu_id`, `serial_number`, `pon_port_interface`.
- Datos documentales obligatorios (cliente, zona, NAP, puerto NAP, dirección, etc.).
- Decisiones operativas:
  - `onu_type` (vinculado a `OnuType`).
  - `service_mode_code` (vinculado a `OnuServiceModeTemplate`).
  - `vlan` (VLAN WAN/servicio).
  - `speed_profile_up`, `speed_profile_down` (y vínculos a `SpeedProfile` / `ProfileCatalog`).
- Resultado de planificación:
  - `generated_cli` (CLI completo que se ejecutará),
  - `validation_result` y `preflight_checks`.

Tras la ejecución exitosa, `ProvisioningPlan` actualiza `Onu` al nuevo estado y deja rastro del CLI aplicado.

---

## 4. Experiencia de UI para el técnico

### 4.1. Flujo simple (por defecto)

En el flujo de creación de plan de provisión para una ONU nueva o pendiente (`ProvisioningPlanCreate`), la UI debe exponer por defecto **sólo cuatro decisiones operacionales**:

1. **Modo ONU (simple):** `Router` / `Bridge` / `Transparente` / `Desconocido`.
   - Estos cuatro modos simples son la proyección de `service_mode_code` documentada en `docs/EFO_NORMALIZACION_MODELO_ONU.md` (`router`, `bridge`, `transparent`, `unknown`).
   - Cualquier variante avanzada (por ejemplo modos "híbridos" que combinan varios servicios por puerto) debe modelarse como plantillas específicas en `OnuServiceModeTemplate` y terminar proyectándose a uno de esos cuatro modos simples.
2. **VLAN WAN/servicio:** selector de `Vlan` filtrado por `olt_id`.
3. **Perfil de subida:** selección de perfil UP (`SpeedProfile` / `ProfileCatalog`).
4. **Perfil de bajada:** selección de perfil DOWN.

El resto de parámetros técnicos (IPHost, VEIP, flows, VLAN filter, DHCP detallado, security-mng, etc.) se resuelven a partir de:

- `OnuType` (capacidades físicas),
- `OnuServiceModeTemplate` (comportamiento por modo/OLT),
- y los parámetros simples del plan.

### 4.2. Configuración avanzada (oculta por defecto)

La UI avanzaday debe mantenerse colapsada/invisible hasta que el técnico la expanda explícitamente. En esta vista se muestran de forma **estructurada** (no como texto libre) los siguientes elementos:

- **Gestión IP:**
  - IPHost: activado/desactivado, índice, VLAN asociada.
  - VEIP: activado/desactivado, uso para gestión/TR-069/etc.
- **VLAN & filtros:**
  - Modo VLAN (`tag`, `transparent`, `untag`).
  - Reglas de VLAN filter (a nivel de IPHost / flows), derivadas de `use_vlan_filter` y la VLAN seleccionada.
- **Flows y GEMPORT:**
  - `flow mode`, `flow priority`, `gemport-flow binding` (relación `gemport` ↔ `flow` ↔ `VLAN`).
- **DHCP source:**
  - Origen lógico (`from-onu`, `from-internet`, `none`) y, si aplica, por puerto ethernet.
- **security-mng:**
  - Perfiles de gestión (HTTPS/HTTP desde LAN, SSH/Telnet/SNMP/Tr069, etc.) expresados como opciones lógicas.
- **Puertos Ethernet:**
  - Por cada puerto físico hasta `OnuType.ethernet_ports`:
    - Estado (enable/disable),
    - rol (LAN interna / servicio / gestión),
    - modo (Access / Tag / Transparent),
    - VLAN primaria y, opcionalmente, VLANs adicionales.
- **WiFi (si aplica):**
  - Activado/desactivado, SSID básico y flags derivados de `disable_wifi` + `OnuType.wifi_ports`.

> **Regla:** la configuración avanzada controla **parámetros estructurados** que luego se traducen a CLI mediante plantillas. El técnico **no** edita líneas de CLI en bruto.

---

## 5. Raw `pon-onu-mng` como auditoría

### 5.1. Conservación del bloque completo por ONU

Para cada ONU conocida, el sistema debe preservar el bloque `pon-onu-mng` actual como parte del historial de configuración:

- `raw_pon_onu_mng` (concepto): bloque completo tal como aparece en el running-config o tal como fue generado por el último `ProvisioningPlan` ejecutado.
- Origen:
  - Importación inicial: extraído de `show running-config`.
  - Provisión: bloque reconstruido desde `OnuServiceModeTemplate` y el modelo estructurado.

### 5.2. Restricciones

- El bloque `raw_pon_onu_mng` **no es editable** como texto libre en ninguna vista.
    - Cualquier cambio de comportamiento ONU debe hacerse:
    - cambiando el modo simple (Router/Bridge/Transparente/Desconocido),
    - ajustando VLAN/perfiles,
    - o modificando parámetros estructurados en la vista avanzada.
- El CLI definitivo se **regenera siempre** a partir de:
  - `OnuType`,
  - `OnuServiceModeTemplate`,
  - catálogos técnicos de la OLT (VLANs, perfiles),
  - y parámetros del `ProvisioningPlan`.

El bloque crudo se muestra únicamente como **lectura/auditoría**, por ejemplo en la ficha ONU.

---

## 6. Generación de CLI en provisioning

### 6.1. Fuentes autorizadas para generar CLI

El CLI que se aplica a una OLT durante provisión debe generarse exclusivamente desde los siguientes elementos:

1. **`OnuType`** — capacidades físicas
   - Número de puertos ethernet (`ethernet_ports`) utilizado para construir:
     - Lista de puertos de gestión o servicio (`eth_0/1`, `eth_0/2`, …).
   - Límites que definen hasta dónde es seguro crear flows, gemports, IPHosts, etc.

2. **`OnuServiceModeTemplate`** — comportamiento ONU por OLT
   - Determina cómo se construye el bloque `pon-onu-mng`:
     - `vlan_mode`, `dhcp_source`, `use_iphost`, `use_veip`, `use_vlan_filter`, `use_loop_detect`, `disable_wifi`.
   - `template_body` proporciona la estructura textual de comandos para management (flows, VLAN filter, security-mng, DHCP, etc.).

3. **Catálogos técnicos de la OLT**
   - VLANs (`Vlan`), Perfiles GPON (`GponProfile`), `ProfileCatalog`, `SpeedProfile`.
   - Siempre filtrados por `olt_id` del plan.

4. **Parámetros de `ProvisioningPlan`**
   - `onu_type`, `service_mode_code`, `vlan`, `speed_profile_up`, `speed_profile_down`, `zone_id`, `nap_id`, `nap_port`, etc.
   - Decisiones opcionales como `ethernet_port`, `vlan_lan_mode`, `dhcp_mode` se utilizan como hints de UI, pero deben ser coherentes con `OnuServiceModeTemplate`.

### 6.2. Lo que NO se permite

- No se permite construir CLI a partir de:
  - texto libre editado por el usuario para `pon-onu-mng`;
  - bloques pegados manualmente desde la OLT sin pasar por el modelo estructurado;
  - catálogos globales sin `olt_id`.

Toda generación debe seguir el flujo:

1. Resolver `OnuType` y `OnuServiceModeTemplate` correctos para la OLT.
2. Construir, en memoria, una representación estructurada del comportamiento ONU (puertos, DHCP, filtros, flows, security-mng, WiFi).
3. Renderizar CLI a partir de esa estructura y la plantilla `template_body`.
4. Guardar `generated_cli` en `ProvisioningPlan` y, tras ejecución, actualizar `Onu` + `raw_pon_onu_mng`.

---

## 7. Riesgos y controles

### 7.1. Riesgos pendientes

1. **Desalineación entre `raw_pon-onu-mng` y modelo estructurado**
   - Si la OLT se modifica manualmente fuera de TOI, el bloque importado puede no coincidir con el último `ProvisioningPlan`.
   - Mitigación: mantener `raw_pon_onu_mng` como fuente para auditoría, y dejar claro en UI si la ONU fue modificada manualmente fuera del sistema.

2. **Modos de servicio desconocidos (`mode_code = "unknown"`)**
   - ONUs históricas con configuraciones especiales o no estandarizadas quedarán en modo simple `Desconocido/importado`.
   - Mitigación: exigir selección explícita de un modo gestionado (Router/Bridge/Transparente/Híbrido) antes de reprovisionar desde TOI.

3. **Complejidad de modelos avanzados (híbridos por puerto)**
   - Modos híbridos pueden requerir configurar comportamientos distintos por puerto.
   - Mitigación: introducir modos híbridos adicionales dentro de `OnuServiceModeTemplate` por OLT y exponer su selección sólo en configuración avanzada.

### 7.2. Controles recomendados

- Validar siempre que `OnuServiceModeTemplate.olt_id == ProvisioningPlan.olt_id`.
- Validar que todos los IDs referenciados en `ProvisioningPlan` (VLAN, perfiles, zonas, NAPs, tipos ONU) pertenecen a la misma OLT.
- Incluir el bloque `pon-onu-mng` final en la preview de validación (`ProvisioningValidationResult.cli_preview`) como sólo lectura.

---

## 8. Recomendación para primera fase de implementación

Sin tocar aún código, se recomienda que la **primera fase técnica** de este modelo se enfoque en:

1. **Documentar explícitamente en código y comentarios** la separación de responsabilidades:
   - `OnuType` = capacidades físicas.
   - `OnuServiceModeTemplate` = comportamiento ONU por OLT.
   - `Onu` = estado actual.
   - `ProvisioningPlan` = estado objetivo.

2. **Exponer en la ficha ONU (modo sólo lectura)** una sección "Comportamiento ONU" que muestre, reutilizando datos actuales:
   - `service_mode_code` mapeado a modo simple (Router / Bridge / Transparente / Híbrido / Desconocido).
   - VLAN WAN/servicio (`Onu.vlan` + nombre de `Vlan`).
   - Perfiles de velocidad (`speed_profile_up` / `speed_profile_down`).

3. **Planificar el almacenamiento de `raw_pon_onu_mng`** por ONU como parte de la auditoría, sin permitir edición.

Pasos siguientes (fases posteriores) pueden abordar la vista avanzada estructurada y la regeneración completa del bloque `pon-onu-mng` desde parámetros estructurados.
