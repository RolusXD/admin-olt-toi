# Initial OLT Import

## Wizard

The `/olts` flow is:

1. Create OLT as `draft`.
2. Run read-only connection check.
3. Execute `show running-config` and create preview.
4. Confirm import.
5. Synchronize cards, physical PON status and uplinks with read-only commands.

The Telnet stream is never parsed directly. `show running-config` must reach a stable final prompt, then its complete raw output is persisted with SHA-256 checksum as a `captured` snapshot. Structural validation runs against that stored text before parsing.

An OLT becomes operational only when `initial_import_status=confirmed`.

## Statuses

- `draft`
- `connection_tested`
- `preview_created`
- `confirmed`
- `failed`
- `cancelled`

## Parser Contract

The preview separates:

- `critical_errors`: block confirmation.
- `warnings`: technical ambiguity requiring attention.
- `legacy_incomplete`: inherited missing metadata that does not block import.

Descriptions are preserved exactly in `description_original`. Partial or unknown descriptions are copied to editable `technician_notes`. Missing explicit zones are assigned to OLT-specific `SIN_ZONA`.

Snapshot validation compares authorized ONU interfaces with `interface gpon-onu_*` blocks, rejects duplicates, residual pagination, missing blocks, orphan blocks, parsed-count differences and Telnet captures without a stable final prompt. Confirmation recalculates checksum and parses the same stored snapshot.

## Upsert Keys

- ONU: `olt_id + serial_number`
- PON port: `olt_id + interface_name`
- VLAN: `olt_id + vlan_id`
- ONU type: `olt_id + name`
- Profile: OLT, kind/type and name
- Zone: `olt_id + name`
- NAP: `olt_id + zone_id + name`

Imports never delete manual records automatically.

## Physical PON Completion

Cards detected by the read-only test are persisted. GTGH/GTGHG cards imply 16 physical ports. Missing ports are created as empty even when absent from ONU state or running config output.
