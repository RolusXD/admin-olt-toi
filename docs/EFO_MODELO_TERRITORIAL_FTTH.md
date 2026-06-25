# Especificación Funcional Oficial

## Modelo Territorial FTTH por OLT

Versión: 1.0  
Fecha: 2026-06-24  
Ámbito: Proyecto TOI OLT Manager (ZTE C300)

---

## 1. Objetivo

Este documento define el **modelo territorial FTTH** de TOI OLT Manager, centrado en la relación entre inventario lógico y planta externa, sin introducir cambios de código ni de esquema.

Objetivos específicos:

1. **Definir el modelo territorial FTTH de Admin OLT TOI.**  
   - Formalizar las entidades territoriales internas y su pertenencia a una OLT.

2. **Formalizar la jerarquía canónica:**

   ```text
   OLT → Zona → NAP/ODN/ODB → NapPort → ONU
   ```

   - Cada escalón de la jerarquía pertenece a **una única OLT**.
   - No se permiten referencias cruzadas entre OLTs.

3. **Evitar cruces entre OLTs.**  
   - Cerrar el escenario actual donde ONUs y planes PCM consumen Zones/NAPs/LAB.
   - Establecer reglas para reconstruir y validar el catálogo territorial por OLT.

Este documento es **puramente conceptual y documental**. No autoriza por sí mismo cambios directos en código, migraciones o datos productivos.

---

## 2. Alcance

### 2.1. Incluye

El modelo territorial FTTH cubre, por OLT:

- **Zones** (zonas operativas / comerciales por OLT).
- **NAPs** (puntos de acceso de planta externa). 
- **ODN** (segmentos de red óptica / distribución).
- **ODB** (cajas / puntos de distribución intermedios cuando existan).
- **NapPorts** (puertos físicos/lógicos de una NAP/ODN/ODB).
- **Relación ONU → Zone/NAP/NapPort**:
  - `Onu.zone_id`
  - `Onu.nap_id`
  - `Onu.nap_port` / `Onu.nap_port_id`
- **Relación ProvisioningPlan → Zone/NAP**:
  - `ProvisioningPlan.zone_id`
  - `ProvisioningPlan.nap_id`

Estas entidades forman el **árbol territorial** que conecta la OLT con la planta externa y, finalmente, con el abonado.

### 2.2. Excluye (catálogos técnicos ya saneados por OLT)

Quedan fuera del alcance de este modelo territorial las siguientes entidades, que ya están correctamente scopiadas por `olt_id` y **no requieren reconstrucción territorial** en esta fase:

- `Vlan`
- `OnuType`
- `SpeedProfile`
- `ProfileCatalog`
- `PonPort`
- `OnuServiceModeTemplate`

Para estos catálogos técnicos se mantienen las EFO existentes:

- `docs/EFO_CALIDAD_DATOS_Y_GOBIERNO_OLT.md`
- `docs/EFO_NORMALIZACION_MODELO_ONU.md`
- `docs/EFO_MODELO_OPERACIONAL_ONU.md`

El trabajo de esta EFO se centra exclusivamente en **Zones / NAP / ODN / ODB / NapPorts** y sus relaciones con **ONUs** y **ProvisioningPlan**.

---

## 3. Principios obligatorios del modelo territorial

### 3.1. Pertenencia por OLT

1. **Todo objeto territorial pertenece a una OLT.**
   - `Zone`, `Nap`, `NapPort` y cualquier representación de `ODN`/`ODB` son entidades **by_olt**.
   - Llevan siempre un `olt_id` que identifica la OLT propietaria.

2. **No existen Zones globales.**
   - No se permite un catálogo de zonas compartidas entre OLTs.
   - La combinación lógica es: `Zone(olt_id, name)`.

3. **No existen NAPs globales.**
   - Cada `Nap` se define por `olt_id + zone_id + canonical_name`.
   - No se comparten NAPs entre OLTs, aunque el nombre visible coincida.

4. **No existen NapPorts globales.**
   - Cada `NapPort` pertenece a un único `Nap` y a la OLT de ese `Nap`.

### 3.2. Invariantes de integridad cruzada

5. **Una ONU nunca puede apuntar a Zone/NAP/NapPort de otra OLT.**
   - Si `Onu.olt_id = 3` (PCM), entonces:
     - `Onu.zone_id` (si existe) **debe** referenciar `Zone.olt_id = 3`.
     - `Onu.nap_id` (si existe) **debe** referenciar `Nap.olt_id = 3`.
     - `Onu.nap_port_id` (si existe) **debe** referenciar `NapPort.olt_id = 3`.

6. **Un ProvisioningPlan nunca puede apuntar a Zone/NAP de otra OLT.**
   - Si `ProvisioningPlan.olt_id = 3`, entonces:
     - `ProvisioningPlan.zone_id` (si existe) **debe** referenciar `Zone.olt_id = 3`.
     - `ProvisioningPlan.nap_id` (si existe) **debe** referenciar `Nap.olt_id = 3`.

7. **Si no existe el objeto territorial para esa OLT, no se reutiliza otro `olt_id`.**
   - Si durante importación o saneamiento no se encuentra una `Zone`/`Nap`/`NapPort` consistente para la OLT actual:
     - El campo puede permanecer `NULL`, y/o
     - Se puede crear un **candidato pendiente** (por ejemplo, `Nap` con `data_quality_status = "pending"`).
   - **Nunca** se permite:
     - Reutilizar una `Zone` existente de otra OLT.
     - Reutilizar un `Nap` o `NapPort` de otra OLT para "rellenar" la FK.

Estas reglas son concreciones de la **Regla de oro de aislamiento por OLT** definida en la EFO de Calidad de Datos.

---

## 4. Identidad canónica de NAP/ODN/ODB

### 4.1. Componentes de la identidad

Para cualquier elemento de planta externa **NAP / ODN / ODB** se define la siguiente estructura lógica:

- **`prefix/type` (obligatorio):**
  - `NAP`
  - `ODN`
  - `ODB`

- **`code/suffix`:**
  - Identificador corto tras el prefijo, por ejemplo: `D01`, `D2`, `H5`, `C4 A`, `C4_A`, etc.

- **`display_name`:**
  - Nombre completo tal como proviene de sistemas heredados (SmartOLT, running-config, catastro):
    - Ejemplos: `ODN H5------COOPERATIVA`, `ODN G7----UE 6 DE MARZO SAN ROQUE`.

- **`canonical_name`:**
  - Nombre normalizado calculado a partir de `prefix + code`:
    - Se preserva el prefijo (`NAP` / `ODN` / `ODB`).
    - Se normalizan espacios/guiones/subrayados en el código.
    - Se aplican reglas consistentes de mayúsculas/minúsculas.

- **`description/notes`:**
  - Campo libre para conservar el texto largo, descripciones adicionales y anotaciones documentales.

### 4.2. Definición de `canonical_name`

Regla general:

```text
canonical_name = PREFIX + " " + CODE_NORMALIZADO
```

Donde `CODE_NORMALIZADO` puede:

- Unificar variantes de formato internas (`C4_A`, `C4-A`, `C4  A`) en un único código lógico (`C4 A`).
- Conservar bloques de letras/números significativos.

**Ejemplos permitidos:**

- Entrada documental: `ODN C4_A`  
  → `prefix = "ODN"`, `code = "C4 A"`  
  → `canonical_name = "ODN C4 A"`.

- Entrada documental: `ODN C4-B`  
  → `prefix = "ODN"`, `code = "C4 B"`  
  → `canonical_name = "ODN C4 B"`.

- Entrada documental: `ODN H5------COOPERATIVA`  
  → `prefix = "ODN"`, `code = "H5"`  
  → `canonical_name = "ODN H5"`  
  → `notes/description`: `COOPERATIVA`.

**Reglas de conservación de notas:**

- Cualquier texto posterior al identificador canónico (barrio, institución, referencia larga) debe conservarse en `description`/`notes`.
- Nunca se descarta información documental; sólo se separa en campos estructurados.

### 4.3. Prohibiciones explícitas

Basado en las auditorías documentadas:

- `NAP D01` ≠ `ODN D01`.
- `NAP D2` ≠ `ODN D2`.
- `NAP D3` ≠ `ODN D3`.
- `NAP D4` ≠ `ODN D4`.
- `NAP F7` ≠ `ODN F7`.

Por tanto, se declara **prohibido**:

- Eliminar el prefijo en la identidad canónica:
  - `ODN D4` → `D4`  ❌
  - `NAP D4` → `D4`  ❌

- Cruzar tipos durante normalización:
  - `NAP D4` → `ODN D4`  ❌
  - `ODN D4` → `NAP D4`  ❌

- Colapsar NAP/ODN/ODB bajo un identificador sin prefijo:
  - `NAP D4` / `ODN D4` / `ODB D4` → `D4`  ❌

Estas reglas son consistentes con la sección **2.bis. Normalización de nombres de NAP y ODN** de `docs/EFO_NORMALIZACION_MODELO_ONU.md` y la sección **5.7. Identidad canónica de NAPs** de `docs/EFO_CALIDAD_DATOS_Y_GOBIERNO_OLT.md`.

---

## 5. Modelo conceptual recomendado (territorial)

> **Importante:** este diseño es **conceptual**. No implica todavía cambios de esquema, migraciones ni código; sirve como contrato para futuras fases de implementación.

### 5.1. Zone (zona operativa por OLT)

Campos conceptuales:

- `id`
- `olt_id`
- `name`
- `source` (por ejemplo: `import_running_config`, `import_smartolt`, `manual`)
- `data_quality_status` (por ejemplo: `complete`, `needs_review`, `legacy_incomplete`, `pending`)
- `notes` (observaciones documentales)

Rol en el modelo territorial:

- Agrupa NAP/ODN/ODB bajo una zona operativa coherente por OLT.
- Se usa como pivote para reporting territorial y provisión.

### 5.2. Nap (NAP / ODN / ODB por OLT y zona)

Campos conceptuales:

- `id`
- `olt_id`
- `zone_id`
- `type/prefix` (obligatorio): `NAP`, `ODN`, `ODB`
- `code` (sufijo normalizado: `D01`, `D2`, `H5`, `C4 A`, etc.)
- `canonical_name` (por ejemplo, `ODN H5`, `NAP D01`, `ODB C4 A`)
- `display_name` (texto heredado tal cual de la fuente)
- `capacity` (número esperado de puertos / clientes)
- `splitter_type` (por ejemplo, `1:8`, `1:16` cuando se conozca)
- `latitude`
- `longitude`
- `source` (igual que en `Zone`)
- `data_quality_status` (alineado con EFO de calidad de datos)
- `notes` (texto libre)
- `last_seen_snapshot_id` (referencia al último snapshot/import en el que fue observado)

Comentarios:

- `Nap` funciona como **contenedor genérico de planta externa**, distinguiendo el tipo real mediante `type/prefix`.
- La combinación `(olt_id, canonical_name)` debe ser única para cada `type/prefix`.

### 5.3. NapPort (puerto de NAP/ODN/ODB)

Campos conceptuales:

- `id`
- `olt_id`
- `nap_id`
- `port_number` (1..N)
- `status` (por ejemplo: `free`, `occupied`, `reserved`, `unknown`)
- `onu_id` (opcional; vínculo directo a `Onu` si se modela a este nivel)
- `fiber_color` (opcional; referencia práctica para campo)
- `notes`

Comentarios:

- `NapPort` materializa la relación **NAP/ODN/ODB → ONU** a nivel de puerto de planta externa.
- La combinación `(nap_id, port_number)` debe ser única.

---

## 6. Estado actual detectado (P3.6.1, P3.6.2, P3.6.3)

Con base en las auditorías anteriores (Fase P3) y la evidencia documentada:

1. **Zones sólo existen para OLT-LAB-ZTE-01.**
   - El catálogo de zonas operativas está poblado únicamente para la OLT de laboratorio.
   - `OLT-PCM-ZTE-01` carece de zonas propias consolidadas en la BD.

2. **NAPs sólo existen para OLT-LAB-ZTE-01.**
   - El catálogo de NAPs/ODN/ODB está concentrado en LAB.
   - PCM no tiene un catálogo territorial propio en tablas `Nap`.

3. **NapPorts sólo existen para OLT-LAB-ZTE-01.**
   - Los puertos de NAP se han modelado sólo para la OLT de laboratorio.

4. **PCM no tiene catálogo territorial propio.**
   - `OLT-PCM-ZTE-01` opera con ONUs reales, pero sus `zone_id`/`nap_id` apuntan al catálogo territorial de LAB.

5. **Cruces de ONUs PCM hacia LAB:**
   - **454 ONUs** de `OLT-PCM-ZTE-01` con `zone_id` cruzado (apuntando a zonas de LAB).
   - **169 ONUs** de `OLT-PCM-ZTE-01` con `nap_id` cruzado (apuntando a NAPs de LAB).

6. **Cruces en ProvisioningPlan PCM:**
   - **27 `ProvisioningPlan`** de PCM con `zone_id`/`nap_id` cruzados hacia LAB.

7. **Resto de catálogos técnicos por OLT sano:**
   - VLANs, SpeedProfiles, ProfileCatalogs, OnuTypes, PonPorts y OnuServiceModeTemplates ya están correctamente scopiados por OLT.
   - El problema real está **concentrado en el modelo territorial** (Zones/NAPs/NapPorts) y su uso por ONUs/planes PCM.

Este estado actual motiva la Fase P4 de **reconstrucción territorial FTTH** por OLT.

---

## 7. Flujo de reconstrucción propuesto (P4)

La reconstrucción territorial se estructurará en fases, todas ellas con enfoque de **preview primero, apply después** y revisión humana obligatoria.

### P4.1. Reconstrucción de Zones por OLT

Objetivo:

- Construir un catálogo de `Zone` por OLT (especialmente PCM) usando la mejor evidencia disponible.

Insumos:

- `parsed_zone_name` (resultado del parser de descripciones ZTE).
- Snapshots confirmados (`ConfigSnapshot`) y resultados de parseo históricos.

Reglas conceptuales:

- Agrupar ONUs PCM por `parsed_zone_name` y por patrones documentales en descripciones.
- Proponer `Zone(olt_id=PCM, name=...)` cuando exista evidencia suficiente.
- Marcar `data_quality_status` según la confianza (ver sección 8).

**Importante:**

- Esta fase sólo genera una **propuesta de catálogo `Zone` por OLT** (preview).  
- No se aplican cambios definitivos sin revisión humana y sin tooling específico.

### P4.2. Reconstrucción de NAP/ODN/ODB por OLT

Objetivo:

- Separar y reconstruir catálogos de **NAP / ODN / ODB** por OLT, evitando colisiones de identidad.

Insumos:

- `parsed_nap_name` (desde descripciones ZTE / SmartOLT).
- `parsed_odn` (cuando exista en parseo estructurado).
- `odb_name` (cuando exista información documental). 
- Inventario histórico de SmartOLT como **referencia documental**, no como verdad absoluta.

Reglas conceptuales:

- Diferenciar siempre entidades por prefijo: `NAP` vs `ODN` vs `ODB`.
- Reconstruir `Nap` con `type/prefix` adecuado y `canonical_name` consistente.
- Alinear NAP/ODN/ODB propuestos con las `Zone` propuestas/confirmadas en P4.1.

Resultado esperado:

- Catálogo propuesto `Nap` por OLT (especialmente PCM), con:
  - `type/prefix`, `canonical_name`, `display_name`, `zone_id`, `capacity`, `splitter_type`, `data_quality_status`.

### P4.3. Reconstrucción de NapPorts

Objetivo:

- Reconstruir `NapPort` por OLT/NAP, equilibrando evidencia técnica y prudencia documental.

Insumos:

- Capacidad y tipo de splitter (`capacity`, `splitter_type`) cuando existan.
- Ocupación observada por ONUs (relación ONU ↔ NAP/NAP-port en descripciones/documentación).

Reglas conceptuales:

- Para cada `Nap`:
  - Inferir un rango de `port_number` esperable (ej. 1..8, 1..16, 1..32) según `splitter_type` o evidencia.
  - Marcar como `occupied` los puertos con ONUs sólidamente asociadas.
  - Marcar como `pending` o `unknown` puertos sin evidencia clara.

- **No forzar completitud artificial:**
  - Si no hay evidencia de capacidad total, mantener puertos como "pendientes" en lugar de inventarlos.

### P4.4. Preview de reasignación (ONU / ProvisioningPlan)

Objetivo:

- Mostrar un **preview detallado** de cómo quedarían las ONUs y ProvisioningPlans al migrar de catálogos LAB a catálogos PCM propios.

Elementos del preview:

1. **Estado actual:**
   - `Onu` con `zone_id`/`nap_id` apuntando a LAB.
   - `ProvisioningPlan` con `zone_id`/`nap_id` cruzados.

2. **Estado propuesto:**
   - Mapeo a `Zone`/`Nap` PCM reconstruidos (cuando exista correspondencia).
   - Casos donde no se encuentra correspondencia clara se marcan como **bloqueados** o `needs_review`.

3. **Confianza:**
   - Cada reasignación se etiqueta con nivel de confianza: `alta` / `media` / `baja` / `bloqueado` (ver sección 8).

4. **Razones:**
   - Para cada reasignación, se almacenan motivos/resumen, por ejemplo:
     - `match prefix+code exacto en misma OLT y zona`.
     - `match sólo por código, sin prefijo en descripción`.
     - `ruido documental extenso; coincidencia parcial`.

### P4.5. Apply controlado

Objetivo:

- Definir cómo se aplicarán en el futuro las reasignaciones territoriales, manteniendo el control operativo.

Principios:

- **Sólo después de revisión humana.**
  - Ninguna reasignación territorial automática debe ejecutarse sin revisión explícita.

- **Nunca masivo sin preview.**
  - Cualquier tooling de apply debe requerir:
    - Haber generado un preview completo.
    - Haber registrado decisiones de inclusión/exclusión por lote.

- **Auditoría antes/después.**
  - Guardar un snapshot lógico de:
    - Relaciones ONU ↔ Zone/Nap/NapPort antes del cambio.
    - Relaciones ONU ↔ Zone/Nap/NapPort después del cambio.
  - Idem para `ProvisioningPlan`.

---

## 8. Reglas de confianza para mapeos territoriales

Para clasificar la calidad de cada reasignación territorial (ONU/plan a nueva Zone/NAP/NapPort) se definen los siguientes niveles de confianza:

### 8.1. ALTA

Condiciones típicas:

- Coincidencia exacta por **prefijo + código** (`NAP D01`, `ODN H5`, etc.).
- Misma `olt_id` en origen y destino.
- Zona coherente (`Zone.name` / `parsed_zone_name` coincidentes o equivalentes por normalización documentada).

Ejemplo:

- Descripción ONU PCM: `zone_Lagunas nap_ODN H5------COOPERATIVA`  
  → `Zone(olt_id=PCM, name="Lagunas")`  
  → `Nap(olt_id=PCM, canonical_name="ODN H5")`.

### 8.2. MEDIA

Condiciones típicas:

- Match consistente por **código**, pero **prefijo ausente** o ambiguo en la fuente (p.ej. sólo `D01`).
- Contexto adicional (dirección, cliente, notas) coincide con el catálogo propuesto.

Ejemplo:

- Descripción ONU PCM: `Lagunas D01 COOPERATIVA`  
  → catálogos propuestos: `NAP D01` y `ODN D01` para la misma zona.  
  → Se sugiere uno de ellos con confianza `media` y se marca el otro camino como posible conflicto.

### 8.3. BAJA

Condiciones típicas:

- Descripciones largas o ruidosas sin estructura clara (`nap`, `odn` ausentes o confusos).
- Referencias vagas a direcciones, instituciones o nombres coloquiales sin código sólido.

Ejemplo:

- Descripción ONU PCM: `zona Lagunas frente a cancha barrio nuevo` sin NAP/ODN explícito.

En confianza `baja`, se pueden sugerir candidatos pero **no** deben aplicarse sin revisión manual detallada.

### 8.4. BLOQUEADO

Condiciones:

- Ambigüedad irresoluble entre NAP/ODN/ODB (ej. posible match tanto a `NAP D4` como a `ODN D4`).
- Cruces territoriales no resolubles con la evidencia disponible.
- Conflictos directos con la regla de identidad canónica (prefijo obligatorio).

Acciones:

- El caso se marca como **bloqueado** para reasignación automática.
- Debe entrar en una lista de revisión humana priorizada.

---

## 9. Reglas para futuras importaciones

Las futuras fases de importación y saneamiento territorial deben respetar las siguientes reglas funcionales:

1. `confirm_import` siempre debe resolver `Zone` / `Nap` / `NapPort` **filtrando por `olt_id`**.
   - Cualquier lookup territorial debe llevar `olt_id` como primer filtro.

2. Si no existe la entidad territorial en esa OLT:

   - **Opción A:** crear un **candidato pendiente** en el catálogo de esa OLT, con `data_quality_status = "pending"` o similar.
   - **Opción B:** dejar el campo `NULL` y marcar la ONU/plan con `needs_review` en calidad de datos.

3. **Nunca reutilizar Zone/Nap/NapPort de otra OLT.**
   - Cualquier cruce actual (PCM usando LAB) es una **deuda histórica** a corregir, no un patrón a repetir.

4. `ProvisioningPlan` debe validar invariantes territoriales antes de generar CLI:

   - `ProvisioningPlan.olt_id == Zone.olt_id == Nap.olt_id` (cuando se informan).
   - `NapPort.olt_id` coincide con `Nap.olt_id` y con `ProvisioningPlan.olt_id`.
   - Si alguna referencia territorial es `NULL` cuando debería ser obligatoria para altas nuevas de ONU, el plan se considera inválido.

---

## 10. Tests requeridos futuros (conceptuales)

Se recomienda introducir tests (unitarios y/o de integración, sobre SQLite en memoria) que verifiquen al menos las siguientes invariantes territoriales:

1. **ONU ↔ Zone:**
   - `Onu.olt_id == Zone.olt_id` cuando `Onu.zone_id` no es nulo.

2. **ONU ↔ Nap:**
   - `Onu.olt_id == Nap.olt_id` cuando `Onu.nap_id` no es nulo.

3. **Nap ↔ Zone:**
   - `Nap.olt_id == Zone.olt_id` cuando `Nap.zone_id` no es nulo.

4. **NapPort ↔ Nap:**
   - `NapPort.olt_id == Nap.olt_id` para todos los `NapPort`.

5. **ProvisioningPlan ↔ Zone:**
   - `ProvisioningPlan.olt_id == Zone.olt_id` cuando `ProvisioningPlan.zone_id` no es nulo.

6. **ProvisioningPlan ↔ Nap:**
   - `ProvisioningPlan.olt_id == Nap.olt_id` cuando `ProvisioningPlan.nap_id` no es nulo.

7. **confirm_import no reutiliza catálogos de otra OLT:**
   - Tests que simulen descripciones ambiguas y verifiquen que los lookups siempre se filtran por `olt_id`.

8. **Parser preserva prefijos NAP/ODN/ODB:**
   - Tests de parser/documental que confirmen que los prefijos `NAP` / `ODN` / `ODB` nunca se pierden ni se intercambian.

Estos tests deben diseñarse y planificarse en fases posteriores; este documento sólo los especifica a nivel conceptual.

---

## 11. Riesgos identificados

Durante la reconstrucción territorial FTTH se deben considerar los siguientes riesgos:

1. **Crear un catálogo PCM incorrecto.**
   - Riesgo de consolidar NAP/Zone equivocadas que luego se usen en provisión.

2. **Fusionar NAP/ODN por error.**
   - Colapso de entidades distintas (ej. `NAP D4` y `ODN D4`) bajo un solo registro.

3. **Perder notas documentales.**
   - Riesgo de descartar nombres largos, direcciones o referencias útiles al normalizar a `canonical_name`.

4. **Aplicar reasignaciones sin revisión humana.**
   - Cambios masivos en `zone_id`/`nap_id`/`nap_port`/`ProvisioningPlan` sin un paso explícito de revisión.

5. **Confundir zona macro con zona operativa.**
   - Uso indistinto de zonas comerciales muy amplias frente a zonas operativas efectivas para planta externa.

Mitigaciones recomendadas:

- Mantener siempre `display_name` y `description` originales además de `canonical_name`.
- Usar niveles de confianza (sección 8) para filtrar qué cambios pueden aplicarse automáticamente.
- Exigir revisión y aprobación por parte de operaciones antes de cualquier apply.

---

## 12. Entregables de la Fase P4 (Modelo Territorial FTTH)

Al cierre de la Fase P4 se esperan, al menos, los siguientes entregables:

1. **Preview de Zones por OLT.**
   - Propuesta de catálogo de zonas por cada OLT (en especial PCM), con `data_quality_status` y fuente.

2. **Preview de NAP/ODN/ODB por OLT.**
   - Listado territorial de planta externa por OLT y zona, con `canonical_name`, `display_name`, `type/prefix` y notas.

3. **Preview de NapPorts.**
   - Rango de puertos por NAP/ODN/ODB, estados (`free`/`occupied`/`pending`) y ONUs asociadas.

4. **Matriz ONU actual vs propuesta.**
   - Para cada ONU PCM afectada:
     - `Zone/Nap/NapPort` actual (LAB).
     - `Zone/Nap/NapPort` propuesta (PCM).
     - Nivel de confianza y razones.

5. **Reporte de confianza.**
   - Estadísticas por nivel (`alta`/`media`/`baja`/`bloqueado`).
   - Distribución por zona/NAP y por OLT.

6. **Lista de casos bloqueados para revisión humana.**
   - ONUs y planes que no pueden reasignarse automáticamente.
   - Motivos de bloqueo (ambigüedad, falta de datos, conflicto con reglas canónicas).

Todos estos entregables deberán generarse inicialmente como **reportes y vistas de análisis**, sin modificar ONUs ni planes hasta que exista una decisión explícita de implementación y apply controlado.
