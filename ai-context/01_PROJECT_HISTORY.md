# Project History

## Foundation

The project started as a modular FastAPI and Next.js manager for ZTE C300 equipment. Drivers, parsers, services and API routes were deliberately separated.

## Read-Only Validation

Production connectivity was validated with:

- `show version-running`
- `show card`
- `show gpon onu state`
- `show gpon onu uncfg`
- ONU RX/TX power commands
- `show interface`

CLI pagination and ZTE prompt variants, including `gpon-onu-mng`, were handled in the Telnet driver.

## Import and Multi-OLT

Initial import evolved into a two-step snapshot, preview and confirm workflow. Inventory upserts are scoped by OLT. Migrations `0031` and `0032` added OLT ownership for zones/NAP inventory and formalized incomplete OLT lifecycle states.

The fixture `tests/fixtures/zte_c300_running_config.txt` is the canonical local ZTE configuration sample. Current expected parsing results include 557 ONUs, 16 physical PON ports and three zones: `Lagunas`, `Zone_1` and `SIN_ZONA`.

## Monitoring and Discovery

ONU state and power synchronization, execution metrics, alerts and unauthorized ONU discovery were added. Every monitoring command is logged with `read_only=true`.

## Provisioning

Provisioning was introduced progressively: dry run, catalog validation, technical preflight and controlled execution. Plan 19 provisioned `GPON00CBAC10`; its management block was resumed separately after adding support for the ZTE management prompt. The plan is now `executed` and cannot be rerun.

