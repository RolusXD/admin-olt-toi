# Auditoria tecnica ZTE C300 V1.2.5P3 - OLT-PCM-ZTE-01

Fecha: 2026-06-18
OLT: OLT-PCM-ZTE-01 / FTTH-PCM-ZTE1
Vendor/model/firmware: ZTE / C300 / V1.2.5P3
Import job: 5
Snapshot: 5

## Seguridad

- Se ejecuto `preview-from-telnet` usando `show running-config`.
- Se confirmo la importacion sobre base de datos local.
- No se ejecuto aprovisionamiento.
- No se ejecutaron comandos de configuracion, `configure terminal`, `write`, `reboot`, `reload`, `reset`, `delete` ni `erase`.

## Reimportacion

Preview real desde Telnet:

| Recurso | Cantidad |
|---|---:|
| VLANs | 215 |
| TCONT profiles | 13 |
| Traffic profiles | 13 |
| GPON profiles total | 26 |
| ONU types | 13 |
| PON ports | 15 |
| ONUs en running-config | 555 |

Confirmacion:

| Recurso | Upsert |
|---|---:|
| VLANs | 215 |
| GPON profiles | 26 |
| ONU types | 13 |
| PON ports | 15 |
| ONUs | 555 |
| Zonas nuevas | 0 |
| NAPs nuevas | 0 |

Comparativo antes/despues:

| Recurso | Antes | Despues |
|---|---:|---:|
| ONU types | 13 | 13 |
| Upload profiles | 13 | 13 |
| Download profiles | 13 | 13 |
| VLANs | 215 | 215 |
| Zonas | 3 | 3 |
| NAPs | 70 | 70 |
| PON ports | 15 | 15 |

## Auditoria ONU Types

| ONU type | Tech | TCONT | GEM | ETH | WiFi | POTS | RF | Source |
|---|---|---:|---:|---:|---:|---:|---:|---|
| BENET | GPON | 8 | 32 | 1 | 0 | 0 | 0 | imported |
| BTPON | GPON | 8 | 32 | 1 | 0 | 0 | 0 | imported |
| BkTellGC1 | GPON | 8 | 32 | 1 | 0 | 0 | 0 | imported |
| CDATA | GPON | 8 | 32 | 1 | 0 | 0 | 0 | imported |
| CDATAWIFI | GPON | 8 | 32 | 1 | 1 | 0 | 0 | imported |
| Huawei-HG8546M | GPON | 8 | 32 | 4 | 1 | 1 | 0 | imported |
| Prueba-vSol-no-usar | GPON | 8 | 32 | 2 | 1 | 0 | 0 | imported |
| TENDA | GPON | 8 | 32 | 2 | 1 | 0 | 0 | imported |
| ZTE-F600 | GPON | 8 | 32 | 3 | 0 | 0 | 0 | imported |
| ZTE-F601V6.0 | GPON | - | 32 | 1 | 0 | 0 | 0 | imported |
| ZTE-F660 | GPON | 8 | 32 | 4 | 4 | 2 | 0 | imported |
| ZTE-F660V5.2 | GPON | 8 | 32 | 4 | 4 | 2 | 0 | imported |
| azul | GPON | 8 | 32 | 1 | 1 | 0 | 1 | imported |

Hallazgos ONU type:

- Tipos incompletos: `ZTE-F601V6.0` no trae `max_tcont`.
- Tipos sin interfaces: ninguno.
- Duplicados: ninguno.
- Sin tecnologia: ninguno.

## Auditoria ProfileCatalog

Upload / TCONT:

| Perfil | fixed_kbps | assured_kbps | maximum_kbps |
|---|---:|---:|---:|
| FTTHTOIH1 | - | - | 1024000 |
| SMARTOLT-100M-UP | 64 | 64 | 104960 |
| SMARTOLT-10M-UP | 64 | 64 | 10496 |
| SMARTOLT-1G-UP | 64 | 64 | 1048064 |
| SMARTOLT-200M-UP | 64 | 64 | 209664 |
| SMARTOLT-20M-UP | 64 | 64 | 20992 |
| SMARTOLT-300M-UP | 64 | 64 | 314624 |
| SMARTOLT-400M-UP | 64 | 64 | 419328 |
| SMARTOLT-500M-UP | 64 | 64 | 524032 |
| SMARTOLT-50M-UP | 64 | 64 | 52480 |
| SMARTOLT-IPTV-10M-UP | 512 | 1024 | 11264 |
| SMARTOLT-TOI_70M-UP | 64 | 64 | 20224 |
| SMARTOLT-VOIPMNG-10M | 512 | 1024 | 11264 |

Download / Traffic:

| Perfil | sir_kbps | pir_kbps |
|---|---:|---:|
| SMARTOLT-100M-DOWN | 104960 | 104960 |
| SMARTOLT-1G-DOWN | 1048064 | 1048064 |
| SMARTOLT-200M-DOWN | 209664 | 209664 |
| SMARTOLT-20M-DOWN | 20992 | 20992 |
| SMARTOLT-250MB-DOWN | 259840 | 259840 |
| SMARTOLT-30M-DOWN | 31488 | 31488 |
| SMARTOLT-400M-DOWN | 419328 | 419328 |
| SMARTOLT-500M-DOWN | 524032 | 524032 |
| SMARTOLT-50M-DOWN | 52480 | 52480 |
| SMARTOLT-60M-DOWN | 62976 | 62976 |
| SMARTOLT-IPTV-50M-DOWN | 56320 | 56320 |
| SMARTOLT-TOI_70M-DOWN | 73472 | 73472 |
| SMARTOLT-VOIPMNG-10M | 10480 | 11264 |

Hallazgos ProfileCatalog:

- Perfiles vacios: ninguno.
- Perfiles duplicados: ninguno.
- Perfiles sin velocidad: ninguno.

## Validacion aprovisionamiento GPON00CBAC10

Plan revalidado: 4
Estado: validated

| Campo | Valor |
|---|---|
| ONU type seleccionado | Prueba-vSol-no-usar |
| Upload profile | SMARTOLT-1G-UP |
| Download profile | SMARTOLT-1G-DOWN |
| VLAN | 200 |
| NAP ID | 14 |
| Puerto NAP | 2 |
| ONU ID seleccionado | 1 |
| ONU ID sugerido | 1 |
| ONU IDs ocupados en PON | 2-18 |
| ONU registrada en esta OLT | No |

Warnings:

- La ONU GPON00CBAC10 existe en laboratorio (`OLT-LAB-ZTE-01`).

Errors:

- Ninguno despues de mapear el alias operativo `VSOL` al tipo real ZTE `Prueba-vSol-no-usar`.

Conclusion actualizada:

- Tecnologicamente el puerto GPON permite sugerir ONU ID 1.
- VLAN 200 existe.
- Perfiles UP/DOWN existen y estan completos.
- El CLI preview usa el nombre real de la OLT: `onu 1 type Prueba-vSol-no-usar sn GPON00CBAC10`.
- El plan queda validado para una futura ejecucion controlada, manteniendo pendiente solo la advertencia de existencia historica en laboratorio.

## Secciones no interpretadas aun

Total estimado de lineas no aprovechadas por el parser actual: 8071.

| Modulo probable | Lineas | Ejemplo |
|---|---:|---|
| flow | 1079 | `flow mode 1 tag-filter vid-filter untag-filter discard` |
| security-mng | 1052 | `security-mng 998 state enable mode permit ingress-type lan protocol web https` |
| dhcp-ip | 861 | `dhcp-ip ethuni eth_0/1 from-internet` |
| switchport-bind | 780 | `switchport-bind switch_0/1 veip 1` |
| switchport | 542 | `switchport mode hybrid vport 1` |
| pon-onu-mng | 529 | `pon-onu-mng gpon-onu_1/2/3:1` |
| sn-bind | 527 | `sn-bind enable sn` |
| tr069 | 513 | `069` |
| vlan under ONU management | 315 | `vlan port eth_0/1 mode tag vlan 200` |
| vlan-filter-mode | 240 | `vlan-filter-mode iphost 1 tag-filter vid-filter untag-filter discard` |
| vlan-filter | 238 | `vlan-filter iphost 1 priority 0 vid 200` |
| loop-detect | 183 | `loop-detect ethuni eth_0/1 enable` |
| system-monitor | 34 | `system-monitor watchdog rackno 1 shelfno 1 slotno 0 disable` |
| interface non-GPON | 30 | `interface mng1` |
| wifi | 24 | `wifi disable` |
| snmp | 16 | `snmp-server location Toi Internet - Bolivia` |
| aaa/access | 10 | `username smartoltustoi password 0 ... privilege 15` |

Nota: varias lineas no interpretadas pertenecen a `pon-onu-mng`, servicios por ONU, TR-069, filtros VLAN, seguridad ONU y bindings. Son candidatas claras para la siguiente iteracion del parser antes de ejecucion real.

## Resumen final JSON

```json
{
  "onu_types_imported": 13,
  "upload_profiles_imported": 13,
  "download_profiles_imported": 13,
  "vlans_imported": 215,
  "zones_imported": 3,
  "naps_imported": 70,
  "validation_result": "valid"
}
```
