# Especificación Funcional Oficial

## Normalización del Modelo ONU y `service_mode_code`

Versión: 1.0  
Fecha: 2026-06-23  
Ámbito: Proyecto TOI OLT Manager (ZTE C300)

---

## 1. Objetivo y alcance

Este documento define la **normalización del modelo ONU** a partir del running-config ZTE C300 (`pon-onu-mng`) y de los catálogos internos, con foco en:

1. Definición formal de `service_mode_code` y su clasificación en modos simples:
   - `router`
   - `bridge`
   - `transparent`
   - `unknown`
2. Separación estricta entre:
   - **Modo ONU** (comportamiento lógico por OLT y plantilla)
   - **Modo WAN** (VLAN WAN / servicio principal)
   - **Modo Puerto** (rol y modo de cada puerto ethernet / VEIP)
   - **VLANs** (catálogo técnico por OLT)
3. Modelo estructurado esperado para importar y representar el bloque `pon-onu-mng` desde el parser `pon-onu-mng` / `pon-onu-mng`+flows (origen: `pon-onu-mng` y secciones asociadas) hasta TOI OLT Manager.
4. Reglas de clasificación usando ejemplos reales auditados (ONU `1215`, `1217`, `1218`, `1227` del running-config de `OLT-PCM-ZTE-01`, según auditoría del 2026-06-18).
5. Asignación de atributos entre:
   - `Onu`
   - `OnuType`
   - `OnuServiceModeTemplate`
   - `ProvisioningPlan`
6. Confirmación de pertenencia OLT-específica para:
   - VLANs
   - Zonas
   - NAPs
   - Tipos ONU
   - Modos ONU (`OnuServiceModeTemplate`)

Este documento **no introduce cambios de código ni de esquema**, sólo fija contratos conceptuales y de datos que deberán respetarse en futuras implementaciones.

---

## 2. Definición formal de `service_mode_code`

### 2.1. Concepto

`service_mode_code` es un **identificador técnico por OLT** que clasifica el comportamiento de una ONU en cuanto a:

- Gestión IP (IPHost / VEIP)
- Origen del DHCP (`dhcp-ip` / `dhcp-ip ethuni`)
- Tratamiento de VLAN WAN/servicio (`vlan port ...`, `vlan-filter`, `vlan-filter-mode`)
- Flujos GEM/flows asociados (`flow mode`, `switchport-bind`, `switchport`)
- Seguridad y servicios de usuario (`security-mng`, `loop-detect`, `wifi`)

`service_mode_code` se materializa como un string estable en:

- `Onu.service_mode_code`: etiqueta histórica/importada de la ONU en inventario.
- `ProvisioningPlan.service_mode_code`: modo de servicio objetivo para planes nuevos.
- `OnuServiceModeTemplate.mode_code`: clave de plantilla de comportamiento por OLT y modo.

### 2.2. Modos simples normalizados

Se definen cuatro **modos simples** para UI y reporting, derivados de `service_mode_code`:

1. `router`
   - La ONU actúa como router CPE.
   - Hay **IPHost activo** y/o `dhcp-ip from-internet` desde la WAN hacia los puertos LAN.
   - La VLAN WAN/servicio se aplica a IPHost/flows, no directamente a los puertos físicos como bridge transparente.

2. `bridge`
   - La ONU actúa como bridge (CPE en modo puente) con VLAN WAN etiquetada.
   - No se utiliza IPHost para la conectividad principal del abonado.
   - La VLAN WAN/servicio se aplica como `vlan port eth_*/* mode tag vlan <WAN_VLAN>` o equivalente, y se encamina de forma transparente hacia el router del cliente.

3. `transparent`
   - La ONU actúa como bridge **sin VLAN de servicio explícita**, o con comportamiento que hace transparente la VLAN (ej. acceso plano o sin tagging gestionado por la OLT).
   - Puede usarse para escenarios especiales (p.ej. pruebas, NID transparente, túneles dedicados).

4. `unknown`
   - Modo no clasificado o importado donde el comportamiento no puede mapearse con seguridad a `router` / `bridge` / `transparent` a partir del running-config disponible.
   - Se usa como estado por defecto para ONUs heredadas con configuraciones atípicas o incompletas.

### 2.3. Mapeo `service_mode_code` → modo simple

Cada OLT define sus códigos concretos de modo, por ejemplo:

- `router_iphost`
- `bridge_tag_internet`
- `transparent_special`
- `legacy_smartolt_router`
- `legacy_smartolt_bridge`

La clasificación se realiza en dos pasos:

1. **Resolución de plantilla**
   - A partir de `Onu.service_mode_code` y `Onu.olt_id` se resuelve la plantilla `OnuServiceModeTemplate` con la misma combinación (`olt_id` + `mode_code`).
   - Si no existe plantilla para el `service_mode_code` dado, el modo simple es `unknown`.

2. **Reglas de mapeo** (por OLT, pero con criterios generales):

   - Si `use_iphost = true` **y** `dhcp_source` ∈ {`from-internet`, `from-olt`} ⇒ **modo simple = `router`**.
   - Si `use_iphost = false` **y** existen reglas `vlan port eth_* mode tag vlan <X>` o flows GEM que sólo etiquetan una VLAN WAN para los puertos LAN ⇒ **modo simple = `bridge`**.
   - Si la plantilla marca explícitamente `vlan_mode = transparent` o equivalente, sin IPHost ⇒ **modo simple = `transparent`**.
   - Si ningún criterio anterior aplica de forma inequívoca ⇒ **modo simple = `unknown`**.

106 | > Nota: los nombres concretos de `mode_code` por OLT son libres mientras respeten el contrato anterior y se mantenga una tabla de mapeo estable a los modos simples.
107 | > "Híbrido" **no es** un quinto modo simple; se utiliza únicamente como concepto de configuración avanzada para describir combinaciones por puerto. Cualquier modo híbrido debe terminar proyectándose a uno de los cuatro modos simples (`router`, `bridge`, `transparent`, `unknown`).

---

## 3. Separación conceptual: Modo ONU vs WAN vs Puerto vs VLAN

### 3.1. Modo ONU

**Definición:** combinación de parámetros que determinan cómo se comporta una ONU a nivel de `pon-onu-mng` y bloques asociados:

- `service_mode_code` y plantilla `OnuServiceModeTemplate` asociados a la OLT.
- Parámetros de gestión IP (`use_iphost`, `use_veip`, índices de IPHost/VEIP, VLAN de gestión).
- DHCP (`dhcp-ip`, `dhcp-ip ethuni ...`), origen y segmentación.
- Flujos GEM (`flow`, `gemport-flow binding`) y VLAN filter (`vlan-filter-mode`, `vlan-filter`).
- Seguridad (`security-mng`, `loop-detect`, reglas firewall básicas, WiFi enable/disable).

El modo ONU **no** decide por sí mismo:

- Qué VLAN concreta se usará como servicio WAN (eso se parametriza en `ProvisioningPlan` / VLAN catálogo).
- Qué puerto físico se usará como LAN del cliente (eso es modo puerto).

### 3.2. Modo WAN

**Definición:** selección de la **VLAN de servicio principal** (WAN) que se asignará a la ONU, típicamente Internet residencial.

Parámetros clave:

- `Vlan.vlan_id` (entidad `Vlan` por OLT).
- En `ProvisioningPlan`: campo `vlan` y referencias internas a la VLAN de catálogo.

Reglas:

- Una ONU debe tener **una VLAN principal WAN/servicio** por plan de provisión.
- VLANs IPTV/VOIP pueden modelarse como VLANs adicionales, pero el modo simple (`router` / `bridge` / `transparent`) se refiere a la VLAN WAN principal.

### 3.3. Modo Puerto

**Definición:** distribución del modo de servicio sobre cada puerto físico/virtual de la ONU:

- Puertos ethernet (`eth_0/1`, `eth_0/2`, ...).
- Puertos VEIP (`veip 1`, ...).
- Asociaciones `switchport`, `switchport-bind`, `loop-detect`, `vlan port ...`.

Ejemplos de decisiones de modo puerto:

- Puertos LAN expuestos al cliente final (bridge o router).
- Puertos dedicados a IPTV o VOIP.
- Puertos deshabilitados.
154 | 
155 | Los valores como `access`, `hybrid`, `trunk` o `transparent` se consideran **modos de puerto**, no valores de `service_mode_code`.

### 3.4. VLANs

**Definición:** catálogo técnico por OLT, representado por la entidad `Vlan`:

- Identificado por `(olt_id, vlan_id)`.
- Puede llevar nombre (`vlan_name`) y clasificación adicional.

Regla de oro (EFO de Calidad):

> Misma `vlan_id` en dos OLT distintas representan **servicios distintos**; nunca se reutilizan catálogos VLAN entre OLTs sin una tabla global explícita.

---

## 4. Modelo estructurado esperado desde `pon-onu-mng`

### 4.1. Origen de datos

El parser ZTE C300 debe extraer, por ONU, un modelo estructurado a partir de:

- Bloque `pon-onu-mng gpon-onu_X/Y/Z:N` completo.
- Secciones relacionadas bajo ese contexto ONU:
  - `flow ...`
  - `vlan port eth_* ...`
  - `vlan-filter-mode ...`
  - `vlan-filter ...`
  - `dhcp-ip ...`
  - `switchport`, `switchport-bind`.
  - `security-mng ...`
  - `loop-detect ...`
  - `wifi ...` (si aplica).

### 4.2. Estructura esperada (conceptual)

Para cada ONU importada, se espera un bloque estructurado equivalente a:

```jsonc
OnuPonOnuMngModel {
  "olt_id": number,
  "onu_interface": "gpon-onu_1/2/3:1215",
  "serial_number": "...",
  "service_mode_code": "router_iphost" | "bridge_tag_internet" | "transparent_special" | "unknown" | string,
  "mode_simple": "router" | "bridge" | "transparent" | "unknown",

  // WAN principal (VLAN servicio)
  "wan_vlan_id": number | null,

  // Gestión IP / DHCP
  "use_iphost": boolean,
  "iphost_index": number | null,
  "use_veip": boolean,
  "veip_index": number | null,
  "dhcp_source": "from-onu" | "from-internet" | "none" | string,

  // VLAN filter / flows
  "vlan_filter_enabled": boolean,
  "vlan_filter_rules": [
    {
      "iphost_index": number,
      "priority": number,
      "vlan_id": number
    }
  ],

  "flows": [
    {
      "id": number,
      "mode": string,
      "gemport_id": number | null,
      "vlan_id": number | null
    }
  ],

  // Puertos ethernet / VEIP
  "ports": [
    {
      "name": "eth_0/1" | "eth_0/2" | "veip 1" | string,
      "role": "lan" | "iptv" | "voip" | "management" | "other",
      "mode": "access" | "tag" | "hybrid" | "transparent" | string,
      "primary_vlan_id": number | null,
      "extra_vlans": number[]
    }
  ],

  // Seguridad y WiFi
  "loop_detect": boolean,
  "wifi_disabled": boolean,

  // Información adicional del running-config
  "raw_pon_onu_mng": string
}
```

Esta estructura **no es un nuevo modelo de base de datos**; se concibe como DTO intermedio entre el parser y las entidades existentes (`Onu`, `OnuServiceModeTemplate`, `ProvisioningPlan`).

### 4.3. Normalización de `service_mode_code`

Durante la importación inicial:

1. El parser determina un identificador `service_mode_code_raw` a partir de patrones en `pon-onu-mng` y bloques asociados.
2. Se aplica una tabla de normalización por OLT:

   ```text
   service_mode_code_raw          →  service_mode_code (normalizado)
   ----------------------------------------------------------------
   router-smartolt-iphost         →  router_iphost
   bridge-smartolt-tag-internet   →  bridge_tag_internet
   transparent-lab-special        →  transparent_special
   <desconocido>                 →  unknown
   ```

3. `Onu.service_mode_code` se llena con el valor normalizado.
4. Si existe `OnuServiceModeTemplate` para (`olt_id`, `mode_code` = `service_mode_code`), se considera la ONU **clasificada**; en caso contrario, se etiqueta como `unknown` en `mode_simple`.

---

## 5. Reglas de clasificación con ejemplos reales (ONU 1215, 1217, 1218, 1227)

### 5.1. Contexto

En la auditoría `zte_c300_reimport_audit_2026-06-18.md` se identificaron múltiples bloques `pon-onu-mng` en `OLT-PCM-ZTE-01`. Para este documento se fijan reglas basadas en cuatro ONUs representativas:

- ONU interface `gpon-onu_1/2/3:1215`
- ONU interface `gpon-onu_1/2/3:1217`
- ONU interface `gpon-onu_1/2/3:1218`
- ONU interface `gpon-onu_1/2/3:1227`

> Nota: los números 1215, 1217, 1218, 1227 se usan como **identificadores de ONU en el contexto ZTE** (parte final de `gpon-onu_X/Y/Z:N`). No son IDs internos de TOI.

### 5.2. Reglas generales de clasificación

Para cada ONU se consideran los siguientes patrones:

1. **Modo router típico (SmartOLT heredado)**
   - Presencia de `iphost` con VLAN de servicio (`iphost 1 ... vlan X`).
   - Líneas `dhcp-ip ethuni eth_0/1 from-internet` o equivalentes.
   - `vlan-filter-mode iphost 1 ...` y `vlan-filter iphost 1 ... vid X`.
   - Puertos LAN en modo bridge hacia IPHost/flows.

   → `service_mode_code` normalizado: `router_iphost`  
   → `mode_simple`: `router`

2. **Modo bridge típico (SmartOLT heredado)**
   - Ausencia de IPHost como plano de datos principal.
   - Presencia de `vlan port eth_0/1 mode tag vlan X` o `switchport ...` que ligan el puerto LAN directamente a la VLAN WAN.
   - No hay reglas de DHCP desde la ONU; el CPE del cliente (router propio) asume esa función.

   → `service_mode_code` normalizado: `bridge_tag_internet`  
   → `mode_simple`: `bridge`

3. **Modo transparente especial**
   - Configuraciones de laboratorio o ONUs con puertos usados como NID/bridge sin filtrado específico.
   - Flujos `flow mode ...` que no permiten inferir con claridad una VLAN WAN única para Internet.

   → `service_mode_code` normalizado: `transparent_special`  
   → `mode_simple`: `transparent`

4. **Modo desconocido/importado**
   - Combinaciones atípicas, configuraciones manuales especiales o bloques incompletos.
   - Falta de mapeo en la tabla de `OnuServiceModeTemplate` por OLT.

   → `service_mode_code` normalizado: `unknown`  
   → `mode_simple`: `unknown`

### 5.3. Ejemplos ONU (casos de auditoría histórica, no normativos)

> Debido a que el documento de auditoría no enumera los bloques `pon-onu-mng` individuales, los siguientes ejemplos son **esquemáticos** y se basan en patrones típicos observados en ZTE C300 / SmartOLT.
> Corresponden a ONUs reales (`1215`, `1217`, `1218`, `1227`) del entorno `OLT-PCM-ZTE-01` usadas como referencia histórica, pero **no definen por sí mismas reglas normativas**.
> En la implementación, la clasificación debe apoyarse siempre en los bloques reales capturados y en las reglas generales de la sección 5.2.

#### 5.3.1. ONU 1215 — Router IPHost

Características esperadas:

- `iphost 1 ... vlan 200`.
- `dhcp-ip ethuni eth_0/1 from-internet`.
- `vlan-filter-mode iphost 1 ...` y `vlan-filter iphost 1 ... vid 200`.

Clasificación:

- `service_mode_code_raw`: `router-smartolt-iphost`.
- `service_mode_code`: `router_iphost`.
- `mode_simple`: `router`.

#### 5.3.2. ONU 1217 — Bridge VLAN tag internet

Características esperadas:

- No se usa `iphost` para el plano de datos.
- `vlan port eth_0/1 mode tag vlan 200`.
- Sin reglas `dhcp-ip` desde la ONU.

Clasificación:

- `service_mode_code_raw`: `bridge-smartolt-tag-internet`.
- `service_mode_code`: `bridge_tag_internet`.
- `mode_simple`: `bridge`.

#### 5.3.3. ONU 1218 — Router híbrido (router + IPTV)

Características esperadas:

- `iphost 1 ... vlan 200` (Internet).
- VLAN adicional para IPTV (`vlan 300` en flows/ports específicos).
- Reglas de `vlan-filter` múltiples.

Clasificación:

- `service_mode_code_raw`: `router-smartolt-iphost+iptv`.
- `service_mode_code`: `router_iphost` (misma familia de modo ONU, diferenciando sólo parámetros avanzados en plantilla).
- `mode_simple`: `router`.

#### 5.3.4. ONU 1227 — Transparente/lab

Características esperadas:

- Uso atípico de flows y puertos, sin VLAN WAN única claramente identificable.
- Escenario de laboratorio o pruebas especiales.

Clasificación:

- `service_mode_code_raw`: `lab-transparent-special`.
- `service_mode_code`: `transparent_special`.
- `mode_simple`: `transparent`.

---

## 6. Atributos por entidad

### 6.1. `Onu`

**Pertenece a OLT:** sí (`olt_id`).

Atributos relevantes para normalización de modelo ONU:

- Identidad y topología:
  - `olt_id`
  - `serial_number`
  - `onu_interface` (ej. `gpon-onu_1/2/3:1215`)
  - `onu_type` (nombre vinculado a `OnuType` de la misma OLT)
  - `zone_id`, `nap_id`, `nap_port`

- Servicio WAN / perfiles:
  - `vlan` (VLAN WAN principal de la ONU)
  - `speed_profile_up`
  - `speed_profile_down`

- Modo de servicio (histórico o efectivo):
  - `service_mode_code` (normalizado, string)
  - `behavior` (bloque de sólo lectura en API/UI que combina información de modo, VLAN y perfiles — ver EFO Modelo Operacional ONU)

- Calidad de datos:
  - `data_quality_status`
  - `data_quality_missing_fields`

### 6.2. `OnuType`

**Pertenece a OLT:** sí (`olt_id`).

Representa **capacidades físicas del equipo ONU**:

- Puertos físicos:
  - `ethernet_ports`
  - `wifi_ports`
  - `pots_ports`
  - `rf_ports`

- Límites técnicos:
  - `max_iphost`
  - `max_tcont`
  - `max_gemport`
  - Otros límites específicos ZTE.

- Metadatos de importación:
  - `olt_code_snapshot`
  - Fuente (`imported`, `manual`, etc.).

**No** contiene comportamiento de provisión (DHCP, flows, VLAN filter, etc.).

### 6.3. `OnuServiceModeTemplate`

**Pertenece a OLT:** sí (`olt_id`).

Representa **plantillas de comportamiento ONU por OLT y modo**:

- Identificación:
  - `olt_id`
  - `mode_code` (igual que `service_mode_code` normalizado)
  - `name`, `description`

- Parámetros de comportamiento:
  - `vlan_mode` (`tag`, `transparent`, `untag`)
  - `dhcp_source`
  - `use_iphost`
  - `use_veip`
  - `use_vlan_filter`
  - `use_loop_detect`
  - `disable_wifi`

- Plantilla CLI:
  - `template_body` (bloque parametrizado que representa `pon-onu-mng` + secciones asociadas)
  - `default_for_provisioning` (indicador de modo por defecto para nuevas ONUs).

Esta entidad es la **encargada principal de materializar `service_mode_code`** en CLI.

### 6.4. `ProvisioningPlan`

**Pertenece a OLT:** sí (`olt_id`).

Representa el **estado objetivo** de provisión de una ONU:

- Identidad y referencias:
  - `olt_id`
  - `unauthorized_onu_id` / `serial_number`
  - `pon_port_interface`

- Datos documentales obligatorios (EFO Calidad de Datos):
  - `customer_name`
  - `zone_id`
  - `nap_id`
  - `nap_port`
  - `address_reference`
  - etc.

- Decisiones operativas:
  - `onu_type` (ref. a `OnuType` de la misma OLT)
  - `service_mode_code` (ref. a `OnuServiceModeTemplate.mode_code` de la misma OLT)
  - `vlan` (VLAN WAN catálogo de la misma OLT)
  - `speed_profile_up`, `speed_profile_down` (perfiles de velocidad de la misma OLT)

- Resultado:
  - `generated_cli` (CLI completo generado a partir de `OnuType`, `OnuServiceModeTemplate`, catálogos y parámetros del plan)
  - `validation_result`, `preflight_checks`.

> Regla: `ProvisioningPlan` **no almacena** detalles de bajo nivel del `pon-onu-mng` (flows, vlan-filter, etc.); estos se generan a partir de las plantillas y parámetros estructurados.

---

## 7. Pertenencia OLT-específica (VLANs, Zonas, NAPs, Tipos ONU, Modos ONU)

Reforzando la EFO **Calidad de Datos, Catálogos Técnicos y Gobierno de OLT** y la EFO **Modelo Operacional de ONU**, se establecen las siguientes invariantes:

1. **VLANs**
   - Tabla `Vlan` siempre tiene `olt_id`.
   - Clave lógica: `(olt_id, vlan_id)`.
   - No se reutilizan VLANs entre OLTs.

2. **Zonas**
   - Tabla `Zone` siempre tiene `olt_id` (aunque en esquema actual pueda ser nullable, su uso se considera obligatorio).
   - Clave lógica: `(olt_id, name)`.
   - Una zona no puede referenciarse desde ONUs de otra OLT.

3. **NAPs y NapPorts**
   - `Nap` y `NapPort` llevan `olt_id`.
   - Relación: `nap.olt_id == zone.olt_id == onu.olt_id`.
   - Ningún `Nap` ni `NapPort` se comparte entre OLTs.

4. **Tipos ONU (`OnuType`)**
   - Cada `OnuType` pertenece a una OLT (`olt_id`, `name`).
   - No se usan tipos de una OLT en otra.

5. **Modos ONU (`OnuServiceModeTemplate`)**
   - Cada modo pertenece a una OLT (`olt_id`, `mode_code`).
   - Un `ProvisioningPlan` de `OLT-PCM-ZTE-01` sólo puede usar `OnuServiceModeTemplate` cuyo `olt_id` coincida.
   - `Onu.service_mode_code` **se interpreta siempre** en el contexto de su `olt_id`.

6. **Planes de provisión (`ProvisioningPlan`)**
   - Todo `ProvisioningPlan` referencia únicamente catálogos (`Vlan`, `Zone`, `Nap`, `NapPort`, `OnuType`, `OnuServiceModeTemplate`, perfiles) con el mismo `olt_id`.
   - Cualquier validación futura debe rechazar planes que mezclen catálogos de OLTs distintas.

---

## 8. Resumen operativo

1. `service_mode_code` es un identificador técnico por OLT que **siempre** se resuelve contra `OnuServiceModeTemplate`.
2. La UI y los reportes deben trabajar con los modos simples:
   - `router`
   - `bridge`
   - `transparent`
   - `unknown`
3. El parser estructurado de `pon-onu-mng` debe:
   - Extraer `service_mode_code` y parámetros de comportamiento.
   - Mapear a plantillas `OnuServiceModeTemplate` por OLT.
   - Respetar la separación entre modo ONU, modo WAN (VLAN), modo puerto y VLANs.
4. La asignación de atributos a entidades es:
   - `OnuType`: capacidades físicas (no comportamiento).
   - `OnuServiceModeTemplate`: comportamiento ONU por OLT y modo.
   - `Onu`: estado actual (incluye `service_mode_code` e información WAN/perfiles).
   - `ProvisioningPlan`: estado objetivo (incluye `service_mode_code`, `vlan`, perfiles y topología documental).
5. VLANs, Zonas, NAPs, Tipos ONU y Modos ONU son **siempre específicos de una OLT**.
