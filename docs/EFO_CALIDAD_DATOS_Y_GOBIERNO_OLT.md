# Especificación Funcional Oficial

## Calidad de Datos, Catálogos Técnicos y Gobierno de OLT

Versión: 1.0  
Fecha: 2026-06-21  
Ámbito: Proyecto TOI OLT Manager (ZTE C300)

---

## 1. Principios rectores

### 1.1. OLT como raíz del inventario técnico

1. **Toda ONU pertenece a una única OLT**
   - Cada registro de ONU está asociado a un `olt_id`.
   - La identidad lógica de una ONU se define por la combinación `olt_id + serial_number`.
   - Ninguna ONU puede moverse entre OLTs sin un proceso explícito de migración.

2. **Todo catálogo técnico pertenece a una OLT**
   - VLANs, tipos de ONU, perfiles GPON, catálogos de velocidad, zonas, NAPs, puertos de NAP, PON y uplinks son **propiedad de una sola OLT**.
   - La pertenencia se expresa mediante `olt_id` y, cuando procede, `olt_code_snapshot` para preservar el contexto histórico.

3. **Toda provisión pertenece a una OLT**
   - Todo `ProvisioningPlan` tiene un `olt_id` explícito.
   - Las plantillas de modo de servicio (`OnuServiceModeTemplate`) se definen por OLT.
   - La ejecución de comandos en OLT se limita a la OLT indicada en el plan.

4. **Toda sincronización pertenece a una OLT**
   - Monitoreos, lecturas de potencia, importaciones iniciales y snapshots se asocian a una OLT concreta (`olt_id`).
   - Los jobs de importación (`ImportJob`) y snapshots (`ConfigSnapshot`) se identifican siempre junto a su `olt_id`.

### 1.2. Regla principal de aislamiento por OLT

> **Regla de oro:** Ninguna entidad técnica puede consumir información técnica perteneciente a otra OLT.

**Implicaciones prácticas:**

- Una ONU de `OLT-PCM-ZTE-01` **no puede**:
  - Usar una NAP de `OLT-LAB-ZTE-01`.
  - Usar una VLAN definida en otra OLT.
  - Usar un perfil de velocidad o modo de servicio (`OnuServiceModeTemplate`) definido para otra OLT.

- Un `ProvisioningPlan` para `OLT-PCM-ZTE-01` **no puede**:
  - Referenciar zonas, NAPs, VLANs o perfiles cuyo `olt_id` no coincida con el del plan.

- Cualquier nueva funcionalidad que introduzca catálogos compartidos deberá hacerlo **en tablas maestras explícitas** (por ejemplo, un catálogo global de plantillas de CLI por vendor/model), claramente separadas de las tablas `*_by_olt`.

**Consecuencias de romper esta regla:**

- Inconsistencias topológicas: ONUs ubicadas en zonas/NAPs de otras OLTs.
- Riesgo de provisión incorrecta: uso de VLANs o perfiles no válidos en la red física correspondiente.
- Dificultad para auditar y depurar incidentes: la trazabilidad por OLT se rompe.

Este documento asume la regla de aislamiento por OLT como **invariante no negociable** para todas las decisiones de calidad de datos y catálogos técnicos.

---

## 2. Catálogos técnicos

Esta sección documenta el alcance, relación con OLT, riesgos actuales y reglas recomendadas para cada catálogo técnico.

### 2.1. Tabla de auditoría de catálogos

| Entidad                | Tiene `olt_id` | Debe tener `olt_id` | Riesgo actual                                                                                                       | Recomendación                                                                                                                  |
|------------------------|----------------|---------------------|---------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------|
| **Olt**                | N/A (raíz)     | N/A                 | —                                                                                                                   | Fuente de verdad. Todas las demás entidades técnicas deben enlazar directa o indirectamente con `olt_id`.                      |
| **Zone**               | Sí (nullable)  | **Sí, no nulo**     | `olt_id` nullable permite zonas huérfanas o confusas entre OLTs si se insertan sin cuidado.                        | Tratar `olt_id` como obligatorio de facto. Validar siempre que `zone.olt_id == onu.olt_id` y que no existan zonas compartidas. |
| **Nap**                | Sí (nullable)  | **Sí, no nulo**     | Igual que `Zone`. Además, `zone_id` podría apuntar a una zona de otra OLT sin validación adicional.                | Exigir que `nap.olt_id` coincida con `zone.olt_id` y con la OLT de las ONUs asociadas.                                        |
| **NapPort**            | Sí (nullable)  | **Sí, no nulo**     | Un `NapPort` podría carecer de `olt_id` explícito o quedar asociado a una ONU de otra OLT.                         | Alinear `nap_ports.olt_id` con `naps.olt_id`. Validar que toda ONU que use un NapPort pertenece a la misma OLT.               |
| **Vlan**               | Sí             | Sí                  | Correctamente scoped (`olt_id` + `vlan_id`). Riesgo de uso cruzado sólo si un servicio omite filtrar por OLT.      | Mantener diseño. Asegurar que toda ONU/plan utilice VLANs correspondientes a su OLT.                                           |
| **OnuType**            | Sí             | Sí                  | Scoped por OLT (`olt_id` + `name`). Posible confusión si se utilizan tipos de otra OLT en validaciones.            | Mantener modelo. Al resolver tipos de ONU, siempre filtrar por `olt_id`.                                                       |
| **GponProfile**        | Sí             | Sí                  | Scoped por OLT. Sin riesgo directo, sirve como input para catálogos de servicio.                                   | Mantener. Usar siempre perfiles de la misma OLT al generar catálogos y `SpeedProfile`.                                        |
| **ProfileCatalog**     | Sí             | Sí                  | Scoped por OLT. Riesgo: asociar catálogos de otra OLT a planes si no se valida.                                     | Garantizar que `profile_catalog.olt_id == plan.olt_id` en validaciones de provisión.                                           |
| **SpeedProfile**       | Sí             | Sí                  | Scoped por OLT. Podría referenciar perfiles de otra OLT si se asigna mal el ID en `ProvisioningPlan`.              | Asegurar en servicio que `speed_profile.olt_id == plan.olt_id`.                                                               |
| **PonPort**            | Sí             | Sí                  | Scoped por OLT. Riesgo si `Onu.pon_port_id` apunta a un puerto de otra OLT.                                         | Validar siempre `onu.olt_id == pon_port.olt_id`.                                                                               |
| **OltUplink**          | Sí             | Sí                  | Scoped por OLT. Riesgo bajo de cross-OLT, se usa principalmente para monitoreo.                                    | Mantener. No reutilizar uplinks entre OLTs.                                                                                    |
| **OnuServiceModeTemplate** | Sí        | Sí                  | Scoped por OLT. Si se usa una plantilla de otra OLT, se pueden aplicar VLANs/perfiles equivocadas.                 | Validar `service_mode_template.olt_id == plan.olt_id` antes de usarla en provisión.                                           |
| **ProvisioningTemplate**   | No        | No (global controlado) | Plantilla global por vendor/model. Riesgo de no contemplar variaciones específicas por OLT.                      | Mantener global por vendor/model. Documentar que no debe contener IDs de catálogos específicos de una OLT.                    |
| **ProvisioningPlan**       | Sí        | Sí                  | `olt_id` presente, pero no se fuerza que los IDs de zona/NAP/VLAN/perfiles pertenezcan a la misma OLT.             | Definir obligación: toda referencia técnica contenida en el plan debe ser de la misma OLT. Validar en capa de servicio.       |

### 2.2. Reglas recomendadas por catálogo

1. **Zone / Nap / NapPort**
   - Cada OLT tiene su árbol `Zone` → `Nap` → `NapPort` independiente.
   - Está prohibido reutilizar zonas/NAPs entre OLTs.
   - Cualquier herramienta de edición debe forzar que:
     - `zone.olt_id == nap.olt_id == nap_port.olt_id == onu.olt_id`.

2. **Vlan**
   - Cada VLAN tiene significado únicamente dentro de su OLT.
   - Misma `vlan_id` en dos OLT distintas son entidades diferentes.
   - Los formularios de selección de VLAN deben estar siempre filtrados por `olt_id`.

3. **OnuType, GponProfile, ProfileCatalog, SpeedProfile**
   - Son catálogos técnicos por OLT que definen capacidades y perfiles de servicio.
   - `ProvisioningPlan` sólo puede utilizar valores cuyo `olt_id` coincide con el del plan.
   - Para futuras extensiones multi-vendor, cualquier catálogo global debe definirse en tablas separadas (por ejemplo, `global_onu_type_templates`) y proyectarse a instancias por OLT.

4. **PonPort / OltUplink**
   - Representan la capa física propia de cada OLT.
   - ONUs sólo pueden estar conectadas a PON ports de su OLT.
   - Reportes de backlog o saturación de uplinks deben respetar el `olt_id`.

5. **ProvisioningTemplate / OnuServiceModeTemplate / ProvisioningPlan**
   - `ProvisioningTemplate` es global a nivel vendor/modelo y define estructuras de CLI.
   - `OnuServiceModeTemplate` y `ProvisioningPlan` son **siempre por OLT**.
   - Un plan de provisión sólo es válido si todos sus campos técnicos se resuelven contra catálogos de la misma OLT.

---

## 3. Integridad cross-OLT

### 3.1. Escenarios de riesgo

1. **ONU PCM-1 usando NAP PCM-2**
   - ONU (`olt_id=PCM-1`) con `nap_id` que apunta a `Nap(olt_id=PCM-2)`.
   - Consecuencia: mapa físico incoherente; herramientas de operación creerán que la ONU está en otra planta externa.

2. **ONU PCM-1 usando VLAN PCM-2**
   - ONU con `vlan` que sólo está configurada en otra OLT.
   - Consecuencia: provisión CLI podría funcionar (si la VLAN existe también en PCM-1), pero las políticas y reportes serán inconsistentes.

3. **ONU PCM-1 usando perfil PCM-2**
   - Uso de `SpeedProfile` o `ProfileCatalog` de otra OLT.
   - Consecuencia: se rompe la referencia entre perfiles contractuales y configuración real.

4. **ONU PCM-1 usando plantilla PCM-2**
   - Plantilla global (`ProvisioningTemplate`) no representa un problema cross-OLT por diseño, siempre que no cargue IDs específicos.

### 3.2. Matriz de riesgos

| Relación                           | Validaciones actuales (implícitas)                         | Validaciones faltantes                                   | Riesgo operativo                                      |
|------------------------------------|------------------------------------------------------------|---------------------------------------------------------|-------------------------------------------------------|
| ONU ↔ Zone/Nap/NapPort            | Scoping por `olt_id` en migraciones y servicios conocidos | Verificación sistemática `onu.olt_id == zone/nap.olt_id` | Medio: incoherencia de planta externa si se rompe.    |
| ONU ↔ PonPort                     | Asociaciones construidas por import/monitoreo             | Falta de check explícito en futuras altas manuales      | Medio: ONU “colgada” de un PON errado.               |
| ONU/Plan ↔ VLAN                   | Filtros habituales por `olt_id`                           | Validación formal en `ProvisioningService.validate`     | Medio: provisión con VLAN no esperada.               |
| Plan ↔ OnuType/Profiles/Speed     | Servicios suelen filtrar por `plan.olt_id`                | Consolidad validación y errores explícitos por cross-OLT | Bajo-medio: degradación de gobernanza de servicio.    |
| Plan ↔ ServiceModeTemplate        | Scoped por OLT                                            | Verificación centralizada `template.olt_id == plan.olt_id` | Bajo: si se usa erróneamente, CLI podría seguir siendo válido pero no gobernado. |

### 3.3. Reglas de integridad recomendadas

1. Toda operación que cree o modifique **ONUs** debe comprobar:
   - Si `zone_id` se informa: `zones.olt_id == onus.olt_id`.
   - Si `nap_id` se informa: `naps.olt_id == onus.olt_id`.
   - Si `pon_port_id` se informa: `pon_ports.olt_id == onus.olt_id`.

2. Toda operación sobre **ProvisioningPlan** debe validar:
   - `zone_id`, `nap_id`, `speed_profile_id`, `upload_profile_id`, `download_profile_id`, `service_mode_template_id` pertenecen a `olt_id` del plan.
   - La VLAN seleccionada existe para esa OLT (`Vlan.olt_id == plan.olt_id`).

3. Cualquier nueva entidad técnica debe declararse explícitamente como:
   - `by_olt` (requiere `olt_id`), o
   - `global` (no tiene `olt_id` y no debe contener referencias a catálogos por OLT).

---

## 4. Calidad documental de ONUs

### 4.1. Estados propuestos

1. **`complete`**
   - Definición: ONU con información documental suficiente para operación, provisión y reporting sin ambigüedades.
   - Requisitos mínimos cumplidos: nombre cliente, zona, dirección, NAP, puerto de NAP, tipo ONU, VLAN, perfiles de subida y bajada consistentes.

2. **`needs_review`**
   - Definición: ONU operativa con datos suficientes para provisión, pero con advertencias documentales (ej. sin ODB, sin EXTID, sin AUTHD).
   - Criterio: faltan datos no críticos para provisión pero valiosos para auditoría o georreferenciación.

3. **`legacy_incomplete`**
   - Definición: ONU importada desde sistemas heredados (SmartOLT / running-config) con metadatos clave ausentes o ambiguos.
   - Criterio: faltantes en zona/NAP/puerto/dirección/EXTID/AUTHD detectados durante el parseo, o presencia de múltiples warnings de `legacy_incomplete`.

4. **Estado opcional `blocked`**
   - Definición: marcador interno para impedir que una ONU específica sea usada como base para nuevas provisiones (p.ej. conflictos de inventario, migraciones en curso).
   - No se aplica a ONUs heredadas ya en operación salvo decisión explícita.

### 4.2. Criterios de entrada/salida y efectos

| Estado            | Criterios de entrada                                                                                                 | Criterios de salida                                                                                          | Impacto operativo                                          |
|-------------------|----------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------|
| `complete`        | Todos los campos mínimos presentes y coherentes.                                                                    | Si se elimina algún dato mínimo → `needs_review` o `legacy_incomplete`.                                     | Operación, monitoreo y provisión sin restricciones.       |
| `needs_review`    | Campos mínimos para provisión presentes, pero faltan datos no críticos (ODB, EXTID, AUTHD, etc.).                  | Al completar todos los campos recomendados → `complete`.                                                    | Provisión permitida; interfaz muestra advertencias.       |
| `legacy_incomplete` | ONU proviene de import heredada con múltiples warnings (`missing descr/address`, `missing zone`, etc.).         | Cuando un operador complete manualmente los faltantes críticos → `needs_review` o `complete`.              | Provisión y monitoreo permitidos según política; se debe priorizar saneamiento. |
| `blocked`         | Asignado manualmente o por lógica de negocio cuando la ONU no debe recibir nuevas provisiones.                     | Sólo por intervención explícita tras resolver el motivo de bloqueo.                                         | Bloqueo de provisión; monitoreo e inventario siguen activos. |

### 4.3. Impactos por estado

- **Monitoreo**: nunca se bloquea por estado de calidad (`complete`, `needs_review`, `legacy_incomplete`, `blocked`).
- **Provisión**:
  - `complete`: siempre permitido.
  - `needs_review`: permitido con advertencias visibles en validación.
  - `legacy_incomplete`: configurable; por defecto, permitir provisión de corrección siempre que el plan complete los campos críticos.
  - `blocked`: no permitir aprobación/ejecución de planes.
- **Inventario**:
  - Todos los estados se muestran; `data_quality_status` funciona como etiqueta para reports y filtros.

---

## 5. Estrategia de saneamiento

### 5.1. Campos a normalizar

- **Zona**: `zone_id`, `parsed_zone_name`, `zone_name`.
- **NAP**: `nap_id`, `parsed_nap_name`, `nap_name`.
- **Puerto NAP**: `nap_port` (numérico), `nap_port_label`, `parsed_nap_port`.
- **Dirección**: `address_reference`, `description_generated`, `technician_notes`.
- **EXTID**: `external_id`, warnings de `missing extid`.
- **AUTHD**: `auth_date`, warnings `missing authd` o `authd token without yyyymmdd date`.
- **ODB/ODN**: `parsed_odn`, `odb_name`.

### 5.2. Detección de faltantes

- Combinar:
  - Campos `parsed_*` y campos estructurados en `Onu`.
  - Lista `description_parse_warnings` y `legacy_incomplete` de `RunningConfigParseResult`.
- Definir un evaluador de calidad que marque explícitamente qué campos faltan por ONU.

### 5.3. Priorización de correcciones

Orden sugerido de trabajo:

1. ONUs `legacy_incomplete` sin zona o con `SIN_ZONA`.
2. ONUs sin NAP/puerto (afecta catastro de planta externa).
3. ONUs sin dirección (afecta localización de cliente).
4. ONUs sin EXTID/AUTHD (afecta correlación con sistemas comerciales y antigüedad del servicio).
5. ONUs sin ODB/ODN (afecta trazabilidad completa OLT → ODB → NAP → cliente).

### 5.4. Registro de correcciones

- Toda corrección manual debería:
  - Mantener `description_original` y `raw_description` intactas para trazabilidad histórica.
  - Registrar cambios estructurados en `zone_id`, `nap_id`, `nap_port`, `address_reference`, `external_id`, etc.
  - Opcionalmente, guardar notas de saneamiento en `technician_notes` o en un log de eventos de ONU.

### 5.5. Medición de avance

- Métricas por OLT:
  - Nº y % de ONUs en cada `data_quality_status`.
  - Nº de ONUs sin zona, sin NAP, sin puerto, sin dirección, sin EXTID, sin AUTHD, sin ODB.
  - Evolución temporal (tendencias de saneamiento).

### 5.6. No pérdida de información histórica

- Ningún proceso de saneamiento debe:
  - Sobrescribir la descripción original proveniente de OLT.
  - Borrar warnings históricos.
- Cualquier dato nuevo se añade en campos estructurados o notas de técnico, preservando la fuente heredada.

---

## 6. Altas nuevas de ONU

### 6.1. Política de alta obligatoria

Para ONUs nuevas (no heredadas), se consideran **obligatorios** los siguientes campos en el flujo de provisión:

1. **Nombre cliente**: identificador humano del abonado (`customer_name`).
2. **Zona**: `zone_id` (FK a `zones` de la misma OLT).
3. **Dirección o referencia**: `address_reference` y/o `address` no vacíos.
4. **NAP**: `nap_id`, consistente con `zone_id` y `olt_id`.
5. **Puerto NAP**: `nap_port` + coherencia con un `NapPort` válido.
6. **Tipo ONU**: `onu_type`, validado contra `OnuType` de esa OLT.
7. **VLAN**: `vlan`, validada contra `Vlan(olt_id, vlan_id)`.
8. **Perfil subida / bajada**: `speed_profile_up`, `speed_profile_down`, validados contra `SpeedProfile`/`ProfileCatalog` de la misma OLT.

Campos opcionales pero recomendados:
- `external_id` (EXTID comercial).
- `auth_date`.
- Comentarios técnicos (`technical_comment`, `notes`).

### 6.2. Validaciones frontend

- Formularios de provisión deberán:
  - Marcar estos campos como requeridos (`required`).
  - Ofrecer selectores para zona/NAP/VLAN/perfiles filtrados por OLT.
  - Validar formatos básicos (no cadenas vacías, enteros válidos en puerto, VLANs en rango permitido).

### 6.3. Validaciones backend

- Schemas Pydantic (p.ej. `ProvisioningPlanCreate`) deben tratar estos campos como obligatorios.
- En la lógica de servicio:
  - Verificar scoping por `olt_id` de todos los catálogos referenciados.
  - Rechazar altas que no cumplan los mínimos (con mensajes de error claros).

### 6.4. Validaciones previas a provisión

- `ProvisioningValidationResult` debe considerar **inválido** cualquier plan en el que falte uno de los campos mínimos.
- No se debe poder aprobar/ejecutar un `ProvisioningPlan` con `is_valid = False` por motivos de calidad documental.

### 6.5. Diferencia ONU heredada vs ONU nueva

- **ONU heredada:**
  - Origen: importación desde running-config/SmartOLT.
  - Puede ser `legacy_incomplete` y seguir operativa.
  - No se le aplica la política de alta estricta retroactivamente.

- **ONU nueva:**
  - Origen: plan de provisión creado en TOI OLT Manager.
  - Debe cumplir todos los campos obligatorios.
  - No se crea si las validaciones fallan; no puede nacer como `legacy_incomplete`.

### 6.6. Borradores y ONUs reales

- **No se permite** la creación de una entidad `Onu` real en inventario con información incompleta.
- Si el operador necesita guardar trabajo parcialmente completado (datos aún en construcción), debe hacerlo a través de un **`ProvisioningPlan` en estado `draft`**, nunca creando una ONU directamente.
- Una ONU sólo puede existir en inventario cuando todas las validaciones obligatorias de negocio y de catálogos técnicos se han satisfecho y el plan de provisión ha sido aprobado/ejecutado.
- El concepto de **borrador** aplica exclusivamente a `ProvisioningPlan` (y a otros artefactos de planificación), **no** a la entidad `Onu`.

---

## 7. Impacto en provisioning

### 7.1. ProvisioningPlan

- Se consolida como **única vía autorizada** para altas nuevas de ONU.
- Debe contener explícitamente:
  - `olt_id`, `zone_id`, `nap_id`, `nap_port`.
  - `onu_type`, `vlan`, `speed_profile_up`, `speed_profile_down`.
  - Enlaces a `SpeedProfile`, `ProfileCatalog`, `OnuServiceModeTemplate` cuando aplique.

### 7.2. ProvisioningValidationResult

- Debe evaluar:
  - Integridad técnica (CLI, puertos libres, compatibilidad con PON/cards).
  - Integridad documental (campos mínimos, scoping por OLT, consistencia con catálogos).
  - Estado de calidad de la ONU objetivo (si es una modificación).

### 7.3. ProvisioningTemplate

- Se mantiene como catálogo global por vendor/model.
- Puede permanecer como catálogo global únicamente si **no contiene referencias técnicas específicas de una OLT**.
- Está prohibido almacenar dentro de `ProvisioningTemplate` referencias directas a catálogos dependientes de OLT, tales como:
  - VLAN IDs (numéricos o etiquetas que impliquen una VLAN concreta de una OLT).
  - Zone IDs.
  - Nap IDs.
  - NapPort IDs.
  - Profile IDs.
  - SpeedProfile IDs.
  - Cualquier otra clave foránea o identificador que dependa de una OLT concreta.
- `ProvisioningTemplate` sólo puede contener **estructura CLI genérica** y **placeholders** (por ejemplo, `{{vlan}}`, `{{zone_name}}`, `{{nap_name}}`) que se rellenan en tiempo de generación a partir de un `ProvisioningPlan` válido para una OLT.

### 7.4. Bloqueos y compatibilidad

- **Bloqueos de provisión:**
  - Plan inválido (`is_valid=False`) por documentación incompleta → no se permite aprobar ni ejecutar.
  - ONU `blocked` → no se permite generar nuevos planes contra ella.

- **Compatibilidad con ONUs heredadas:**
  - Se permite crear planes para ONUs heredadas siempre que el plan aporte datos suficientes para remediar la incompletitud (por ejemplo asignando NAP/puerto y VLAN correctos).
  - Alternativamente, se puede forzar saneamiento previo de ONU antes de generar planes.

---

## 8. Dashboard de calidad documental

### 8.1. Concepto “Calidad de Datos”

Se propone un módulo de UI dedicado a calidad documental por OLT.

**Indicadores principales por OLT:**
- Total ONUs.
- Nº y % `complete`.
- Nº y % `needs_review`.
- Nº y % `legacy_incomplete`.
- Gráficos de tendencias (evolución de estados en el tiempo).

### 8.2. Filtros recomendados

- Por tipo de faltante:
  - Sin Nombre.
  - Sin Zona / en `SIN_ZONA`.
  - Sin NAP.
  - Sin Puerto de NAP.
  - Sin Dirección.
  - Sin EXTID.
  - Sin AUTHD.
  - Sin ODB/ODN.

- Por `data_quality_status`.
- Por zona/NAP.

### 8.3. Mockup textual

**Cabecera:**

- Selector de OLT: `[ OLT-PCM-ZTE-01 ▾ ]`
- Resumen: `557 ONUs · 320 complete · 150 needs_review · 87 legacy_incomplete`

**Sección “Indicadores”:**

- Tarjeta 1: `Calidad documental global: 68% complete`
- Tarjeta 2: `ONUs sin NAP/Puerto: 186`
- Tarjeta 3: `ONUs en SIN_ZONA: 4`
- Tarjeta 4: `ONUs sin dirección: 115`

**Sección “Filtros avanzados”:**

- [x] Mostrar sólo `legacy_incomplete`
- [ ] Sin Nombre
- [x] Sin NAP
- [x] Sin Puerto
- [ ] Sin Dirección
- [ ] Sin EXTID
- [ ] Sin AUTHD

**Tabla “ONUs a normalizar”:**

| ONU interface   | Cliente                        | Zona       | NAP        | Puerto | Faltantes                         | Estado             |
|-----------------|--------------------------------|------------|-----------|--------|-----------------------------------|--------------------|
| gpon-onu_1/2/3:6| Diego_Fernando_Huanca_Tito    | Lagunas    | —         | —      | Zona (implícita), NAP, Puerto, ODB | legacy_incomplete  |
| gpon-onu_1/2/10:49 | Juan_Carlos_Quispe_Condori | SIN_ZONA   | —         | —      | Zona, NAP, Puerto, Dirección      | legacy_incomplete  |

Cada fila incluye acción “Editar” que abre un formulario pre-rellenado para normalizar zona/NAP/puerto/dirección sin perder la descripción original.

---

## 9. Ciclo de vida de OLT

### 9.1. Estados actuales

- `draft`
- `connection_tested`
- `preview_created`
- `confirmed`
- `failed`
- `cancelled`

### 9.2. Estados propuestos adicionales

- `archived`: OLT fuera de servicio, sólo lectura, datos preservados.
- `retired`: OLT definitivamente retirada; los datos se mantienen para auditoría a largo plazo.

### 9.3. Transiciones válidas (conceptuales)

- `draft` → `connection_tested` → `preview_created` → `confirmed`.
- `draft`/`connection_tested`/`preview_created` → `failed`/`cancelled`.
- `confirmed` → `archived` → `retired`.

### 9.4. Transiciones prohibidas

- Volver de `confirmed` a `draft`.
- Volver de `archived`/`retired` a estados operativos sin un proceso de “reactivación” explícito (si se permite).

### 9.5. Reglas operativas por estado

- `draft` / `connection_tested` / `preview_created` / `failed` / `cancelled`:
  - Importación inicial no confirmada o abortada.
  - Es aceptable borrar la OLT física y todos sus datos asociados (previa confirmación manual).

- `confirmed`:
  - OLT productiva o históricamente relevante.
  - **Eliminación física prohibida**.
  - Sólo pueden aplicarse cambios operativos (nuevas ONUs, ajustes de catálogos) o transición a `archived`.

- `archived` / `retired`:
  - OLT fuera de servicio.
  - No se permiten nuevas provisiones ni cambios de catálogos.
  - Los datos se conservan para reporting y auditoría.

---

## 10. Política de eliminación de OLT

### 10.1. Eliminación física permitida

- Estados: `draft`, `connection_tested`, `preview_created`, `failed`, `cancelled`.
- Impacto esperado:
  - ONUs asociadas: se consideran de laboratorio/test y se eliminan con la OLT.
  - VLANs, Zonas, NAPs, PONs, Uplinks, Snapshots, ImportJobs, EventLogs, DriverLogs: se eliminan en cascada.
  - Si la OLT se encuentra en estado `preview_created`, la eliminación debe incluir **todos** los artefactos temporales generados durante el proceso de importación inicial: snapshots capturados, resultados de parseo, previews de importación y logs temporales asociados a dicho flujo (`ImportJob`, `ConfigSnapshot`, resultados de parseo en tablas auxiliares, archivos intermedios si existieran, etc.).
  - El objetivo es **evitar residuos operativos** (jobs huérfanos, snapshots sin OLT, previews colgantes y cualquier otro artefacto de importación sin OLT asociada) que puedan generar inconsistencias o confusión futura.

### 10.2. Eliminación física prohibida

- Estados: `confirmed`, `archived`, `retired`.
- En estos estados sólo se permiten:
  - Desactivación parcial (por ejemplo, suspender monitoreo periódico).
  - Exportación de datos.
  - Transición `confirmed` → `archived` → `retired`.

### 10.3. Impacto por tipo de entidad

Al eliminar físicamente una OLT en estados permitidos:

- **ONUs**: se borran; no debe hacerse sobre OLTs confirmadas en producción.
- **VLANs, Zonas, NAPs, PONs, Uplinks**: se borran; sólo aceptable en entornos de lab/test.
- **Snapshots, ImportJobs**: se borran o se archivan afuera de la base de datos (backups).
- **EventLogs, DriverCommandLog, MonitoringExecution**: logs asociados se eliminan; es aceptable para OLTs de lab/test.

Para OLTs `confirmed/archived/retired`, la política recomendada es **no eliminar físicamente**;
en su lugar, aplicar archivado lógico y definir políticas de retención de backups.

---

## 11. Roadmap de implementación

### Fase A – Calidad documental

- **Objetivo:** introducir `data_quality_status`, evaluación de calidad y reporting básico.
- **Complejidad:** media (nueva semántica y endpoints de lectura).
- **Impacto:** alto en visibilidad de problemas, sin cambios operativos inmediatos.
- **Riesgo:** bajo-medio, requiere criterios claros de clasificación.
- **Dependencias:** ninguna fuerte; se apoya en datos existentes.

### Fase B – Validaciones nuevas ONU

- **Objetivo:** endurecer la creación de planes y ONUs nuevas con campos mínimos obligatorios y scoping por OLT.
- **Complejidad:** media (schemas, servicios, mensajes de error).
- **Impacto:** alto en operación diaria; evita repetición del escenario SmartOLT.
- **Riesgo:** medio; exige comunicación clara con operadores antes del cambio.
- **Dependencias:** Fase A (para etiquetar calidad heredada y no mezclar conceptos).

### Fase C – Dashboard de saneamiento

- **Objetivo:** proporcionar herramientas de visualización y priorización de trabajo de limpieza.
- **Complejidad:** media-alta (frontend + endpoints de agregación).
- **Impacto:** alto en gobernanza de datos; facilita saneamiento progresivo.
- **Riesgo:** bajo-medio; cambios principalmente en UI y reporting.
- **Dependencias:** Fases A y B.

### Fase D – Gestión de ciclo de vida OLT

- **Objetivo:** formalizar estados `archived`/`retired` y políticas de eliminación.
- **Complejidad:** media (logística de estados, UI simplificada).
- **Impacto:** medio-alto en gobernanza de infraestructura.
- **Riesgo:** bajo-medio; requiere revisar procesos de operación antes de activarlo.
- **Dependencias:** Fases A–C, para tener datos y validaciones consolidadas.

### Fase E – Endurecimiento de base de datos

- **Objetivo:** reflejar invariantes de scoping por OLT en el esquema (por ejemplo, `Zone.olt_id` no nulo).
- **Complejidad:** alta (migraciones, posibles datos legacy que ajustar).
- **Impacto:** alto en robustez a largo plazo.
- **Riesgo:** moderado-alto; requiere inventario de datos existentes y plan de migración cuidadoso.
- **Dependencias:** Fases anteriores completadas y estables.
