# Especificación Funcional Oficial

## Arquitectura Operativa de Admin OLT TOI

Versión: 1.0  
Fecha: 2026-06-24  
Ámbito: Proyecto TOI OLT Manager (multi-OLT, multi-vendor, OSS FTTH)

---

## 1. Filosofía

### 1.1. Objetivo del sistema

Admin OLT TOI deja de ser sólo un importador de configuraciones para convertirse en el **Sistema Operativo de las OLT administradas**.  
Su objetivo es:

- Administrar el **ciclo de vida completo** de cada OLT y su inventario FTTH asociado.
- Separar y orquestar claramente:
  - **Inventario aprobado (Desired State)**.
  - **Estado observado en la OLT (Observed State)**.
  - **Historial de configuraciones (Snapshots)**.
  - **Inventario oficial** como fuente de verdad operacional.
- Permitir que la OLT sea un **dispositivo administrado**, no la fuente única de verdad.

En este modelo, Admin OLT TOI tiene el rol de **orquestador central de verdad operacional**; las OLTs se convierten en **nodos ejecutores** cuyos estados deben alinearse, bajo control, con el inventario aprobado.

### 1.2. Qué significa administrar una OLT

Administrar una OLT implica:

1. **Conocer su estado** en todo momento:
   - Versiones de software, tarjetas, puertos PON, uplinks.
   - ONUs, perfiles, VLANs, modos de servicio, estado óptico.
   - Relación con planta externa (Zones, NAP/ODN/ODB, NapPorts).

2. **Mantener un inventario aprobado y coherente** por OLT:
   - Qué ONUs deberían existir, dónde, con qué servicios y sobre qué recursos (PON, VLAN, NAP, NapPort, Zone).
   - Qué catálogos técnicos/territoriales están vigentes.

3. **Controlar la convergencia entre inventario y realidad**:
   - Detectar y clasificar desviaciones (**drift**) entre el inventario aprobado y el estado observado.
   - Proponer y ejecutar planes de provisión/saneamiento que resuelvan ese drift bajo control humano.

4. **Garantizar auditabilidad y recuperabilidad**:
   - Cada cambio importante deja huella: quién lo pidió, qué plan lo ejecutó, qué CLI se generó, qué snapshot lo respalda.
   - Debe ser posible recuperar una OLT a un estado consistente a partir de snapshots e inventario oficial.

En síntesis, administrar una OLT es **gobernar el ciclo de vida conjunto de inventario, configuración y operación**, no sólo ejecutar comandos.

### 1.3. Diferencia entre importar y adoptar

- **Importar**:
  - Acción de **observar** el estado actual de una OLT mediante snapshots (`show running-config` + comandos adicionales) y parsers.
  - Produce información estructurada de **Observed State** y propuestas de cambio sobre inventario.
  - No implica que el sistema asuma responsabilidad sobre ese estado; sólo lo describe y lo compara con el inventario existente.

- **Adoptar**:
  - Acción de **asumir responsabilidad** sobre el inventario y la configuración de una OLT.
  - Implica definir un **Desired State** explícito que se considera fuente de verdad oficial, y al que la OLT debe converger.
  - Supone haber pasado por un proceso de revisión y saneamiento (preview → validación → aprobación) sobre el inventario descubierto.

En la nueva arquitectura operativa:

- Una OLT puede estar **importada pero no adoptada**: el sistema conoce su estado, pero no lo considera todavía parte de un inventario oficial consolidado.
- Una OLT **adoptada** tiene:
  - Inventario aprobado por OLT (Desired State).
  - Procedimientos de sincronización y drift detection activos.
  - Estrategias de recuperación definidas.

### 1.4. Rol del operador

El operador humano es la **autoridad de decisión** sobre inventario y cambios operativos. Sus responsabilidades son:

- Revisar previews de importación, reconstrucción territorial, drift y provisión.
- Aprobar o rechazar propuestas de cambios en inventario y catálogos.
- Lanzar planes de provisión (ProvisioningPlan) en modo controlado.
- Resolver conflictos o ambigüedades (casos `REVIEW` / `BLOQUEADO`).
- Supervisar auditorías y validar resultados ante incidentes.

La IA, los parsers y los servicios de análisis sólo **asisten** al operador con clasificación, normalización, recomendaciones y generación de planes, pero **no sustituyen su decisión**.

### 1.5. Rol de la OLT

La OLT pasa a ser un **dispositivo administrado**:

- Expone un estado observable (configuración actual, estado de ONUs, potencia, alarmas).
- Ejecuta comandos de configuración cuando un plan aprobado se aplica.
- No define el inventario oficial por sí sola: su configuración se compara y alinea con el **Desired State** gestionado por Admin OLT TOI.

La OLT es una **implementación concreta** del estado deseado; Admin OLT TOI es el **orquestador de ese estado**.

---

## 2. Ciclo de vida de una OLT

El ciclo de vida operativo de una OLT dentro de Admin OLT TOI se define mediante los siguientes estados conceptuales:

- `REGISTERED`
- `CONNECTED`
- `SNAPSHOTTED`
- `PREVIEW_READY`
- `UNDER_REVIEW`
- `ADOPTED`
- `SYNCHRONIZED`
- `SUSPENDED`
- `RETIRED`

> Nota: Estos estados son **conceptuales** y no implican por sí mismos cambios en el modelo actual de BD. Pueden proyectarse sobre los estados existentes (`draft`, `connection_tested`, `preview_created`, `confirmed`, etc.) o extenderse en futuras fases.

### 2.1. REGISTERED

La OLT existe en el sistema como registro mínimo:

- Se creó una entrada de OLT con identificación básica (código, nombre, vendor, entorno).
- No hay aún validación de conectividad ni snapshots asociados.

Responsabilidades y restricciones:

- Sólo se permiten operaciones de configuración documental (metadatos, etiquetas, entorno).
- No se deben ejecutar comandos Telnet ni importaciones.

### 2.2. CONNECTED

La OLT ha pasado las pruebas de conexión **read-only**:

- Se validó acceso Telnet/SSH con `read_only=true`.
- Se confirmaron comandos básicos (`show version`, `show card`, etc.).

Responsabilidades y restricciones:

- La OLT está lista para capturar snapshots.
- Aún **no** hay inventario aprobado ni adopción; sólo se conoce que la OLT es alcanzable.

### 2.3. SNAPSHOTTED

Se ha capturado al menos un **snapshot completo** válido:

- `show running-config` completo con prompt estable y checksum.
- Configuración de soporte (comandos adicionales) cuando aplique.
- El snapshot es **inmutable** y versionado.

Responsabilidades y restricciones:

- El sistema puede **reconstruir catálogos técnicos y parte del inventario** a partir de este snapshot.
- Aún no se ha consolidado ningún cambio en inventario oficial.

### 2.4. PREVIEW_READY

Sobre uno o más snapshots válidos se ha ejecutado el **parser**, produciendo:

- Estado observado estructurado (ONUs, VLANs, perfiles, PON, etc.).
- Propuestas de inventario y/o cambios (preview de importación, reconstrucción territorial, etc.).

La OLT está lista para que el operador revise:

- Diferencias entre inventario actual e información observada.
- Recomendaciones de saneamiento.

### 2.5. UNDER_REVIEW

El operador está evaluando las propuestas generadas:

- Revisa previews (import, territorial, drift, provisión).
- Marca candidatos como aceptados, rechazados, bloqueados o pendientes.
- Puede iterar múltiples veces: nuevos snapshots, nuevos previews.

Responsabilidades y restricciones:

- No se consideran cambios definitivos en inventario hasta que se complete la revisión.
- La OLT aún no se considera **adoptada**.

### 2.6. ADOPTED

La OLT ha sido **formalmente adoptada** por Admin OLT TOI:

- Existe un **Desired State** consistente para su inventario (ONUs, catálogos técnicos, territoriales, provisión).
- Las deudas históricas críticas han sido al menos identificadas y clasificadas.
- Se definen reglas de operación y recuperación.

Efectos de la adopción:

- El inventario de Admin OLT TOI pasa a ser la **fuente principal de verdad** sobre la OLT.
- El estado observado de la OLT se evalúa permanentemente contra ese Desired State.

### 2.7. SYNCHRONIZED

Estado dinámico alcanzado cuando, para una OLT adoptada:

- El estado observado (**Observed State**) es compatible con el **Desired State** dentro de tolerancias definidas.
- El drift presente se limita a desviaciones esperadas (ej. ONUs temporalmente desconectadas) sin cambios estructurales no aprobados.

Responsabilidades y restricciones:

- Cualquier cambio estructural (nuevas ONUs, cambios de VLAN, reasignaciones territoriales) debe pasar por flujo de **Provisioning** + Snapshot + Validación.

### 2.8. SUSPENDED

Estado en el que el sistema **suspende temporalmente** la gestión activa de una OLT:

- Puede deberse a incidentes, mantenimiento mayor, migraciones, auditorías regulatorias, etc.
- Se congelan flujos de provisión y sincronización automática.

Responsabilidades y restricciones:

- Sólo se permiten operaciones de análisis y snapshot adicionales.
- No se ejecutan cambios en la OLT desde Admin OLT TOI.

### 2.9. RETIRED

Estado final de una OLT que ha sido retirada del servicio:

- No se programan nuevas provisiones.
- Se conserva el historial de snapshots, inventario y auditoría como referencia.

Responsabilidades y restricciones:

- Sólo se permiten consultas históricas.
- Cualquier reutilización de recursos (VLANs, NAPs, ONU seriales, etc.) debe pasar por flujos de alta en OLTs activas.

---

## 3. Capas del sistema

La arquitectura operativa se organiza en capas lógicas encadenadas:

1. **Snapshot**
2. **Parser**
3. **Preview**
4. **Inventario Deseado (Desired State)**
5. **Observed State**
6. **Drift**
7. **Provisioning**
8. **Auditoría**

### 3.1. Snapshot

Responsable de **capturar y preservar** el estado de configuración de la OLT en un momento dado.

- Entradas: OLT conectada (`CONNECTED`).
- Salidas: `ConfigSnapshot` inmutable con:
  - Running-config.
  - Startup-config (si está disponible en vendor/versión).
  - Comandos adicionales acordados (estado de tarjetas, ONUs, potencia, etc.).

### 3.2. Parser

Responsable de **transformar snapshots en datos estructurados**:

- Lee snapshots sin modificarlos.
- Produce representaciones intermedias (DTOs, estructuras en memoria) de:
  - ONUs, VLANs, perfiles, puertos PON, uplinks.
  - Descripciones, notas de técnico, metadatos territoriales.

El parser es **determinista**: la misma entrada produce la misma salida.

### 3.3. Preview

Responsable de **comparar y proponer cambios**:

- Compara el estado observado estructurado con:
  - Inventario e históricos existentes.
  - Catálogos globales, técnicos, territoriales.
- Genera vistas de preview para:
  - Importación inicial.
  - Reconstrucción territorial (TRE, Zone/Nap/NapPort).
  - Saneamiento de inventario ONU.
  - Drift detection y sugerencias de provisión.

### 3.4. Inventario Deseado (Desired State)

Representa la **configuración aprobada** por OLT (ver sección 4).

### 3.5. Observed State

Representa el **estado real observado en la OLT** a partir de snapshots y comandos de monitoreo (ver sección 5).

### 3.6. Drift

Responsable de calcular y clasificar la **diferencia entre Desired State y Observed State** (ver sección 9):

- Determina qué objetos están sincronizados, qué falta en OLT, qué falta en sistema, qué sobra, qué entra en conflicto.
- Es la base para recomendaciones y planes de provisión.

### 3.7. Provisioning

Responsable de **planificar y ejecutar cambios controlados** en la OLT:

- Usa como entrada:
  - Desired State (inventario aprobado).
  - Drift calculado.
- Genera `ProvisioningPlan` que, una vez aprobado, se traduce en CLI ejecutable.

### 3.8. Auditoría

Responsable de **registrar todas las decisiones y ejecuciones** relevantes:

- Importaciones y confirmaciones.
- Cambios de inventario y catálogos.
- Ejecución de planes de provisión.
- Eventos de drift y resultados de sincronización.

La auditoría es transversal: acompaña a todas las capas.

---

## 4. Desired State

### 4.1. Qué representa

El **Desired State** es el **inventario aprobado y operativo** por OLT. Representa:

- Qué objetos **deben existir** en la OLT y cómo deben estar configurados.
- Qué relaciones lógicas y territoriales son válidas.
- Qué perfiles, VLANs, modos de servicio y catálogos están activos.

Es la proyección operacional del **inventario oficial**, lista para ser aplicada (o mantenida) en la OLT.

### 4.2. Qué objetos contiene

Sin ser exhaustivo, el Desired State agrupa por OLT:

- **OLT**: identidad, vendor, versión objetivo.
- **Catálogos técnicos activos**:
  - VLANs de servicio.
  - Perfiles GPON y de velocidad.
  - Tipos de ONU (`OnuType`).
  - Modos/plantillas de servicio ONU (`OnuServiceModeTemplate`).
  - Perfiles agregados (`ProfileCatalog`).

- **Catálogos territoriales activos**:
  - Zones.
  - Nap / ODN / ODB.
  - NapPorts.

- **Inventario lógico aprobado**:
  - ONUs aprobadas (serial, PON, VLAN, NAP/NapPort, Zone, modo de servicio, cliente vinculado cuando aplique).
  - `ProvisioningPlan` aprobados (históricos y vigentes) que describen cómo se llegó a ese estado.

### 4.3. Cómo se mantiene

El Desired State se mantiene mediante:

- Flujos controlados de **importación + preview + confirmación**.
- Flujos de **provisión** que actualizan inventario e historiales.
- Procesos de **saneamiento territorial y de calidad de datos**.

No se modifica nunca «a mano» en tablas críticas sin un flujo que deje traza de preview y aprobación.

### 4.4. Qué puede modificarlo

Pueden originar cambios en Desired State (siempre pasando por preview + aprobación):

- Confirmación de importaciones desde snapshots.
- Aplicación de planes de provisión (altas/bajas/cambios).
- Procesos de saneamiento (territorial, de catálogos técnicos, de modelo ONU).
- Operaciones explícitas de mantenimiento (por ejemplo, retiros de ONUs, cambios de perfiles comerciales).

En todos los casos:

- El cambio debe quedar **auditado**.
- Debe poder reconstruirse el estado previo a partir de inventario histórico y snapshots.

---

## 5. Observed State

### 5.1. Qué es

El **Observed State** es la representación estructurada del **estado real** de una OLT en un momento dado, tal como se observa vía:

- Snapshots (`show running-config`).
- Comandos de monitoreo (`show gpon onu state`, `show interface`, potencia óptica, alarmas).

Incluye tanto configuración como estado operativo.

### 5.2. Cómo se obtiene

- A partir de snapshots capturados (`ConfigSnapshot`) y sus parsers.
- A partir de consultas periódicas de monitoreo (comandos read-only) que actualizan datos operativos.

### 5.3. Qué representa

- La **configuración actual** que la OLT ejecuta.
- El **estado momentáneo** de ONUs, puertos y enlaces.
- Evidencia de cambios manuales o no controlados sobre la OLT.

Es la base para:

- Detectar drift respecto al Desired State.
- Proponer cambios de saneamiento.
- Verificar el resultado de un plan de provisión.

### 5.4. Qué NO representa

- No es, por sí solo, el inventario oficial.
- No sustituye a los catálogos técnicos ni territoriales como fuente de verdad.
- No autoriza cambios automáticos en inventario ni en la OLT.

El Observed State **describe**, pero no **decide**.

---

## 6. Snapshot

### 6.1. Running Config

Es la captura completa de `show running-config`:

- Debe incluir la configuración íntegra.
- Debe terminar en un **prompt estable** validado.
- Se almacena con:
  - Marca de tiempo.
  - OLT asociada.
  - Checksum (SHA-256 u otro).
  - Metadatos de captura (origen, operador, diagnóstico).

### 6.2. Startup Config

Cuando el vendor/versión lo permiten, se capturará también:

- `show startup-config` o equivalente.

Usos principales:

- Comparar running vs startup ante incidentes de pérdida de configuración.
- Reconstruir la intención de configuración persistida en la OLT.

### 6.3. Comandos adicionales

Además del running-config, pueden capturarse:

- `show card`, `show gpon onu state`, `show interface`, potencia óptica, alarmas, etc.

Estos comandos complementan el snapshot lógico y alimentan Observed State y Auditoría.

### 6.4. Periodicidad

- Debe definirse una **política de periodicidad** por OLT y entorno:
  - Snapshots de referencia (por ejemplo, antes y después de cambios mayores).
  - Snapshots periódicos para auditorías continuas.

### 6.5. Inmutabilidad

- Un snapshot es **inmutable**: no se sobreescribe ni edita.
- Cualquier corrección se hace mediante nuevos snapshots o metadatos adicionales, nunca modificando el texto original.

### 6.6. Versionado

- Los snapshots forman un **historial versionado** por OLT.
- Pueden etiquetarse puntos clave (antes de migración, después de saneamiento, etc.).

---

## 7. Inventario

### 7.1. Objetos administrados

El inventario oficial (Desired State + historial) abarca, al menos:

- **OLT**
  - Identidad, vendor, modelo, entorno, estado de ciclo de vida.

- **Recursos físicos y lógicos de OLT**
  - PON (puertos GPON/XG-PON).
  - Uplinks.
  - Slots/tarjetas (cuando se modelen).

- **Catálogos técnicos por OLT**
  - `Vlan`.
  - `GponProfile` / `SpeedProfile`.
  - `ProfileCatalog`.
  - `OnuType`.
  - `PonPort`.
  - `OltUplink`.
  - `OnuServiceModeTemplate`.
  - `ProvisioningTemplate` (global controlado, proyectado a OLT).

- **Catálogos territoriales por OLT**
  - `Zone`.
  - `Nap` (NAP/ODN/ODB, con tipo/prefijo).
  - `NapPort`.

- **Inventario de servicio**
  - `Onu`.
  - `ProvisioningPlan`.
  - `ServiceMode` / plantillas asociadas (a través de OnuServiceModeTemplate).

- **Otros objetos relevantes** (no exhaustivo)
  - `ServiceMode` derivado de `service_mode_code`.
  - `Olt` logical groups (clusters, entornos).
  - Etiquetas de calidad de datos (`data_quality_status`).

Este listado es conceptual y se alinea con `docs/EFO_GOBIERNO_DE_CATALOGOS.md` y `docs/EFO_MODELO_TERRITORIAL_FTTH.md`.

---

## 8. Sincronización

### 8.1. Principios

La sincronización entre inventario y OLT **nunca** modifica directamente el inventario a partir del estado observado.  
Siempre se sigue esta secuencia:

1. **Snapshot**
2. **Comparación (Parser + Drift)**
3. **Preview**
4. **Validación** (humana + reglas)
5. **Aprobación**
6. **Actualización de Inventario** y, según el caso, ejecución de cambios en la OLT.

### 8.2. Flujo de sincronización

1. **Captura de snapshot** de OLT.
2. **Parser** extrae Observed State.
3. **Comparador de drift** identifica diferencias entre Observed State e Inventario Deseado.
4. **Generación de preview** que clasifica cada diferencia (SYNC, CONFIG_MISMATCH, etc.).
5. **Validación**:
   - Aplicación de reglas de gobierno.
   - Evaluación de impacto.
6. **Aprobación** por operador:
   - Selección de qué diferencias se aceptan.
   - Generación de `ProvisioningPlan` cuando haga falta tocar la OLT.
7. **Ejecución** (cuando corresponda):
   - Aplicación de CLI controlada.
   - Confirmación mediante snapshot posterior.

En ningún caso se permite que el Observed State sobrescriba inventario sin este flujo.

---

## 9. Drift Detection

### 9.1. Categorías de drift

Se definen las siguientes categorías conceptuales de drift entre Desired State y Observed State:

1. **SYNC**
   - El objeto está presente tanto en inventario como en la OLT.
   - Sus atributos relevantes coinciden dentro de tolerancias definidas.

2. **CONFIG_MISMATCH**
   - El objeto existe en ambos lados pero con diferencias relevantes de configuración.
   - Ejemplos:
     - ONU con VLAN distinta a la aprobada.
     - ONU en NAP/Zone distinta a la esperada.
     - Perfil de velocidad o modo de servicio divergente.

3. **MISSING_IN_OLT**
   - El objeto existe en inventario aprobado pero **no** se encuentra en la OLT.
   - Ejemplos:
     - ONU dada de alta en inventario pero ausente en running-config.
     - VLAN definida en inventario pero no configurada en la OLT.

4. **MISSING_IN_SYSTEM**
   - El objeto se observa en la OLT pero **no** existe en inventario.
   - Ejemplos:
     - ONU presente en OLT nunca importada/adoptada.
     - VLAN o perfil local sin entrada equivalente en catálogos.

5. **EXTRA_OBJECT**
   - Subconjunto de `MISSING_IN_SYSTEM` en el que el objeto es claramente residual o no debería existir desde la perspectiva del Desired State.
   - Ejemplos:
     - ONU de pruebas que debió ser dada de baja.
     - VLAN ya retirada en inventario pero aún presente en configuración.

6. **CONFLICT**
   - Se detectan inconsistencias internas o imposibles de resolver automáticamente.
   - Ejemplos:
     - Dos objetos de inventario apuntando al mismo recurso físico.
     - Colisiones de identidad territorial (NAP/ODN/ODB ambiguos).
     - ONUs que violan invariantes de pertenencia de OLT.

7. **UNMANAGED_OBJECT**
   - Objetos presentes en la OLT que el sistema **decide explícitamente no gestionar**.
   - Pueden ser:
     - Recursos de vendor o sistema que no forman parte del dominio TOI.
     - Objetos marcados como externos o fuera de alcance.

Estas categorías alimentan reportes, dashboards y recomendaciones, y son insumo directo para la generación de planes de provisioning.

---

## 10. Recuperación

La arquitectura operativa debe contemplar escenarios de recuperación y reconstrucción a partir de snapshots e inventario.

### 10.1. Reemplazo de OLT

Escenario: una OLT es reemplazada por otra (fallo hardware, actualización mayor, migración).

Lineamientos:

- El inventario oficial de la OLT antigua se conserva como referencia.
- Se modela la nueva OLT (nuevo `olt_id`) y se decide qué partes del Desired State se migran:
  - ONUs, VLANs, perfiles, NAPs, etc.
- La migración debe:
  - Generar **nuevos ProvisioningPlan** para la OLT destino.
  - Capturar snapshots antes/después de la migración.
  - Mantener historial completo en la OLT origen (ahora `RETIRED`).

### 10.2. Pérdida de Startup Config

Escenario: la OLT pierde su startup-config pero conserva parte de la running-config o viceversa.

Lineamientos:

- Utilizar el inventario oficial y snapshots históricos como referencia.
- Generar un plan de recuperación que:
  - Restaure configuraciones críticas (VLANs, perfiles, ONUs) desde Desired State.
  - Evite reintroducir deuda histórica ya saneada.
- Ejecutar siempre bajo preview + aprobación + snapshot posterior.

### 10.3. Running Config no guardado

Escenario: se aplican cambios en running-config sin guardar a startup-config.

Lineamientos:

- Detectar divergencias running vs startup mediante comandos y snapshots.
- Clasificar drift específico de persistencia.
- Definir planes de corrección:
  - Guardar cambios legítimos (mediante plan de provisioning que los consolide).
  - Revertir cambios no aprobados restableciendo Desired State.

### 10.4. Recuperación completa

- Objetivo: alinear una OLT severamente dañada con el Desired State aprobado más reciente.
- Requisitos:
  - Inventario oficial consistente.
  - Snapshots históricos suficientes para comprender el estado previo.
- Flujo:
  1. Snapshot actual (aunque esté degradado).
  2. Análisis de drift extremo.
  3. Generación de plan de reconstrucción completa (VLANs, perfiles, ONUs, NAPs si aplica).
  4. Ejecución controlada por fases con snapshots intermedios.

### 10.5. Recuperación parcial

- Objetivo: recuperar sólo un subconjunto de recursos (ej. una PON, un grupo de ONUs, un NAP).
- Flujo:
  - Similar a la recuperación completa pero acotado por filtros (OLT, PON, zona, NAP, cliente).

### 10.6. Reconstrucción desde inventario

En todos los casos, el **inventario oficial** es la referencia primaria para reconstruir configuración:

- Snapshots proporcionan evidencia histórica y contexto, pero la decisión final se basa en Desired State.

---

## 11. Provisioning

### 11.1. Principios

Todo flujo de provisión sigue el pipeline:

1. **Inventario** (Desired State candidato).
2. **Generación de ProvisioningPlan**.
3. **Ejecución controlada en OLT**.
4. **Snapshot posterior**.
5. **Validación de resultado y actualización de inventario**.

### 11.2. Casos de uso

- **Alta ONU**
  - Crear ONU en inventario aprobado.
  - Generar CLI para alta (VLAN, perfil, NAP/NapPort, modo de servicio).
  - Ejecutar en OLT.
  - Capturar snapshot y validar que la ONU está presente y coherente.

- **Baja ONU**
  - Marcar ONU para retiro en inventario.
  - Generar CLI de baja (desconfiguración de ONU, limpieza asociada).
  - Ejecutar, snapshot, validar.

- **Cambio de VLAN**
  - Ajustar Desired State de ONU (VLAN/servicio).
  - Generar CLI correspondiente (vlan-filter, flows, perfiles si aplica).
  - Ejecutar, snapshot, validar.

- **Cambio de Profile**
  - Cambiar perfiles de velocidad o plantillas ONU.
  - Alinear catálogos técnicos y Desired State.
  - Ejecutar, snapshot, validar.

- **Cambio de Zona / NAP / NapPort**
  - Reasignar ONU territorialmente (por ejemplo, migración física).
  - Ajustar referencias territoriales en inventario (Zone/Nap/NapPort) mediante flujos de saneamiento.
  - Generar plan que actualice descripciones, CLI relacionada y asegurarse de que las invariantes territoriales se mantienen.

- **Cambio de Service Mode**
  - Cambiar sólo cuando existan plantillas (`OnuServiceModeTemplate`) definidas y aprobadas.
  - Actualizar Desired State y ejecutar el cambio.

En todos los casos, la secuencia **Inventario → OLT → Snapshot → Validación** es obligatoria.

---

## 12. Auditoría

Todo cambio relevante debe quedar auditado. Cada evento de cambio (import, provisioning, saneamiento, recuperación) debe registrar al menos:

- **Quién**: identidad del operador (humano o sistema autorizado).
- **Cuándo**: fecha y hora.
- **Qué cambió**: resumen estructurado del cambio (antes → después).
- **Snapshot origen**: identificador(es) de snapshot(s) usados como evidencia de partida.
- **Snapshot destino**: snapshot(s) posteriores usados para validar el resultado.
- **CLI generado**: comandos producidos por el plan (texto o referencia segura).
- **Resultado**: éxito, fallo parcial, rollback, incidencias.

Esta auditoría debe ser **inmutable** y consultable a largo plazo, especialmente para:

- Ondas de provisión masiva.
- Saneamientos territoriales.
- Migraciones de OLT.

---

## 13. Compatibilidad Multivendor

La arquitectura operativa debe ser válida para múltiples vendors (ZTE, VSOL, Huawei, FiberHome, etc.) **sin modificar el núcleo**.

Principios:

- Definir un **modelo lógico común** de Desired/Observed State e inventario.
- Implementar **drivers, parsers y adaptadores por vendor** que proyecten:
  - Snapshots vendor-específicos → modelo común de Observed State.
  - CLI generada desde ProvisioningPlan → comandos específicos por vendor.

El núcleo (inventario, Desired State, drift, auditoría, catálogos) permanece estable; sólo cambian:

- Formatos de snapshot.
- Parsers.
- Adaptadores de provisioning.

---

## 14. IA

La IA puede asistir en múltiples capas, bajo las siguientes restricciones:

- **Nunca ejecutar cambios automáticamente en OLT**.
- **Nunca modificar inventario directamente** sin pasar por preview + aprobación.

Ámbitos de ayuda:

- **Clasificación**
  - Clasificar ONUs por modo de servicio, perfil, zona, NAP, tipo de cliente.
  - Etiquetar drift según severidad e impacto esperado.

- **Reconstrucción**
  - Proponer catálogos territoriales a partir de descripciones y evidencia histórica.
  - Completar catálogos técnicos basados en patrones observados.

- **Auditoría**
  - Priorizar issues críticos.
  - Agrupar incidentes similares.
  - Sugerir acciones mitigadoras.

- **Detección de anomalías**
  - Identificar comportamientos atípicos en ONUs, puertos, VLANs, perfiles.
  - Detectar cambios manuales no documentados en la OLT.

- **Generación de CLI**
  - Proponer bloques de comandos para planes de provisión, siempre bajo supervisión humana.

La IA es un **asistente experto**, nunca un actor autónomo sobre producción.

---

## 15. Invariantes

Las siguientes reglas **nunca deben romperse** en la arquitectura operativa:

1. **Nunca modificar un Snapshot**.
   - Los textos capturados (running/startup-config, comandos) son inmutables.

2. **Nunca editar inventario crítico directamente**.
   - Cambios en ONUs, catálogos técnicos y territoriales deben pasar por flujos de preview + aprobación.

3. **Todo cambio debe quedar auditado**.

4. **Toda ONU pertenece a una sola OLT**.

5. **Todo NAP pertenece a una sola OLT**.

6. **Toda Zona pertenece a una sola OLT**.

7. **Todo NapPort pertenece a una sola OLT**.

8. **Todo ProvisioningPlan pertenece a una sola OLT**.

9. **Toda sincronización relevante genera al menos un Snapshot**.

10. **Toda restauración genera Snapshot** (antes y después cuando sea posible).

11. **Toda modificación operativa termina con validación**.
    - Validación técnica (drift, estado ONU, alarmas).
    - Validación documental/auditable.

12. **Observed State nunca sobreescribe inventario directamente**.

13. **Importaciones nunca eliminan manualmente inventario sin revisión**.

14. **Scoping estricto por OLT** para todos los objetos con `olt_id`.

15. **No reutilizar catálogos territoriales entre OLTs**.

16. **Preservar prefijos NAP/ODN/ODB en identidad canónica**.

17. **Preview antes de Apply** en cambios masivos o estructurales.

18. **Drivers y parsers son siempre read-only** respecto a la OLT.

19. **Provisioning sólo se ejecuta mediante planes aprobados**.

20. **Toda ejecución de CLI está asociada a un ProvisioningPlan** y a un operador.

21. **Datos operativos no cambian inventario** (sólo aportan contexto).

22. **No compartir ONUs, Zones, NAPs ni NapPorts entre OLTs**.

23. **Cualquier cambio de pertenencia de recursos (migraciones)** debe materializarse como nuevos registros y planes, nunca como reasignación silenciosa.

24. **La IA no puede ejecutar cambios ni alterar inventario sin aprobación humana explícita**.

25. **Toda OLT en estado ADOPTED debe tener políticas de snapshot y recuperación definidas**.

26. **Los flujos de recuperación (completa o parcial) se tratan como provisión controlada**, con planes, snapshots y auditoría completos.

Esta lista no es cerrada; nuevas invariantes podrán añadirse en futuras versiones de la EFO, pero nunca relajarse sin decisión explícita documentada.

---

## 16. Roadmap Operativo (P6.x)

El roadmap se organiza en fases P6.x para completar el ciclo operativo completo sobre la base de P4 (modelo territorial) y P5 (consola de auditoría):

- **P6.1 – Formalización de Desired/Observed State y Drift**
  - Definir y documentar el modelo lógico de Desired State y Observed State por OLT, alineado con esta EFO.
  - Introducir (a nivel documental y de servicios internos) un módulo de Drift Detection que clasifique diferencias según las categorías de la sección 9.
  - No cambiar aún el esquema de BD; trabajar con vistas y DTOs.

- **P6.2 – Inventario oficial y adopción de OLTs**
  - Definir criterios formales para que una OLT pase a estado `ADOPTED`.
  - Documentar y preparar tooling para declarar un corte de «inventario aprobado» por OLT.
  - Integrar la noción de OLT adoptada en los reportes y la consola de auditoría.

- **P6.3 – Sincronización asistida y planes de saneamiento**
  - Utilizar Drift Detection para generar propuestas de saneamiento (cambios en inventario y/o OLT).
  - Diseñar previews específicos de drift (por OLT, por PON, por zona).
  - Definir políticas de aceptación automática sólo para cambios de bajo riesgo, siempre sujetos a aprobación final.

- **P6.4 – Provisioning operacional completo sobre inventario oficial**
  - Alinear todos los flujos de alta/baja/cambio ONU, cambios de VLAN/perfil/modo/territorio con Desired State.
  - Garantizar que ningún flujo de provisión bypassa el inventario.
  - Extender tests y auditorías para cubrir todo el ciclo Inventario → OLT → Snapshot → Validación.

- **P6.5 – Recuperación automatizada asistida**
  - Diseñar planes de recuperación (completa y parcial) basados en Desired State + snapshots.
  - Añadir vistas de simulación de recuperación (qué ocurriría si aplicamos este plan).
  - Incluir recomendaciones basadas en IA para priorizar acciones de recuperación.

- **P6.6 – Multivendor operativo**
  - Extender el modelo a nuevos vendors (VSOL, Huawei, FiberHome) mediante drivers y parsers específicos.
  - Validar que la arquitectura de Desired/Observed State, drift y provisioning funciona sin cambios en el núcleo.

- **P6.7 – Optimización OSS FTTH**
  - Integrar métricas de capacidad, calidad de servicio y planificación de expansión.
  - Conectar con GIS, CRM/ERP y otros sistemas OSS/BSS manteniendo el mismo modelo operativo.

Cada fase P6.x deberá respetar esta EFO y coordinarse con las EFO existentes (`EFO_GOBIERNO_DE_CATALOGOS`, `EFO_MODELO_TERRITORIAL_FTTH`, `EFO_MODELO_OPERACIONAL_ONU`, etc.).
