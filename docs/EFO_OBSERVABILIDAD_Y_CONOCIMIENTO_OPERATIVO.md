# Especificación Funcional Oficial

## Observabilidad y Conocimiento Operativo en Admin OLT TOI

Versión: 1.0  
Fecha: 2026-06-24  
Ámbito: Proyecto TOI OLT Manager (multi-OLT, multi-vendor, OSS FTTH)

---

## 1. Objetivo

Este documento define la **capa de Observabilidad y Conocimiento Operativo** de Admin OLT TOI. Su propósito es:

- Proveer al personal técnico una visión clara, en tiempo casi real, del **estado operativo actual** y del **histórico relevante** de:
  - OLTs.
  - PON ports.
  - Uplinks.
  - ONUs.
  - NAP/ODN/ODB.
  - Zonas.
- Unificar métricas, alertas, eventos e históricos bajo un modelo coherente de **Operations** y **Knowledge**, alineado con las EFO existentes de:
  - Gobierno de Catálogos.
  - Modelo Territorial FTTH.
  - Arquitectura Operativa (Desired/Observed State, Drift, Provisioning, Auditoría).
- Habilitar una capa de **recomendaciones asistidas por IA** basada en evidencia operacional, **sin ejecutar cambios** ni modificar inventario por sí misma.

> Importante: esta EFO es **exclusivamente conceptual y documental**. No introduce cambios de código, BD, migraciones ni endpoints, y no autoriza conexiones adicionales a OLTs.


---

## 2. Separación de capas

Se definen cinco capas lógicas que encadenan inventario, configuración, operación y automatización:

1. **Inventory**  
2. **Configuration**  
3. **Operations**  
4. **Knowledge**  
5. **Automation**

Estas capas se apoyan en la arquitectura operativa existente (Desired State, Observed State, Drift, Provisioning, Auditoría) y en la clasificación de catálogos (Globales, Técnicos por OLT, Territoriales, Operativos).

### 2.1. Inventory

Representa el **inventario aprobado y persistente** de Admin OLT TOI:

- OLTs, PON ports, uplinks, ONUs, VLANs, perfiles, Zones, NAP/ODN/ODB, NapPorts, etc.
- Es la proyección operativa del **Desired State** (ver EFO de Arquitectura Operativa).
- Es la **fuente de verdad canónica** sobre qué recursos existen, dónde y con qué configuración aprobada.

Restricciones:

- Inventory **no cambia automáticamente** por efecto de métricas, observabilidad ni IA.
- Cualquier modificación de inventario requiere flujos explícitos de preview → aprobación → apply (Provisioning, saneamiento, import confirmada).

### 2.2. Configuration

Capa responsable de **definir y materializar** la configuración deseada sobre las OLTs:

- Desired State detallado (perfiles, VLANs, modos ONU, asignaciones territoriales, etc.).
- Planes de provisión (`ProvisioningPlan`) que describen cómo llevar el Desired State a la OLT.

Relación con Observabilidad:

- La configuración proporciona el **referente normativo** frente al que se mide el estado observado (drift).
- La capa de Observabilidad puede comparar estados observados con Desired State, pero **no está autorizada** a modificar ni Desired State ni inventario directamente.

### 2.3. Operations

Capa responsable de la **observabilidad en tiempo casi real** y de los **datos operativos dinámicos**:

- Estados actuales: online/offline, potencia óptica, utilización de enlaces, alarmas activas, flaps.
- Métricas en tiempo real y series temporales (históricos) de:
  - Potencia óptica (ONU/PON/NAP/Zona).
  - Tráfico (OLT, PON, uplinks, ONU).
  - Disponibilidad y uptime.
  - Alarmas y eventos.
- Deriva principalmente de **Observed State** (snapshots + monitoreo periódico) y de catálogos **Operativos** (OnuStatus, PowerHistory, Alarm/Event, ConfigSnapshot, ImportJob, etc.).

Características clave:

- La capa **Operations se actualiza continuamente** a partir de lecturas read-only, tareas programadas y eventos internos.
- Puede recalcular métricas y estados sin tocar inventario.
- Es la base para dashboards operativos, fichas técnicas y alertas.

### 2.4. Knowledge

Capa responsable de transformar datos operativos e históricos en **conocimiento operativo estructurado**:

- Deriva patrones, tendencias y riesgos a partir de históricos (power, status, uptime, tráfico, alarmas, drift, snapshots).
- Reconoce comportamientos típicos y atípicos (degradaciones progresivas, zonas con incidencias recurrentes, PON próximas a saturación, etc.).
- Genera **indicadores derivados** (por ejemplo, Health Scores) y **explicaciones** basadas en evidencia.

Aclaraciones:

- **Knowledge se construye con históricos**; no se limita al estado actual.
- Sus conclusiones se almacenan como conocimiento operativo (por ejemplo, "NAP H5 con múltiples incidencias ópticas"), pero **no modifican inventario**.

### 2.5. Automation

Capa responsable de **proponer acciones** a partir del conocimiento operativo y del drift:

- Sugerencias de planes de provisión, saneamiento, expansión de capacidad, mantenimiento preventivo.
- Generación de recomendaciones asistidas por IA (ver sección 12).

Restricciones obligatorias:

- **Automation propone, pero no ejecuta sin aprobación.**
- Ninguna acción de Automation puede:
  - Crear, modificar o borrar inventario sin pasar por flujos formales (preview → aprobación → apply).
  - Ejecutar CLI en OLT sin un `ProvisioningPlan` aprobado.


---

## 3. Observabilidad de OLT

La observabilidad de OLT consolida el estado operativo actual y el historial relevante de cada OLT administrada.

### 3.1. Datos actuales

Para cada OLT se deben poder consultar, al menos, los siguientes datos **actuales** (Observed State):

- Estado de conectividad: `online` / `offline` / `degraded` (según políticas definidas).
- Uptime actual.
- Último reinicio conocido (fecha/hora) a partir de versión, contadores o eventos.
- Causa probable de reinicio si existe evidencia suficiente (evento registrado, cambio de versión, incidente documentado).
- Utilización de recursos:
  - CPU.
  - Memoria.
  - Temperatura global y, cuando exista, por tarjeta.
  - Fuente de energía / alimentación (presente/fallo/backup) cuando el vendor lo soporte.
- Alarmas activas a nivel de OLT.
- Eventos recientes relevantes:
  - Cambios de estado de OLT.
  - Cambios de versión.
  - Cambios de tarjetas/slots.
  - Eventos críticos de enlaces o PON.
- Estado de tarjetas/slots:
  - Presencia/ausencia.
  - Estado operativo (`up` / `down` / `degraded`).
- Estado de PON ports:
  - Número de puertos activos.
  - Puertos con ONUs.
  - Puertos con errores o saturación.
- Estado de uplinks:
  - Enlaces físicos `up/down`.
  - Velocidad negociada.
  - Indicadores de errores.
- Tráfico por uplink (ancho de banda actual subida/bajada).
- Disponibilidad actual (porcentaje de tiempo `online` en la ventana reciente).

### 3.2. Históricos de OLT

Para cada OLT se recomienda mantener, al menos:

- **Histórico de tráfico** por uplink y, cuando sea relevante, por PON.
- Historial de disponibilidad (por ventanas de tiempo configurables).
- Historial de alarmas y eventos críticos.
- Historial de reinicios (fecha, causa probable, evidencia asociada: snapshot, evento, notas).
- Historial resumido de utilización de CPU/memoria/temperatura.

Este historial alimenta la capa de **Knowledge** (tendencias, patrones de falla, cálculo de Health Scores) sin alterar el inventario.


---

## 4. Observabilidad de PON

La observabilidad de PON se centra en el estado operativo de cada puerto PON y su relación con las ONUs conectadas.

Para cada PON port se deben exponer, como mínimo:

- **Estado del puerto**:
  - `up` / `down` / `admin_down` / `degraded`.
  - Errores de nivel físico o de protocolo.
- **ONUs registradas** en el puerto:
  - Conteo total.
  - Lista resumida de ONUs asociadas.
- **ONUs online/offline**:
  - Número y porcentaje de ONUs `online`.
  - Número y porcentaje de ONUs `offline` o `flapping`.
- **Ocupación del puerto**:
  - Puestos usados vs capacidad teórica.
  - Umbrales de ocupación (por ejemplo, advertencia >70 %, crítico >85 % de puertos/ONUs usados según política).
- **Potencia TX/RX agregada** (cuando aplique y sea visible a nivel de PON):
  - Rangos típico/mínimo/máximo de potencia observada para las ONUs del puerto.
- **Errores asociados al puerto**:
  - Errores físicos (por ejemplo, BIP/FEC).
  - Errores de señal (LOS, LOF, LOB).
- **Eventos asociados**:
  - Altas/bajas masivas de ONUs.
  - Cambios de estado significativos.
- **Histórico de cambios**:
  - Evolución de número de ONUs.
  - Cambios frecuentes de estado (`up/down`).
  - Historial de errores y alarmas asociadas.
- **Saturación o sobreocupación**:
  - Indicadores de proximidad a capacidad máxima.
  - Señales de congestión o degradación de calidad.
- **Alertas por caída masiva de ONUs**:
  - Detección de descensos simultáneos o en ventana corta de un porcentaje significativo de ONUs en el mismo PON.
  - Correlación con eventos de uplink, OLT, NAP o zona.


---

## 5. Observabilidad de Uplinks

La observabilidad de uplinks es crítica para anticipar saturaciones y cortes que afectan a múltiples PONs y zonas.

Para cada uplink se deben modelar:

- **Estado físico**:
  - `up` / `down` / `admin_down` / `degraded`.
  - Detección de enlaces intermitentes (flap).
- **Velocidad negociada**:
  - Velocidad actual (`1G`, `10G`, etc.).
  - Capacidad teórica vs capacidad efectiva (por ejemplo, LAGs, agregación de enlaces).
- **Tráfico actual**:
  - Ancho de banda instantáneo (`in/out`).
  - Porcentaje de utilización frente a la capacidad.
- **Tráfico histórico**:
  - Series temporales de utilización.
  - Picos de tráfico y su frecuencia.
- **Errores y drops**:
  - Errores físicos.
  - Paquetes descartados.
  - Colisiones, si aplica.
- **Flap del enlace**:
  - Conteo de cambios `up/down` por ventana de tiempo.
  - Clasificación de enlaces inestables.
- **Utilización pico**:
  - Máxima utilización registrada por intervalos (hora/día/semana/mes).
- **Disponibilidad**:
  - Porcentaje de tiempo `up` vs `down`.
- **Alertas por saturación**:
  - Umbrales configurables (ej. `warning` >70 %, `critical` >90 % de utilización sostenida).
  - Detección de congestión recurrente en horas pico.
- **Alertas por caída**:
  - Detección inmediata de `down`.
  - Correlación con caídas masivas en PON/ONUs.


---

## 6. Observabilidad de ONU

La ficha operativa de ONU es el principal punto de diagnóstico a nivel de abonado.

Para cada ONU, la capa de Observabilidad debe exponer, como mínimo:

- **Estado online/offline** actual.
- **Uptime** desde el último arranque.
- **Última caída** registrada (fecha/hora, causa probable si existe evidencia).
- **Última reconexión** (fecha/hora).
- **RX power** actual.
- **TX power** actual (cuando esté disponible).
- **Histórico RX/TX**:
  - Series temporales de potencia óptica.
  - Identificación de rangos normales por modelo y PON.
- **Distancia estimada** si el vendor lo provee.
- **Atenuación estimada** (por ONU, por tramo hacia NAP cuando se pueda derivar).
- **Cambios de potencia**:
  - Detección de degradación gradual o cambios bruscos.
  - Identificación de saltos asociados a intervenciones (mantenimiento, reempalmes, cambios de NAP).
- **Alarmas relevantes**:
  - `dying gasp`.
  - `LOS` (Loss of Signal).
  - Alarmas críticas reportadas por la ONU o la OLT.
- **Patrones de degradación óptica**:
  - Temporales (por horario, clima, etc.).
  - Asociados a eventos de planta externa.
- **Flapping**:
  - Conteo de cambios `online/offline` en ventana de tiempo.
  - Clasificación de ONUs inestables.
- **Modo router/bridge observado** (desde Observed State / comportamiento ONU) sin asumir que sea el deseado.
- **VLAN observada** (WAN/servicio efectiva).
- **Perfil observado** (perfiles de velocidad o plantillas efectivas).
- **Comparación contra Desired Configuration**:
  - Drift entre configuración observada vs inventario aprobado.
  - Marcadores claros de divergencia (VLAN distinta, perfil distinto, modo distinto, NAP/Zone diferente, etc.).


---

## 7. Históricos

La observabilidad no se limita al estado actual; debe registrar **historial suficiente** para diagnóstico, auditoría y planificación.

### 7.1. Tipos de históricos

Se recomienda mantener, al menos, los siguientes históricos:

- **Power history**:
  - Potencia RX/TX por ONU.
  - Agregados por PON, NAP y Zona.
- **Status history**:
  - Cambios de estado online/offline por ONU, PON, uplink, OLT.
- **Uptime history**:
  - Historial de uptime y reinicios por ONU y OLT.
- **Traffic history**:
  - Tráfico por uplink, PON y, cuando aplique, por ONU.
- **Alarm history**:
  - Alarmas generadas, reconocidas, resueltas; severidad y duración.
- **Event history**:
  - Eventos operativos relevantes (cambios de config observada, flaps, cortes, intervenciones documentadas).
- **Config snapshot history**:
  - Historial de snapshots (running/startup-config, comandos complementarios), siempre inmutable.
- **Drift history**:
  - Registros de diferencias detectadas entre Desired State y Observed State.
  - Clasificación por tipo de drift (SYNC, CONFIG_MISMATCH, MISSING_IN_OLT, etc.).

### 7.2. Usos de los históricos

Los históricos sirven para:

- **Diagnóstico**:
  - Entender qué ocurrió antes de una caída o degradación.
  - Confirmar si un problema es puntual o recurrente.
- **Auditoría**:
  - Reconstruir la secuencia de eventos, alertas y cambios ante incidentes.
  - Verificar que las intervenciones siguieron los flujos aprobados.
- **Tendencias**:
  - Identificar degradaciones ópticas graduales.
  - Detectar evolución de ocupación de PON, NAP y zonas.
  - Observar el crecimiento de tráfico en uplinks.
- **Recuperación**:
  - Proveer contexto a flujos de recuperación completa o parcial (ver EFO de Arquitectura Operativa).
  - Determinar el último estado conocido estable.
- **Planificación**:
  - Planificar expansión de capacidad (PON, uplinks, NAP, planta externa).
  - Priorizar inversiones según históricos de saturación y degradación.


---

## 8. Alertas

La capa de alertas debe apoyarse en métricas e históricos, con umbrales configurables y reglas claras. Aquí se definen **alertas mínimas** recomendadas.

### 8.1. Alertas de OLT

- OLT **offline** (pérdida de conectividad prolongada).
- **Reboot detectado** (cambio de uptime, cambio de versión, eventos asociados).
- **Divergencia running/startup** significativa:
  - Diferencias persistentes entre running-config y startup-config.
  - Posibles cambios no guardados o no aprobados.
- **Alta CPU / memoria / temperatura**:
  - Umbrales de advertencia y crítico, con histograma temporal.
- **Uplink caído**:
  - Caída de uno o más uplinks críticos.
- **Tráfico saturado**:
  - Utilización sostenida por encima de umbrales definidos.

### 8.2. Alertas de PON

- **Caída masiva de ONUs** en el mismo PON.
- **Puerto PON down** o degradado.
- **Ocupación crítica**:
  - Número de ONUs/puertos usados cerca o por encima de la capacidad práctica.

### 8.3. Alertas de ONU

- ONU **offline** durante más tiempo que el umbral esperado.
- **Flapping** (múltiples cambios online/offline en ventana corta).
- **RX bajo** o fuera de rango aceptable.
- **Degradación progresiva** de potencia (tendencia negativa sostenida).
- **Dying gasp** recibido.
- **Pérdida de potencia** brusca.
- **Diferencia contra configuración deseada**:
  - Drift crítico (por ejemplo, VLAN o perfil distintos en una ONU crítica).

### 8.4. Alertas de NAP/Zona

- **Múltiples ONUs degradadas** asociadas al mismo NAP.
- **Múltiples caídas en la misma zona**.
- **Patrones de falla recurrente**:
  - Incidencias repetidas en NAP/ODN/ODB específicos.
  - Correlación con cortes de planta externa o energía.

> Nota: las alertas **no ejecutan acciones por sí mismas**. Disparan notificaciones y alimentan la capa de Knowledge y de recomendaciones asistidas.


---

## 9. Tendencias

Las tendencias permiten anticipar problemas antes de que se materialicen en incidentes visibles.

Se recomienda implementar análisis de tendencias, al menos, para:

- **Degradación óptica por ONU**:
  - Pendiente de RX/TX a lo largo del tiempo.
  - Identificación de ONUs con degradación gradual.
- **Degradación promedio por NAP**:
  - Cambio medio de potencia de las ONUs asociadas.
  - Señales de problemas en empalmes, splitters o conectores compartidos.
- **Degradación por zona**:
  - Agrupación territorial (Zone → NAP/ODN/ODB → ONUs).
  - Detección de sectores con planta externa envejecida o problemática.
- **Crecimiento de ocupación PON**:
  - Evolución del número de ONUs por PON.
  - Identificación de PON próximos a saturación.
- **Crecimiento de tráfico uplink**:
  - Tendencias diarias, semanales y mensuales.
  - Identificación de horas pico y patrones estacionales.
- **Frecuencia de reinicios OLT**:
  - Número de reinicios por periodo.
  - Clasificación de OLTs inestables.
- **Frecuencia de caídas por zona**:
  - Conteos de incidentes por zona territorial.
  - Priorización de zonas para saneamiento de planta externa.
- **Clientes críticos afectados**:
  - Cruce entre incidentes y clientes marcados como críticos.
  - Indicadores de impacto operativo y reputacional.


---

## 10. Health Scores

Los **Health Scores** son indicadores agregados que resumen la salud de un elemento técnico o territorial. Deben ser **explicables** y basarse en métricas observables.

Se definen Health Scores, al menos, para:

- OLT.
- PON.
- Uplink.
- ONU.
- NAP/ODN/ODB.
- Zona.

### 10.1. Factores de ejemplo

#### 10.1.1. ONU Health

Factores considerados (no exhaustivos):

- Estado actual (online/offline, flapping).
- RX/TX actuales y históricos.
- Tendencia óptica (degradación o estabilidad).
- Eventos recientes (caídas, cambios de potencia, cambios de PON/NAP).
- Flapping (número de cambios de estado).
- Alarmas asociadas (LOS, dying gasp, otras alarmas críticas).
- Drift de configuración (diferencias entre Desired State y Observed State).
- Calidad de datos (cuando exista `data_quality_status`).

#### 10.1.2. OLT Health

Factores considerados (no exhaustivos):

- Disponibilidad histórica.
- Uptime y frecuencia de reinicios.
- Alarmas activas y recientes.
- Utilización de CPU/memoria/temperatura.
- Estado y utilización de uplinks.
- Estado de PONs (porcentaje de PON degradados, caídas masivas de ONUs).
- Eventos significativos (cambios de versión, cortes, incidencias mayores).
- Drift acumulado entre Desired State y Observed State.

#### 10.1.3. Otros Health Scores

- **PON Health**:
  - Ocupación, caídas masivas, degradaciones ópticas agregadas, estabilidad de ONUs.
- **Uplink Health**:
  - Disponibilidad, saturación, flaps, errores y drops.
- **NAP/ODN/ODB Health**:
  - Porcentaje de ONUs asociadas con buena potencia.
  - Número de incidentes recientes.
  - Tendencias de degradación óptica agregada.
- **Zona Health**:
  - Agregación de Health Scores de NAPs y ONUs.
  - Historial de incidentes y cortes.

> Regla obligatoria: todo Health Score debe ser **desglosable y explicable** (qué factores y pesos lo componen), nunca una "caja negra" ininteligible.


---

## 11. Knowledge Layer

La **Knowledge Layer** representa el conocimiento operativo consolidado a partir de datos, históricos y experiencias previas.

### 11.1. Definición

Conocimiento operativo es la **interpretación estructurada** de los datos operativos, que permite responder preguntas como:

- ¿Qué ONUs están degradándose gradualmente?
- ¿Qué NAPs y zonas concentran más incidencias?
- ¿Qué PONs están próximas a saturación?
- ¿Qué uplinks muestran patrones de tráfico preocupantes?
- ¿Qué OLTs presentan reinicios repetidos o drift persistente?

### 11.2. Ejemplos de conocimiento operativo

- **ONU con degradación gradual**:
  - Historial de RX/TX muestra caída progresiva en semanas/meses.
  - Asociada a cambios en planta externa o conectores.
- **NAP con múltiples incidencias**:
  - Varias ONUs con degradación óptica o flapping.
  - Incidentes repetidos en la misma caja o tramo.
- **Zona con cortes recurrentes**:
  - Alta frecuencia de incidentes por causas similares.
  - Correlación con fallas de energía o infraestructura.
- **PON próximo a saturación**:
  - Ocupación y tráfico cercanos a límites aceptables.
  - Riesgo de degradación de servicio ante nuevas altas.
- **Uplink con tráfico pico frecuente**:
  - Picos que superan umbrales críticos en horarios previsibles.
  - Necesidad de ampliación de capacidad o balanceo.
- **OLT con reinicios repetidos**:
  - Patrón de reinicios no planificados.
  - Correlación con cambios de versión, fallos de energía o errores de hardware.

El Knowledge Layer **no toma decisiones ni ejecuta cambios**; provee contexto para que operaciones decida.


---

## 12. Recomendaciones asistidas

La capa de recomendaciones asistidas, potencialmente apoyada en IA, traduce el conocimiento operativo en **sugerencias de acción** para el personal técnico.

### 12.1. Tipos de recomendaciones

Ejemplos de recomendaciones posibles:

- **Revisar empalme**:
  - Cuando varias ONUs de un mismo NAP muestran degradación similar.
- **Revisar conector**:
  - Cuando la degradación se concentra en una sola ONU o en un pequeño grupo.
- **Revisar NAP**:
  - Cuando existe correlación entre incidentes y un NAP/ODN/ODB concreto.
- **Revisar energía de zona**:
  - Cuando se detectan caídas simultáneas en un área geográfica.
- **Planificar expansión PON**:
  - Cuando la ocupación y el tráfico del PON se acercan sistemáticamente a límites seguros.
- **Aumentar capacidad de uplink**:
  - Cuando la utilización pico de uplink supera umbrales críticos de forma recurrente.
- **Revisar configuración ONU**:
  - Cuando existe drift persistente entre Desired State y Observed State.
- **Guardar running-config en startup-config**:
  - Cuando se detecta divergencia persistente running/startup.
- **Ejecutar snapshot de verificación**:
  - Tras incidentes relevantes o cambios no documentados.
- **Revisar drift**:
  - Cuando se acumulan diferencias significativas entre inventario y estado observado.

### 12.2. Restricciones de IA y automatización

Restricciones obligatorias:

- La IA o automatización **sólo recomienda**; **no ejecuta cambios**.
- Ninguna recomendación puede:
  - Ejecutar CLI directamente en OLT.
  - Modificar inventario o Desired State.
  - Confirmar importaciones o planes de provisión.
- Toda acción sugerida debe materializarse, si se aprueba, mediante flujos existentes:
  - Preview → aprobación humana → `ProvisioningPlan` → ejecución controlada → snapshot → validación.


---

## 13. Fuentes de datos

La capa de Observabilidad y Conocimiento Operativo puede alimentarse de múltiples fuentes **read-only** y eventos internos.

Fuentes posibles (conceptuales):

- **Telnet/SSH CLI**:
  - Comandos de monitoreo (`show ...`) ejecutados en modo `read_only` y auditados.
- **SNMP**:
  - Lectura de contadores y métricas estándar (tráfico, errores, temperatura, estado de interfaz).
- **Zabbix u otros sistemas de monitoreo**:
  - Alarmas, triggers e históricos.
- **Tareas Celery**:
  - Jobs periódicos que recolectan métricas y estados desde la OLT o sistemas intermedios.
- **ConfigSnapshot**:
  - Snapshots históricos de running/startup-config y comandos adicionales.
- **Eventos internos**:
  - Resultados de importaciones, drift detection, ejecución de planes de provisión.
- **Provisioning results**:
  - Estado y resultado de `ProvisioningPlan` ejecutados (éxito, error, rollback).
- **Notas manuales**:
  - Observaciones de técnicos, registros de campo, tickets de incidentes.

> Las fuentes de datos se consideran **insumos de observabilidad** y conocimiento; ninguna de ellas, por sí sola, autoriza cambios automáticos en inventario o configuración.


---

## 14. Fichas operativas

Se recomienda estructurar fichas operativas que consoliden la información clave por tipo de entidad.

### 14.1. Ficha OLT

Secciones recomendadas:

- **Identidad**:
  - Código OLT, nombre, entorno (lab/producción), vendor, modelo.
- **Estado actual**:
  - Online/offline, estado de salud, alertas activas.
- **Uptime y reinicios**:
  - Uptime actual, historial de reinicios, causas probables.
- **PON ports**:
  - Número de PON activos, estado agregado, ocupación, incidencias recientes.
- **Uplinks**:
  - Estado por uplink, utilización, errores, flaps.
- **Tráfico**:
  - Gráficos de tráfico por uplink y PON.
- **Alarmas**:
  - Listado de alarmas activas y recientes.
- **Snapshots**:
  - Últimos snapshots relevantes (referencias, no contenido completo).
- **Drift**:
  - Resumen de diferencias relevantes entre Desired State y Observed State.
- **Historial**:
  - Eventos críticos, cambios importantes, incidentes mayores.
- **Recomendaciones**:
  - Sugerencias generadas por la capa de Knowledge/IA (sin acciones directas).

### 14.2. Ficha ONU

Secciones recomendadas:

- **Identidad**:
  - Interface, serial, cliente asociado (cuando exista), OLT, PON, NAP, zona.
- **Inventario**:
  - Datos de inventario aprobados (Desired State): VLAN, perfil, zona/NAP/NapPort, modo ONU deseado.
- **Configuración deseada**:
  - Resumen del Desired State para la ONU.
- **Configuración observada**:
  - Estado operativo actual y modo observado (comportamiento ONU, VLAN efectiva, perfil efectivo).
- **Estado actual**:
  - Online/offline, uptime, últimas caídas/reconexiones.
- **Potencia actual**:
  - RX/TX actuales.
- **Histórico óptico**:
  - Gráficos o tablas de potencia a lo largo del tiempo.
- **Eventos**:
  - Cambios de estado, flaps, intervenciones.
- **Alarmas**:
  - LOS, dying gasp y otras alarmas relevantes.
- **Drift**:
  - Diferencias entre Desired y Observed State (configuración, VLAN, perfil, territorio).
- **Recomendaciones**:
  - Sugerencias asociadas a esta ONU (revisar conector, revisar NAP, ajustar configuración, etc.).

### 14.3. Ficha NAP/Zona

Secciones recomendadas:

- **Inventario**:
  - Identidad territorial (Zone, NAP/ODN/ODB) según EFO Modelo Territorial FTTH.
- **ONUs asociadas**:
  - Conteo total y distribución por estado.
- **Salud agregada**:
  - Health Score de la zona/NAP.
  - Porcentaje de ONUs con buena potencia vs degradadas.
- **Eventos**:
  - Incidentes recientes, cortes, mantenimientos.
- **Incidencias**:
  - Lista de incidencias abiertas/cerradas asociadas.
- **Tendencias**:
  - Degradación óptica promedio, frecuencia de caídas.
- **Capacidad**:
  - Ocupación vs capacidad (puertos, ONUs, reservas).
- **Recomendaciones**:
  - Acciones sugeridas (saneamiento de planta externa, ampliación de capacidad, cambios de diseño territorial).


---

## 15. Invariantes

Las siguientes reglas son **obligatorias** para la capa de Observabilidad y Conocimiento Operativo.

1. **Observabilidad no modifica inventario.**  
   - Los datos de observabilidad (métricas, estados, históricos, Health Scores) nunca crean, actualizan ni eliminan registros de inventario (Desired State, catálogos técnicos o territoriales).

2. **Métricas operativas no cambian Desired State.**  
   - El Desired State se modifica sólo mediante flujos explícitos (import confirmada, saneamiento, provisión), nunca como reacción directa a métricas.

3. **Alertas no ejecutan provisioning.**  
   - Una alerta puede sugerir acciones, pero no dispara planes de provisión automáticamente.

4. **IA no ejecuta cambios.**  
   - La IA/automatización sólo propone; cualquier ejecución requiere aprobación humana y flujos ya existentes.

5. **Todo cambio requiere flujo aprobado.**  
   - Cambios en OLT o inventario deben materializarse vía `ProvisioningPlan` u otros flujos documentados, con preview, aprobación y auditoría.

6. **Históricos no se sobrescriben.**  
   - Los históricos se gestionan de forma append-only o versionada; se pueden aplicar políticas de retención, pero no se reescriben valores históricos.

7. **Eventos deben ser trazables.**  
   - Cada alerta/evento relevante debe tener origen, instante, entidad afectada y, cuando aplique, referencia a snapshot o evidencia.

8. **Drift requiere snapshot o evidencia.**  
   - Cualquier registro de drift debe estar respaldado por un snapshot o lectura de monitoreo verificable.

9. **Health Score debe ser explicable.**  
   - Debe ser posible desglosar un Health Score en factores y pesos; se prohíben indicadores opacos sin justificación.

10. **Datos operativos no cambian catálogos.**  
    - Estados, métricas y alertas no alteran catálogos globales, técnicos, territoriales ni operativos canónicos; sólo añaden observaciones e históricos.


---

## 16. Roadmap

Se define el siguiente roadmap conceptual para la Fase **P7 – Observabilidad y Conocimiento Operativo**:

- **P7.1 Observabilidad OLT**  
  - Consolidar métricas de estado, uptime, reinicios, CPU/memoria/temperatura, alarmas y tráfico por uplink a nivel de OLT.

- **P7.2 Observabilidad PON**  
  - Exponer estado de puertos PON, ocupación, ONUs online/offline, errores, saturación y alertas de caída masiva.

- **P7.3 Observabilidad ONU**  
  - Completar fichas operativas de ONU con estado, potencia actual, históricos, eventos, alarmas y drift.

- **P7.4 Históricos ópticos**  
  - Diseñar y documentar el almacenamiento y explotación de `power history` a nivel de ONU/PON/NAP/Zona.

- **P7.5 Alertas**  
  - Definir y priorizar reglas de alertas mínimas (OLT, PON, ONU, NAP/Zona) y su integración con operaciones.

- **P7.6 Health Scores**  
  - Definir modelos explicables de Health Score para OLT, PON, uplink, ONU, NAP/ODN/ODB y zona.

- **P7.7 Knowledge Layer**  
  - Formalizar el modelo de conocimiento operativo (patrones de degradación, reincidencias por NAP/zona, PON próximas a saturación, etc.).

- **P7.8 Recomendaciones asistidas**  
  - Diseñar catálogos de recomendaciones y reglas de IA que traduzcan conocimiento en sugerencias operativas.

- **P7.9 Integración Zabbix/SNMP**  
  - Documentar la integración de fuentes externas de monitoreo (Zabbix, SNMP u otros) con la capa de Observabilidad.

- **P7.10 Dashboard operativo**  
  - Definir dashboards de operación diaria para NOC/operaciones, basados en métricas, alertas, Health Scores y conocimiento operativo, manteniendo siempre la separación entre Observed/Desired State y sin introducir acciones de apply.
