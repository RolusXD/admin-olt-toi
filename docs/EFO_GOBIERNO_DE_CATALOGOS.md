# Especificación Funcional Oficial

## Gobierno de Catálogos en Admin OLT TOI

Versión: 1.0  
Fecha: 2026-06-24  
Ámbito: Proyecto TOI OLT Manager (multi-OLT, multi-vendor, OSS FTTH)

---

## 1. Objetivo

Este documento define el **Gobierno de Catálogos** de Admin OLT TOI. Es la referencia arquitectónica permanente que regula:

- Gobierno de la información.  
- Clasificación oficial de catálogos.  
- Propiedad de los datos y de cada dominio.  
- Ciclo de vida de catálogos y datos asociados.  
- Reglas de aislamiento entre OLTs y dominios.  
- Reglas de importación, preview y confirmación.  
- Reglas de evolución al añadir nuevas OLTs, vendors y ciudades.  
- Principios arquitectónicos para la transición hacia un **OSS FTTH multi-OLT/multi-vendor**.

**Obligatoriedad:**

- Cualquier nuevo módulo, servicio, migración, parser, API o integración externa **debe respetar este documento**.  
- Las decisiones que entren en conflicto con esta EFO requieren una decisión arquitectónica explícita documentada en `ai-context/07_DECISIONS.md` y, si procede, una nueva versión de esta EFO.

Este documento **no describe sólo el estado actual**, sino las reglas oficiales que deben guiar la evolución del sistema a largo plazo.

---

## 2. Principios Fundamentales

1. **Un dato tiene un único propietario.**  
   - Cada pieza de información tiene un sistema/tabla/módulo responsable de su verdad canónica.  
   - Otros componentes sólo pueden consumir copias derivadas, nunca redefinir la verdad canónica.

2. **Un catálogo pertenece a un único dominio.**  
   - Ningún catálogo puede ser gestionado simultáneamente por varios dominios con reglas contradictorias.  
   - El dominio propietario define modelo, invariantes y políticas de evolución.

3. **Ningún objeto puede pertenecer simultáneamente a varias OLTs.**  
   - Cada entidad técnica o territorial con `olt_id` representa un recurso propio de esa OLT.  
   - No existen ONUs, VLANs, Zones, NAPs ni NapPorts compartidos entre OLTs.

4. **Los datos operativos nunca reemplazan los datos de inventario.**  
   - Métricas, estados, alarmas y mediciones no sobreescriben inventario ni catálogos; sólo aportan contexto y auditoría.

5. **Las importaciones descubren información.**  
   - El proceso de importación (snapshots, parsers) es un mecanismo de descubrimiento: observa el estado de la red y propone cambios.

6. **La confirmación consolida información.**  
   - Sólo tras una confirmación explícita (preview → apply) las propuestas se convierten en parte del inventario canónico.

7. **Todo cambio debe ser auditable.**  
   - Cualquier modificación relevante de inventario o catálogos debe dejar rastro: quién, cuándo, desde qué fuente y mediante qué plan.

8. **Toda automatización debe ser reversible.**  
   - Debe ser posible revertir o mitigar automáticamente cambios erróneos, ya sea mediante planes inversos, backups o estados previos.

9. **Preview antes de Apply.**  
   - Ningún cambio estructural en inventario o catálogos puede aplicarse sin un paso de preview claro y comprensible para el operador.

10. **La calidad de datos prevalece sobre la automatización.**  
    - En caso de duda, el sistema debe priorizar la consistencia y claridad documental frente a la automatización agresiva.
    - Las heurísticas pueden proponer, pero la decisión final sobre catálogo territorial e inventario debe poder ser humana.

---

## 3. Clasificación Oficial de Catálogos

Se definen cuatro grandes familias de catálogos:

1. **Catálogos Globales** (A).  
2. **Catálogos Técnicos por OLT** (B).  
3. **Catálogos Territoriales** (C).  
4. **Catálogos Operativos** (D).

### 3.A. Catálogos Globales

Definición: catálogos **independientes de una OLT concreta**, que modelan conceptos genéricos reutilizables por múltiples OLTs y vendors.

Ejemplos (no exhaustivos):

- Fabricantes (vendors) de equipos (ZTE, Huawei, Nokia, etc.).
- Modelos ONU genéricos (familias de hardware independientes de una OLT concreta).
- Tipos de splitter (1:8, 1:16, 1:32, 1:64, etc.).
- Tipos de conectores (SC/APC, SC/PC, LC, etc.).
- Marcas comerciales o líneas de producto. 
- Tecnologías soportadas (GPON, XG-PON, XGS-PON, 10G-EPON, etc.).

Para cada catálogo global se debe documentar:

- **Propietario:** dominio de Arquitectura / Catálogos Globales.  
- **Versionado:** versiones claras del catálogo (ej. v1, v2) cuando cambian reglas o campos.  
- **Historial:** cambios auditados (alta, modificación, deprecación).  
- **Importación:**
  - Puede provenir de fuentes externas (ficheros, APIs de vendors) pero el alta en el catálogo global es una decisión controlada.
  - Nunca se crean catálogos globales automáticamente desde estados casuales de la red.
- **Mantenimiento:**
  - Curado manual y excepciones aprobadas por Arquitectura.  
  - Políticas claras de obsolescencia (p.ej., marcar modelos como "deprecated" sin borrarlos).

### 3.B. Catálogos Técnicos por OLT

Definición: catálogos **específicos de una OLT**, que representan configuración técnica necesaria para provisión y monitoreo.

Ejemplos actuales:

- `Vlan` (VLANs de servicio).  
- `GponProfile` (perfiles GPON de bajo nivel).  
- `SpeedProfile` (perfiles de velocidad).  
- `ProfileCatalog` (catálogos agregados de servicio).  
- `OnuType` (capacidades de hardware ONU específicas por OLT/snapshot).  
- `PonPort` (puertos PON físicos).  
- `OltUplink` (uplinks físicos).  
- `OnuServiceModeTemplate` (modos de servicio ONU por OLT).  
- `ProvisioningTemplate` (plantillas CLI por vendor/modelo, lógicamente globales pero sin IDs por OLT).

Características:

- **Pertenecen a una OLT** (excepto `ProvisioningTemplate`, que es global controlado y no debe contener IDs de OLT).  
- **Pueden recrearse desde snapshots** (`show running-config`, inventario histórico) con reglas determinísticas y auditoría.  
- **Pueden versionarse**: es válido introducir nuevas versiones de perfiles, VLANs o modos de servicio manteniendo historial.

### 3.C. Catálogos Territoriales

Definición: catálogos que modelan **infraestructura física de planta externa** y su relación con la OLT.

Ejemplos:

- `Zone` (zonas operativas/comerciales por OLT).  
- `Nap` (incluyendo NAP/ODN/ODB, distinguidos por `type/prefix`).  
- `NapPort` (puertos de NAP/ODN/ODB).

Características:

- **Representan infraestructura física**: cajas, divisiones territoriales, puntos de distribución.  
- **Pertenecen a una OLT** (no son globales).  
- **Nunca son globales ni compartidos entre OLTs.**  
- **Requieren revisión humana**: las propuestas automáticas deben considerarse sugerencias.  
- **Preview obligatorio** antes de consolidar cambios territoriales.

### 3.D. Catálogos Operativos

Definición: catálogos y registros **dinámicos**, centrados en el estado operativo, historial y eventos.

Ejemplos:

- Estado de ONU (`Onu.status`, `signal_status`, etc.).  
- `OnuBehavior` (bloque de sólo lectura en API/UI).  
- Historial de potencia óptica (power history).  
- Alarmas y eventos (por OLT, ONU, puerto).  
- Tokens/documentos AUTHD (fechas de autenticación de servicio).  
- Etiquetas de calidad de datos (`data_quality_status`, `data_quality_missing_fields`).  
- Snapshots (`ConfigSnapshot`) e import jobs (`ImportJob`).  
- Metadatos de snapshot e importación (`snapshot_status`, `warnings`, `legacy_incomplete`).

Características:

- **Son dinámicos:** cambian frecuentemente con el tiempo.  
- **Se regeneran:** pueden reconstruirse desde lecturas periódicas o nuevas importaciones.  
- **Generan historial:** se prioriza registrar la evolución, no sólo el último estado.  
- **No representan inventario estático:** no son la fuente de verdad sobre la topología ni los catálogos técnicos.

---

## 4. Propiedad de cada catálogo

La siguiente tabla resume la propiedad y gobierno principales de los catálogos conocidos (listado conceptual; los nombres concretos de tablas pueden variar):

| Catálogo                    | Dominio principal           | Propietario            | Global / OLT         | Versionado         | Historial              | Autoimport        | Preview requerido | Apply (consolida) | Observaciones clave |
|-----------------------------|-----------------------------|------------------------|----------------------|--------------------|------------------------|-------------------|-------------------|-------------------|---------------------|
| **Vendor** (fabricante)     | Catálogos Globales         | Arquitectura           | Global (sin `olt_id`)| Sí (soft)          | Sí (alta/obsolescencia)| No automático     | N/A               | N/A               | Lista cerrada y curada manualmente. |
| **OnuModelTemplate** (HW)   | Catálogos Globales         | Arquitectura           | Global               | Sí                 | Sí                     | Parcial (desde fuentes externas) | Sí (para altas)   | Sí                | Define familias de ONU independientes de una OLT. |
| **SplitterType**            | Catálogos Globales         | Planta Externa         | Global               | Bajo               | Bajo                    | No automático     | N/A               | N/A               | Tipos estándar de planta externa. |
| **ConnectorType**           | Catálogos Globales         | Planta Externa         | Global               | Bajo               | Bajo                    | No automático     | N/A               | N/A               | SC/APC, LC, etc. |
| **Technology** (GPON/XGS)   | Catálogos Globales         | Arquitectura           | Global               | Raro               | Sí                     | No automático     | N/A               | N/A               | Define familias tecnológicas soportadas. |
| **Olt**                     | Inventario Lógico          | Operaciones / NOC      | Global (raíces)      | Sí                 | Sí (ciclo de vida)     | Semi-manual       | Sí (wizard)       | Sí                | Raíz de todo inventario por OLT. |
| **Vlan**                    | Técnico por OLT            | Operaciones / NOC      | OLT (`olt_id`)       | Opcional           | Sí (uso en planes)     | Sí (desde snapshot)| Sí (en preview)   | Sí                | Clave `(olt_id, vlan_id)`. |
| **GponProfile**             | Técnico por OLT            | Ingeniería de Red      | OLT                  | Sí                 | Sí                     | Sí (snapshot)     | Sí (por lote)     | Sí                | Base de SpeedProfiles y plantillas. |
| **SpeedProfile**            | Técnico por OLT            | Ingeniería / Comercial | OLT                  | Sí                 | Sí                     | Parcial           | Sí (cambios)      | Sí                | Ligado a perfiles contractuales. |
| **ProfileCatalog**          | Técnico por OLT            | Ingeniería / Comercial | OLT                  | Sí                 | Sí                     | No automático     | Sí                | Sí                | Agrupa perfiles de servicio. |
| **OnuType**                 | Técnico por OLT            | Ingeniería de Red      | OLT                  | Sí (por snapshot)  | Sí                     | Sí (snapshot)     | Sí (nuevos tipos) | Sí                | Capacidades físicas por OLT. |
| **PonPort**                 | Técnico por OLT            | Ingeniería de Red      | OLT                  | Bajo               | Sí (cambios físicos)   | Sí (snapshot)     | Sí (reconciliación)| Sí               | Puertos GPON físicos. |
| **OltUplink**               | Técnico por OLT            | Ingeniería de Red      | OLT                  | Bajo               | Sí                     | Sí (descubrimiento)| Sí               | Sí                | Uplinks y agregaciones. |
| **OnuServiceModeTemplate**  | Técnico por OLT            | Ingeniería / Arquitectura | OLT              | Sí                 | Sí                     | Semi-automático (desde parser) | Sí (nuevos modos) | Sí                | Comportamiento ONU por OLT y modo. |
| **ProvisioningTemplate**    | Técnico global (CLI)       | Arquitectura / Ingeniería| Global controlado  | Sí                 | Sí                     | No automático     | Sí                | Sí                | No debe contener IDs de catálogos por OLT. |
| **ProvisioningPlan**        | Operación / Provisión      | Operaciones            | OLT                  | Implícito (por plan)| Sí (ejecución)       | No automático     | Siempre           | Sí (ejecución)    | Única vía autorizada para nuevas ONUs. |
| **Zone**                    | Territorial                 | Planta Externa / NOC   | OLT                  | Bajo-medio         | Sí                     | Semi-automático (descubrimiento) | Sí (obligatorio) | Sí (tras revisión) | Nunca global, nunca compartida. |
| **Nap (NAP/ODN/ODB)**       | Territorial                 | Planta Externa         | OLT                  | Medio              | Sí                     | Semi-automático   | Sí (obligatorio) | Sí (tras revisión) | Prefijo (`NAP`/`ODN`/`ODB`) parte de la identidad. |
| **NapPort**                 | Territorial                 | Planta Externa         | OLT                  | Bajo               | Sí                     | Semi-automático   | Sí                | Sí                | No crear masivamente sin evidencia. |
| **Onu**                     | Inventario Lógico          | Operaciones / NOC      | OLT                  | Implícito          | Sí                     | Sí (import)       | Sí (nuevas altas) | Sí                | Estado actual de cada ONU en la OLT. |
| **OnuStatus / PowerHistory**| Operativo                   | Monitoreo              | Por OLT/ONU          | N/A                | Sí (series temporales)| Sí (monitoreo)    | N/A               | N/A               | No modifican inventario ni catálogos. |
| **Alarm / Event**           | Operativo                   | Monitoreo / NOC        | Por OLT/ONU          | N/A                | Sí (event log)        | Sí (runtime)      | N/A               | N/A               | No afectan catálogos. |
| **ConfigSnapshot**          | Operativo (import)          | Operaciones / Arquitectura | Por OLT         | N/A (inmutable)   | Sí (historial completo)| Sí (captura)     | Sí (antes de parseo) | N/A            | Snapshot es fuente de verdad de importación. |
| **ImportJob / SnapshotMeta**| Operativo (import)          | Operaciones            | Por OLT              | N/A                | Sí                     | Sí (workflow)     | Sí               | Sí (confirmación) | Controlan preview/confirm de import. |
| **DataQuality** (ONU)       | Operativo                   | Arquitectura / Operaciones | Por ONU        | N/A                | Sí                     | Sí (evaluador)    | N/A               | N/A               | Etiqueta estados `complete/needs_review/legacy_incomplete/blocked`. |

Esta tabla sirve como guía conceptual. El detalle de implementación puede distribuir algunos campos entre varias tablas, pero **la propiedad y el dominio no deben cambiar sin una decisión arquitectónica explícita**.

---

## 5. Ciclo de vida

### 5.1. Catálogos Globales

- **Crear:**
  - Alta manual o semiautomática, aprobada por Arquitectura.  
  - Debe incluir fuente, fecha y justificación.
- **Actualizar:**
  - Cambios controlados, normalmente aditivos (nuevos modelos, nuevas tecnologías).  
  - Evitar cambios destructivos sobre claves visibles.
- **Obsoleto:**
  - Marcar elementos como `deprecated` cuando ya no se usen en nuevas provisiones.
- **Eliminar:**
  - Sólo si no existen referencias históricas ni funcionales; preferible mantener registros obsoletos marcados.

### 5.2. Catálogos Técnicos por OLT

- **Importar:**
  - Desde snapshots confirmados o APIs read-only de vendor.  
  - Nunca desde una lectura parcial sin prompt estable.
- **Validar:**
  - Verificar scoping por `olt_id`, ausencia de duplicados y coherencia con catálogos globales.  
  - Separar errores críticos, warnings y `legacy_incomplete`.
- **Versionar:**
  - Permitir coexistencia de varios perfiles/plantillas con marcas de vigencia (activo/obsoleto).  
- **Activar:**
  - Declarar explícitamente qué versión o combinación de catálogos se considera activa para provisión.
- **Reemplazar:**
  - Cambiar gradual, preservando historial y evitando rupturas abruptas de servicio.

### 5.3. Catálogos Territoriales

- **Descubrir:**
  - A partir de descripciones heredadas, inventario externo (SmartOLT, GIS) y patrones de uso reales.  
  - Nunca asumir completitud sin evidencia.
- **Revisar:**
  - Revisión documental y de planta externa, combinando evidencia técnica y conocimiento de campo.
- **Preview:**
  - Generar propuestas de Zones/NAPs/NapPorts por OLT con niveles de confianza (`alta`/`media`/`baja`/`bloqueado`).
- **Confirmar:**
  - Confirmación humana y/o comité antes de consolidar catálogos territoriales.
- **Operar:**
  - Usar catálogos territoriales confirmados en provisión, reporting y planificación.
- **Expandir:**
  - Añadir nuevas zonas/NAPs mediante flujos controlados cuando se expande la red física.

### 5.4. Catálogos Operativos

- **Generar:**
  - A partir de monitoreo, importaciones, ejecuciones de planes y eventos externos.
- **Actualizar:**
  - Sobrescribir estado actual (ej. potencia ONU) manteniendo historiales separados cuando aplique.
- **Historial:**
  - Registrar series temporales y logs de eventos para auditoría y análisis.
- **Caducar:**
  - Definir políticas de retención (tiempo máximo de logs, snapshots históricos, etc.).
- **Eliminar:**
  - Purgar datos operativos caducados de forma controlada, sin afectar inventario ni catálogos.

---

## 6. Reglas de aislamiento

### 6.1. Global

- Catálogos globales **no tienen `olt_id`**.  
- No pueden contener referencias directas a IDs de catálogos por OLT (VLANs, Zones, NAPs, etc.).

### 6.2. Técnico por OLT

- Catálogos técnicos por OLT **siempre tienen `olt_id`**.  
- Una VLAN, perfil, tipo ONU o modo de servicio sólo es válido en el contexto de su `olt_id`.

### 6.3. Territorial

- Catálogos territoriales **siempre tienen `olt_id`**.  
- No se comparten entre OLTs ni se reutilizan registros para otra OLT.  
- **Nunca compartir, nunca reutilizar, nunca copiar automáticamente** zonas, NAPs o NapPorts de una OLT a otra.  
- Cualquier clonación debe materializarse como nuevos registros explícitos por OLT.

### 6.4. Operativo

- Datos operativos pertenecen:
  - A una **ONU** (`onu_id`),  
  - A una **OLT** (`olt_id`),  
  - A un **Snapshot** (`config_snapshot_id`),  
  - A un **evento** (`event_id`), o  
  - A un **ImportJob** (`import_job_id`).
- Nunca cambian la propiedad de catálogos ni inventario; sólo describen estado y evolución.

---

## 7. Reglas de importación

### 7.1. Qué puede crearse automáticamente

- Catálogos técnicos por OLT (VLANs, perfiles, tipos ONU, PON ports) **pueden** crearse automáticamente desde snapshots confirmados, siempre que:
  - Exista snapshot persistido y validado.  
  - Se respete scoping por `olt_id`.  
  - Se registre historial de cambios.

- ONUs pueden crearse desde importación inicial y descubrimiento, con etiquetas de calidad (`legacy_incomplete` cuando falte información).

### 7.2. Qué requiere Preview

- Cambios estructurales de inventario, incluyendo:
  - Alta masiva de ONUs.  
  - Cambios en catálogos técnicos (nuevas VLANs, nuevos perfiles) derivados de importaciones.  
  - Cambios propuestos en catálogos territoriales.

- El preview debe mostrar:
  - Diferencias entre estado actual y propuesto.  
  - Impacto esperado (nº de ONUs, planes afectados, etc.).

### 7.3. Qué requiere revisión humana

- Toda consolidación de **catálogos territoriales**.  
- Cambios que afecten a ONUs en producción (reasignación de NAP, zona, puerto).  
- Introducción de nuevos modos de servicio ONU (`OnuServiceModeTemplate`) derivados de patrones atípicos.

### 7.4. Qué nunca debe crearse automáticamente

- Zones, NAPs y NapPorts **definitivos** sin paso previo por preview y revisión.  
- Catálogos globales (vendors, modelos ONU globales, tecnologías).  
- Entradas históricas críticas (por ejemplo, eliminación/creación de snapshots ya confirmados).

Ejemplos:

- **Permitido automáticamente:** crear nuevas VLANs observadas en `show running-config` para una OLT de laboratorio, tras preview de cambios.  
- **Requiere revisión:** proponer nuevos NAPs PCM basados en descripciones con niveles de confianza.  
- **Prohibido:** crear NAP PCM copiando directamente NAPs LAB sin evidencia documental.

---

## 8. Reglas de eliminación

### 8.1. Restricciones estructurales

- **No eliminar Zone con NAPs asociadas.**  
  - Requiere reasignar o archivar previamente las NAPs y su impacto en ONUs.

- **No eliminar NAP con ONUs asociadas.**  
  - Debe realizarse un proceso de migración explícito de ONUs a otro NAP.

- **No eliminar VLAN usada.**  
  - Si una VLAN se usa en ONUs o ProvisioningPlans, debe marcarse como obsoleta pero no borrarse.

- **No eliminar SpeedProfile usado.**  
  - Análogo a VLAN; se recomienda estrategia de "no nuevas altas" antes de retirarlo.

- **No eliminar Snapshot confirmado.**  
  - Los snapshots confirmados forman parte del historial de auditoría.

- **No eliminar catálogo territorial histórico.**  
  - A lo sumo, archivar o desactivar; nunca borrar sin traza.

### 8.2. Políticas recomendadas

- Preferir **marcar como obsoleto/archivado** frente a borrar.  
- Eliminar físicamente sólo en entornos de laboratorio o para datos operativos caducados, con criterios claros de retención.

---

## 9. Reglas de evolución

### 9.1. Nueva OLT

Al agregar una nueva OLT, el sistema debe:

1. **Crear automáticamente estructuras vacías:**
   - Registros base de OLT, estados iniciales y colecciones vacías para catálogos técnicos y territoriales.

2. **Nunca copiar automáticamente desde otras OLTs:**
   - ✘ No copiar `Zones`.  
   - ✘ No copiar `NAPs`.  
   - ✘ No copiar `NapPorts`.

3. **Importar catálogos técnicos desde snapshots:**
   - ✔ VLANs.  
   - ✔ GponProfiles.  
   - ✔ SpeedProfiles.  
   - ✔ OnuTypes.  
   - ✔ PON ports.  
   - ✔ OnuServiceModeTemplates (derivados de parser estructurado).

4. **Reconstruir catálogos territoriales mediante Preview:**
   - ✔ Zones.  
   - ✔ NAPs (incl. ODN/ODB).  
   - ✔ NapPorts.

### 9.2. Escalado hacia multi-vendor y multi-ciudad

- Mantener la misma separación de dominios (global / por OLT / territorial / operativo) aunque se añadan nuevos vendors o ciudades.  
- Introducir catálogos globales por vendor/modelo que posteriormente se proyecten a instancias por OLT sin mezclar dominios.

---

## 10. Matriz de Gobierno

La siguiente matriz complementa la tabla de propiedad anterior con atributos de gobierno adicionales:

| Catálogo                | Global | OLT | Operativo | Versionado | Historial | Preview | Apply | Autoimport | Reconstruible | Auditable |
|-------------------------|:------:|:---:|:---------:|:----------:|:--------:|:-------:|:-----:|:---------:|:-------------:|:---------:|
| Vendor                  |  ✔    |     |           |   ✔        |   ✔      |   N/A   | N/A   |    ✘      |      ✘        |    ✔     |
| OnuModelTemplate        |  ✔    |     |           |   ✔        |   ✔      |   ✔     |  ✔    |   (✚)     |      ✔        |    ✔     |
| SplitterType            |  ✔    |     |           |   ◯        |   ◯      |   N/A   | N/A   |    ✘      |      ◯        |    ✔     |
| Technology              |  ✔    |     |           |   ◯        |   ✔      |   N/A   | N/A   |    ✘      |      ◯        |    ✔     |
| Olt                     |  ✔    |     |           |   ✔        |   ✔      |   ✔     |  ✔    |   (✚)     |      ◯        |    ✔     |
| Vlan                    |       | ✔  |           |   ◯        |   ✔      |   ✔     |  ✔    |    ✔      |      ✔        |    ✔     |
| GponProfile             |       | ✔  |           |   ✔        |   ✔      |   ✔     |  ✔    |    ✔      |      ✔        |    ✔     |
| SpeedProfile            |       | ✔  |           |   ✔        |   ✔      |   ✔     |  ✔    |   (✚)     |      ✔        |    ✔     |
| ProfileCatalog          |       | ✔  |           |   ✔        |   ✔      |   ✔     |  ✔    |    ✘      |      ◯        |    ✔     |
| OnuType                 |       | ✔  |           |   ✔        |   ✔      |   ✔     |  ✔    |    ✔      |      ✔        |    ✔     |
| PonPort                 |       | ✔  |           |   ◯        |   ✔      |   ✔     |  ✔    |    ✔      |      ✔        |    ✔     |
| OltUplink               |       | ✔  |           |   ◯        |   ✔      |   ✔     |  ✔    |    ✔      |      ✔        |    ✔     |
| OnuServiceModeTemplate  |       | ✔  |           |   ✔        |   ✔      |   ✔     |  ✔    |   (✚)     |      ✔        |    ✔     |
| ProvisioningTemplate    |   ✔   |     |           |   ✔        |   ✔      |   ✔     |  ✔    |    ✘      |      ◯        |    ✔     |
| ProvisioningPlan        |       | ✔  |           |   ◯        |   ✔      |   ✔     |  ✔    |    ✘      |      ✘        |    ✔     |
| Zone                    |       | ✔  |           |   ◯        |   ✔      |   ✔     |  ✔    |   (✚)     |      ◯        |    ✔     |
| Nap (NAP/ODN/ODB)       |       | ✔  |           |   ◯        |   ✔      |   ✔     |  ✔    |   (✚)     |      ◯        |    ✔     |
| NapPort                 |       | ✔  |           |   ◯        |   ✔      |   ✔     |  ✔    |   (✚)     |      ◯        |    ✔     |
| Onu                     |       | ✔  |           |   ◯        |   ✔      |   ✔     |  ✔    |    ✔      |      ◯        |    ✔     |
| OnuStatus / PowerHistory|       | ✔  |   ✔       |   ✘        |   ✔      |   N/A   | N/A   |    ✔      |      ✔        |    ✔     |
| Alarm / Event           |       | ✔  |   ✔       |   ✘        |   ✔      |   N/A   | N/A   |    ✔      |      ✔        |    ✔     |
| ConfigSnapshot          |       | ✔  |   ✔       |   ✘        |   ✔      |   ✔     |  ✔    |    ✔      |      ✔        |    ✔     |
| ImportJob               |       | ✔  |   ✔       |   ✘        |   ✔      |   ✔     |  ✔    |    ✔      |      ✔        |    ✔     |
| DataQuality (ONU)       |       | ✔  |   ✔       |   ✘        |   ✔      |   N/A   | N/A   |    ✔      |      ✔        |    ✔     |

Leyenda rápida:

- ✔ = sí / aplicable.  
- ✘ = no / prohibido.  
- ◯ = opcional / bajo.  
- (✚) = importación asistida (se propone, pero requiere decisión explícita).

---

## 11. Invariantes Arquitectónicas

Las siguientes reglas son **obligatorias** y deben respetarse en toda evolución del sistema:

1. **Scoping por OLT (territorial y técnico):**
   - `Onu.olt_id == Zone.olt_id` cuando `Onu.zone_id` no es nulo.  
   - `Onu.olt_id == Nap.olt_id` cuando `Onu.nap_id` no es nulo.  
   - `Nap.olt_id == Zone.olt_id` cuando `Nap.zone_id` no es nulo.  
   - `NapPort.olt_id == Nap.olt_id` para todo `NapPort`.  
   - `ProvisioningPlan.olt_id == Zone.olt_id` cuando `ProvisioningPlan.zone_id` no es nulo.  
   - `ProvisioningPlan.olt_id == Nap.olt_id` cuando `ProvisioningPlan.nap_id` no es nulo.

2. **Resolución con filtro por OLT:**
   - Nunca resolver catálogos por nombre sin filtrar por `olt_id`.  
   - Cualquier lookup debe incluir `olt_id` como parte de su clave lógica.

3. **No reutilización de objetos territoriales:**
   - Nunca usar `Zone`/`Nap`/`NapPort` de otra OLT para rellenar campos faltantes.  
   - Si falta un catálogo territorial, debe aparecer como `NULL` o candidato pendiente de revisión.

4. **Snapshots antes de importar:**
   - Toda importación relevante se basa en un snapshot persistido y validado (`ConfigSnapshot`).  
   - El snapshot es inmutable y se reutiliza para preview y confirm.

5. **Preview antes de Apply:**
   - Ningún cambio masivo (inventario, catálogos técnicos, catálogos territoriales) puede aplicarse sin un preview claro.

6. **Parser determinista:**
   - Los parsers deben ser deterministas sobre la misma entrada; no pueden depender de estado externo mutable.  
   - Las heurísticas deben ser explícitas y auditables.

7. **Preservación de nomenclatura NAP/ODN/ODB:**
   - El prefijo (`NAP`/`ODN`/`ODB`) forma parte de la identidad canónica.  
   - Prohibido colapsar `NAP D4` / `ODN D4` / `ODB D4` bajo `D4` o intercambiar tipos.

8. **Datos operativos no sobreescriben inventario:**
   - ONUs pueden cambiar de estado operativo, pero su ubicación e identidad canónica se gestionan vía inventario y catálogos.

---

## 12. Principios OSS FTTH

Admin OLT TOI debe evolucionar hacia una plataforma OSS FTTH que soporte:

- **Múltiples fabricantes** (ZTE, Huawei, Nokia, etc.) con drivers y parsers específicos.  
- **Múltiples OLTs** por fabricante, entorno y ciudad.  
- **Múltiples ciudades y áreas geográficas**, integradas con sistemas GIS.  
- **Inventario físico completo** (cables, cajas, splitters, rutas).  
- **Planificación de expansión** basada en capacidad por NAP/ODN/ODB y consumo real.  
- **Capacidad por NAP** y reservas de puertos para altas futuras.  
- **Integración comercial y CRM** (clientes, productos, contratos).  
- **Integración ERP** (activos, depreciación, compras).  
- **Flujos OSS/BSS completos**: provisión, fallos, cambios, configuración, inventario.

La clasificación de catálogos y las reglas de gobierno definidas aquí deben continuar siendo válidas incluso cuando:

- Se añadan nuevos vendors.  
- Se amplíe la planta externa y los modelos territoriales.  
- Se integren sistemas externos (CRM/ERP).  
- Se añadan nuevos módulos de planificación o análisis.

---

## 13. Decisiones Arquitectónicas

Las siguientes decisiones se consolidan como **fundamentales** para Admin OLT TOI:

1. **Snapshots antes de importar:**
   - Siempre se captura un `show running-config` completo y validado antes de parsear.

2. **Preview antes de apply:**
   - Todo cambio importante (import inicial, provisión, saneamiento territorial) pasa por un paso de preview.

3. **Parser determinista y no intrusivo:**
   - Los parsers leen y estructuran; nunca alteran estado en OLT.

4. **Scoping estricto por `olt_id`:**
   - Todas las entidades técnicas y territoriales se separan por OLT.  
   - Se prohíben catálogos ambiguos que mezclen OLTs.

5. **Calidad de datos como eje central:**
   - Se introducen estados de calidad (`data_quality_status`) y evaluadores por OLT antes de endurecer validaciones operativas.

6. **Catálogos territoriales separados:**
   - Zones/NAPs/NapPorts se gestionan como catálogos territoriales independientes, con reglas específicas y revisión humana.

7. **Preservación de nomenclatura NAP/ODN/ODB:**
   - Confirmado documentalmente que el prefijo forma parte de la clave; la normalización sólo puede actuar sobre formato interno (espacios/guiones).

Estas decisiones deben considerarse la **constitución arquitectónica** de Admin OLT TOI en materia de catálogos.

---

## 14. Roadmap Arquitectónico

El roadmap de alto nivel asociado al gobierno de catálogos y evolución hacia OSS FTTH es:

- **P4 – Modelo Territorial FTTH**  
  - Reconstrucción y saneamiento de Zones/NAP/ODN/ODB/NapPorts por OLT, siguiendo `docs/EFO_MODELO_TERRITORIAL_FTTH.md`.

- **P5 – GIS**  
  - Integración con sistemas GIS para ubicar NAPs, ODNs, ODBs, rutas de fibra y clientes en mapa.  
  - Sincronización entre catálogos territoriales y capas geográficas.

- **P6 – Inventario de Planta Externa**  
  - Extender el modelo territorial a cables, tramos, cajas, postes y rutas de planta externa.  
  - Definir capacidad y ocupación por tramo.

- **P7 – CRM/ERP**  
  - Integración con sistemas comerciales y de gestión de recursos empresariales.  
  - Trazabilidad contrato → ONU → NAP → planta externa → activos.

- **P8 – OSS FTTH completo**  
  - Convergencia de módulos de planificación, operación, inventario, monitoreo y facturación bajo un modelo de datos consistente.

Cada fase deberá respetar las clasificaciones, reglas de gobierno e invariantes definidas en este documento.
