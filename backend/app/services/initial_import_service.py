from datetime import UTC, datetime
import json
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.drivers.errors import DriverCommandError
from app.drivers.zte.c300_v125p3_telnet.running_config_parser import ParsedOnu, parse_running_config
from app.drivers.zte.c300_v125p3_telnet.running_config_snapshot_validator import (
    snapshot_checksum,
    validate_parsed_interface_count,
    validate_running_config_snapshot,
)
from app.drivers.zte.c300_v125p3_telnet.zte_onu_management_mode_parser import SERVICE_MODE_DEFINITIONS
from app.models.entities import (
    ConfigSnapshot,
    DriverCommandLog,
    GponProfile,
    ImportJob,
    Nap,
    NapPort,
    Olt,
    OltCard,
    OltTechnicalSettings,
    OltUplink,
    Onu,
    OnuServiceModeTemplate,
    OnuType,
    UnauthorizedOnu,
    PonPort,
    ProfileCatalog,
    SpeedProfile,
    Vlan,
    Zone,
)
from app.services.event_service import EventService


class ImportCriticalError(ValueError):
    pass


class SnapshotValidationError(ValueError):
    pass


class InitialImportService:
    def __init__(self, db: Session):
        self.db = db
        self.events = EventService(db)

    IMPORT_SOURCE_BY_JOB_SOURCE = {
        "telnet": "telnet_running_config",
        "file": "file_upload",
        "text": "text_input",
    }

    def create_preview_from_text(self, olt_id: int, raw_config: str, source: str = "text") -> dict:
        olt = self._get_olt_or_error(olt_id)
        snapshot = ConfigSnapshot(
            olt_id=olt.id,
            raw_config=raw_config,
            source_command="show running-config",
            status="captured",
            checksum=snapshot_checksum(raw_config),
        )
        self.db.add(snapshot)
        self.db.commit()
        self.db.refresh(snapshot)
        return self._create_preview_from_snapshot(olt, snapshot, source, require_final_prompt=False)

    def _create_preview_from_snapshot(
        self,
        olt: Olt,
        snapshot: ConfigSnapshot,
        source: str,
        require_final_prompt: bool,
    ) -> dict:
        try:
            validation = validate_running_config_snapshot(snapshot.raw_config, require_final_prompt=require_final_prompt)
            if not validation.is_complete:
                raise SnapshotValidationError("; ".join(validation.errors))
            parsed = parse_running_config(snapshot.raw_config)
            count_errors = validate_parsed_interface_count(validation, len(parsed.onus))
            if count_errors:
                raise SnapshotValidationError("; ".join(count_errors))
            summary = self._preview_summary(parsed, olt.id)
            snapshot.status = "parsed"
            snapshot.warnings = json.dumps(
                {
                    "validation": validation.warnings,
                    "parser": parsed.warnings,
                    "legacy_incomplete": parsed.legacy_incomplete,
                },
                ensure_ascii=True,
            )
            snapshot.parser_result = json.dumps(
                {"summary": summary, "validation": validation.metrics()},
                ensure_ascii=True,
            )
            job = ImportJob(
                olt_id=olt.id,
                status="preview",
                source=source,
                raw_config_snapshot_id=snapshot.id,
                parsed_summary_json=json.dumps(summary, ensure_ascii=True),
            )
            self.db.add(job)
            self.db.flush()
            olt.initial_import_status = "preview_created"
            olt.last_import_job_id = job.id
            self.events.record("IMPORT_PREVIEW_CREATED", "olt", olt.id, f"Preview inicial creado para OLT {olt.olt_code} - {olt.name}")
            self.db.commit()
            self.db.refresh(job)
            return {"import_job_id": job.id, "snapshot_id": snapshot.id, **summary}
        except Exception as exc:
            snapshot.status = "failed"
            snapshot.warnings = json.dumps({"errors": [str(exc)]}, ensure_ascii=True)
            olt.initial_import_status = "failed"
            self.db.commit()
            raise

    def create_preview_from_telnet(self, olt_id: int) -> dict:
        olt = self._get_olt_or_error(olt_id)
        from app.services.olt_service import OltService

        olt_service = OltService(self.db)
        driver = olt_service.driver_for(olt)
        try:
            driver.connect(disable_paging=True)
            raw_config = driver.show_running_config()
            self._log_command(olt.id, "show running-config", True, raw_config)
        except DriverCommandError as exc:
            olt.initial_import_status = "failed"
            self._log_command(olt.id, exc.command, False, exc.output, exc.message)
            self.db.commit()
            raise
        finally:
            driver.disconnect()
        snapshot = ConfigSnapshot(
            olt_id=olt.id,
            raw_config=raw_config,
            source_command="show running-config",
            status="captured",
            checksum=snapshot_checksum(raw_config),
        )
        self.db.add(snapshot)
        self.db.commit()
        self.db.refresh(snapshot)
        return self._create_preview_from_snapshot(olt, snapshot, "telnet", require_final_prompt=True)

    def confirm_import(self, import_job_id: int) -> dict:
        job = self.db.get(ImportJob, import_job_id)
        if not job:
            raise ValueError("Import job not found")
        olt = self._get_olt_or_error(job.olt_id)
        return self._confirm_job(olt, job)

    def preview(self, olt: Olt) -> dict:
        return self.create_preview_from_telnet(olt.id)

    def confirm(self, olt: Olt, import_job_id: int) -> dict:
        job = self.db.get(ImportJob, import_job_id)
        if not job or job.olt_id != olt.id:
            raise ValueError("Import job not found for this OLT")
        return self._confirm_job(olt, job)

    def _confirm_job(self, olt: Olt, job: ImportJob) -> dict:
        if job.status == "confirmed":
            return {
                "import_job_id": job.id,
                "status": job.status,
                "vlans_upserted": 0,
                "gpon_profiles_upserted": 0,
                "onu_types_upserted": 0,
                "pon_ports_upserted": 0,
                "onus_upserted": 0,
                "zones_upserted": 0,
                "naps_upserted": 0,
                "warnings": json.loads(job.parsed_summary_json).get("warnings", []),
            }

        snapshot = self.db.get(ConfigSnapshot, job.raw_config_snapshot_id)
        if not snapshot:
            raise ValueError("Config snapshot not found")
        if snapshot.status != "parsed":
            raise SnapshotValidationError(f"Snapshot no confirmable en estado {snapshot.status}")
        if not snapshot.checksum or snapshot.checksum != snapshot_checksum(snapshot.raw_config):
            snapshot.status = "failed"
            job.status = "failed"
            olt.initial_import_status = "failed"
            self.db.commit()
            raise SnapshotValidationError("Checksum del snapshot no coincide")

        validation = validate_running_config_snapshot(snapshot.raw_config, require_final_prompt=job.source == "telnet")
        if not validation.is_complete:
            snapshot.status = "failed"
            job.status = "failed"
            olt.initial_import_status = "failed"
            self.db.commit()
            raise SnapshotValidationError("; ".join(validation.errors))
        parsed = parse_running_config(snapshot.raw_config)
        structural_errors = validate_parsed_interface_count(validation, len(parsed.onus))
        if parsed.critical_errors or structural_errors:
            errors = [*structural_errors, *parsed.critical_errors]
            snapshot.status = "failed"
            job.status = "failed"
            olt.initial_import_status = "failed"
            self.db.commit()
            raise ImportCriticalError("La importacion contiene errores criticos: " + "; ".join(errors))
        counters = {
            "vlans_upserted": 0,
            "gpon_profiles_upserted": 0,
            "onu_types_upserted": 0,
            "pon_ports_upserted": 0,
            "uplinks_upserted": 0,
            "onus_upserted": 0,
            "zones_upserted": 0,
            "naps_upserted": 0,
            "warnings": parsed.warnings,
        }

        for vlan in parsed.vlans:
            self._upsert_vlan(olt.id, vlan)
            counters["vlans_upserted"] += 1
        imported_profiles = []
        for profile in parsed.gpon_profiles:
            self._upsert_profile(olt.id, profile)
            imported_profiles.append(profile)
            counters["gpon_profiles_upserted"] += 1
        for profile_catalog in parsed.profile_catalogs:
            self._upsert_profile_catalog(olt, profile_catalog)
        self._sync_speed_profiles(olt.id, imported_profiles)
        for onu_type in parsed.onu_types:
            self._upsert_onu_type(olt, onu_type)
            counters["onu_types_upserted"] += 1
        for pon_port in parsed.pon_ports:
            self._upsert_pon_port(olt.id, pon_port)
            counters["pon_ports_upserted"] += 1
        parsed_pon_names = {port.interface_name for port in parsed.pon_ports}
        for interface_name in sorted(self._physical_pon_interfaces(olt.id) - parsed_pon_names):
            self._ensure_physical_pon_port(olt.id, interface_name)
            counters["pon_ports_upserted"] += 1
        for uplink in parsed.uplinks:
            self._upsert_uplink(olt.id, uplink)
            counters["uplinks_upserted"] += 1
        self._ensure_technical_settings(olt.id)
        management_modes = {item.onu_interface: item for item in parsed.onu_management_modes}
        self._sync_onu_service_modes(olt, parsed.onu_management_modes)
        for parsed_onu in parsed.onus:
            historical_mode = management_modes.get(parsed_onu.onu_interface)
            if not historical_mode or historical_mode.mode_code == "unknown":
                continue
            pending = self.db.scalar(
                select(UnauthorizedOnu).where(
                    UnauthorizedOnu.olt_id == olt.id,
                    UnauthorizedOnu.serial_number == parsed_onu.serial_number,
                )
            )
            if pending:
                pending.suggested_service_mode_code = historical_mode.mode_code
        for onu in parsed.onus:
            zone, zone_created = self._ensure_zone(olt, onu.parsed_zone_name)
            nap, nap_created = self._ensure_nap(olt, zone, onu.parsed_nap_name)
            counters["zones_upserted"] += 1 if zone_created else 0
            counters["naps_upserted"] += 1 if nap_created else 0
            persisted = self._upsert_onu(
                olt,
                job,
                onu,
                zone.id if zone else None,
                nap.id if nap else None,
                management_modes.get(onu.onu_interface).mode_code if management_modes.get(onu.onu_interface) else None,
            )
            if nap and persisted.nap_port:
                self._occupy_nap_port(nap, persisted)
            counters["onus_upserted"] += 1

        job.status = "confirmed"
        snapshot.status = "confirmed"
        job.confirmed_at = datetime.now(UTC)
        olt.initial_import_status = "confirmed"
        olt.last_import_job_id = job.id
        olt.last_import_confirmed_at = job.confirmed_at
        self.events.record("IMPORT_CONFIRMED", "olt", olt.id, f"Importacion inicial confirmada para OLT {olt.olt_code} - {olt.name}")
        self.db.commit()
        return {"import_job_id": job.id, "status": job.status, **counters}

    def _preview_summary(self, parsed, olt_id: int) -> dict:
        base = parsed.summary()
        return {
            "vlans": base["vlans"],
            "tcont_profiles": sum(1 for profile in parsed.gpon_profiles if profile.profile_type == "tcont"),
            "traffic_profiles": sum(1 for profile in parsed.gpon_profiles if profile.profile_type == "traffic"),
            "gpon_profiles": base["gpon_profiles"],
            "onu_types": base["onu_types"],
            "pon_ports": len({port.interface_name for port in parsed.pon_ports} | self._physical_pon_interfaces(olt_id)),
            "uplinks": base.get("uplinks", 0),
            "onus": base["onus"],
            "onu_management_modes": base.get("onu_management_modes", 0),
            "zones_detected": base["zones_detected"],
            "naps_detected": base["naps_detected"],
            "warnings": base["warnings"],
            "legacy_incomplete": base.get("legacy_incomplete", []),
            "critical_errors": base.get("critical_errors", []),
        }

    def _get_olt_or_error(self, olt_id: int) -> Olt:
        olt = self.db.get(Olt, olt_id)
        if not olt:
            raise ValueError("OLT not found")
        return olt

    def list_jobs(self, olt: Olt) -> list[dict]:
        jobs = self.db.scalars(select(ImportJob).where(ImportJob.olt_id == olt.id).order_by(ImportJob.created_at.desc())).all()
        return [self._job_to_dict(job) for job in jobs]

    def get_job(self, job_id: int) -> dict:
        job = self.db.get(ImportJob, job_id)
        if not job:
            raise ValueError("Import job not found")
        return self._job_to_dict(job)

    def _upsert_vlan(self, olt_id: int, parsed) -> Vlan:
        olt = self.db.get(Olt, olt_id)
        vlan = self.db.scalar(select(Vlan).where(Vlan.olt_id == olt_id, Vlan.vlan_id == parsed.vlan_id))
        if not vlan:
            vlan = Vlan(olt_id=olt_id, vlan_id=parsed.vlan_id)
            self.db.add(vlan)
        vlan.olt_code_snapshot = olt.olt_code if olt else vlan.olt_code_snapshot
        vlan.name = parsed.name
        vlan.description = parsed.description
        vlan.source = "imported"
        vlan.is_active = True
        return vlan

    def _upsert_profile(self, olt_id: int, parsed) -> GponProfile:
        profile = self.db.scalar(
            select(GponProfile).where(
                GponProfile.olt_id == olt_id,
                GponProfile.profile_type == parsed.profile_type,
                GponProfile.name == parsed.name,
            )
        )
        if not profile:
            profile = GponProfile(olt_id=olt_id, profile_type=parsed.profile_type, name=parsed.name)
            self.db.add(profile)
        profile.upstream_rate = parsed.upstream_rate
        profile.downstream_rate = parsed.downstream_rate
        return profile

    def _upsert_onu_type(self, olt: Olt, parsed) -> OnuType:
        onu_type = self.db.scalar(select(OnuType).where(OnuType.olt_id == olt.id, OnuType.name == parsed.name))
        if not onu_type:
            onu_type = OnuType(olt_id=olt.id, name=parsed.name)
            self.db.add(onu_type)
        elif onu_type.source != "imported" or not onu_type.is_active:
            return onu_type
        onu_type.olt_code_snapshot = olt.olt_code
        onu_type.vendor = olt.vendor
        onu_type.model = olt.model
        onu_type.firmware = olt.firmware
        onu_type.vendor_detected = parsed.vendor_detected
        onu_type.technology = parsed.technology.upper()
        onu_type.pon_type = parsed.pon_type.upper()
        onu_type.channel_gpon = parsed.channel_gpon
        onu_type.channel_xgpon = parsed.channel_xgpon
        onu_type.channel_xgspon = parsed.channel_xgspon
        onu_type.max_tcont = parsed.max_tcont
        onu_type.max_gemport = parsed.max_gemport
        onu_type.max_ports = parsed.max_ports
        onu_type.max_switch_perslot = parsed.max_switch_perslot
        onu_type.max_flow_perswitch = parsed.max_flow_perswitch
        onu_type.max_iphost = parsed.max_iphost
        onu_type.ethernet_ports = parsed.ethernet_ports
        onu_type.wifi_ports = parsed.wifi_ports
        onu_type.pots_ports = parsed.pots_ports
        onu_type.rf_ports = parsed.rf_ports
        onu_type.allow_custom_profiles = parsed.allow_custom_profiles
        onu_type.default_custom_profile_id = parsed.default_custom_profile_id
        onu_type.capability_mode = parsed.capability_mode
        onu_type.source = "imported"
        onu_type.is_active = True
        return onu_type

    def _upsert_profile_catalog(self, olt: Olt, parsed) -> ProfileCatalog:
        catalog = self.db.scalar(
            select(ProfileCatalog).where(
                ProfileCatalog.olt_id == olt.id,
                ProfileCatalog.profile_kind == parsed.profile_kind,
                ProfileCatalog.name == parsed.name,
            )
        )
        if not catalog:
            catalog = ProfileCatalog(olt_id=olt.id, profile_kind=parsed.profile_kind, name=parsed.name)
            self.db.add(catalog)
        elif catalog.source != "imported" or not catalog.is_active:
            return catalog
        catalog.olt_code_snapshot = olt.olt_code
        catalog.vendor = olt.vendor
        catalog.model = olt.model
        catalog.firmware = olt.firmware
        catalog.direction = parsed.direction
        catalog.service_type = parsed.service_type
        catalog.speed_kbps = parsed.speed_kbps
        catalog.is_default = parsed.is_default
        catalog.type_value = parsed.type_value
        catalog.fixed_kbps = parsed.fixed_kbps
        catalog.assured_kbps = parsed.assured_kbps
        catalog.maximum_kbps = parsed.maximum_kbps
        catalog.sir_kbps = parsed.sir_kbps
        catalog.pir_kbps = parsed.pir_kbps
        catalog.source = "imported"
        catalog.is_active = True
        return catalog

    def _upsert_pon_port(self, olt_id: int, parsed) -> PonPort:
        pon = self.db.scalar(select(PonPort).where(PonPort.olt_id == olt_id, PonPort.interface_name == parsed.interface_name))
        if not pon:
            pon = PonPort(olt_id=olt_id, slot=parsed.slot, port=parsed.port)
            self.db.add(pon)
        pon.rack = parsed.rack
        pon.shelf = parsed.shelf
        pon.slot = parsed.slot
        pon.port = parsed.port
        pon.interface_name = parsed.interface_name
        pon.pon_type = "GPON"
        return pon

    def _physical_pon_interfaces(self, olt_id: int) -> set[str]:
        interfaces: set[str] = set()
        cards = self.db.scalars(select(OltCard).where(OltCard.olt_id == olt_id)).all()
        for card in cards:
            card_type = (card.card_type or card.real_type or "").upper()
            if not card_type.startswith(("GTGH", "GTGO")):
                continue
            parts = [int(part) for part in card.slot_number.split("/") if part.isdigit()]
            rack = parts[0] if parts else 1
            slot = parts[-1] if parts else 0
            for port in range(1, (card.port_count or 0) + 1):
                interfaces.add(f"gpon-olt_{rack}/{slot}/{port}")
        return interfaces

    def _ensure_physical_pon_port(self, olt_id: int, interface_name: str) -> PonPort:
        existing = self.db.scalar(select(PonPort).where(PonPort.olt_id == olt_id, PonPort.interface_name == interface_name))
        if existing:
            return existing
        match = re.fullmatch(r"gpon-olt_(\d+)/(\d+)/(\d+)", interface_name)
        if not match:
            raise ValueError(f"Invalid physical PON interface {interface_name}")
        rack, slot, port = (int(value) for value in match.groups())
        pon = PonPort(
            olt_id=olt_id,
            rack=rack,
            shelf=0,
            slot=slot,
            port=port,
            interface_name=interface_name,
            pon_type="GPON",
            admin_status="unknown",
            oper_status="empty",
            online_count=0,
            offline_count=0,
            total_count=0,
            occupancy_percent=0,
            sync_source="Telnet Read-Only",
        )
        self.db.add(pon)
        return pon

    def _upsert_uplink(self, olt_id: int, parsed) -> OltUplink:
        uplink = self.db.scalar(select(OltUplink).where(OltUplink.olt_id == olt_id, OltUplink.interface_name == parsed.interface_name))
        if not uplink:
            uplink = OltUplink(olt_id=olt_id, interface_name=parsed.interface_name)
            self.db.add(uplink)
        uplink.description = parsed.description
        uplink.interface_type = parsed.interface_type
        uplink.admin_status = parsed.admin_status
        uplink.oper_status = parsed.oper_status
        uplink.negotiation = parsed.negotiation
        uplink.mtu = parsed.mtu
        uplink.mode = parsed.mode
        uplink.allowed_vlans = parsed.allowed_vlans
        uplink.pvid_untag = parsed.pvid_untag
        uplink.last_seen_at = datetime.now(UTC)
        return uplink

    def _ensure_technical_settings(self, olt_id: int) -> OltTechnicalSettings:
        settings = self.db.scalar(select(OltTechnicalSettings).where(OltTechnicalSettings.olt_id == olt_id))
        if not settings:
            settings = OltTechnicalSettings(olt_id=olt_id)
            self.db.add(settings)
        return settings

    def _ensure_zone(self, olt: Olt, name: str | None) -> tuple[Zone | None, bool]:
        if not name:
            return None, False
        zone = self.db.scalar(select(Zone).where(Zone.olt_id == olt.id, Zone.name == name))
        if zone:
            return zone, False
        zone = Zone(olt_id=olt.id, olt_code_snapshot=olt.olt_code, name=name, description="Detectada por importacion inicial OLT")
        zone.code = name
        zone.source = "imported"
        zone.is_active = True
        self.db.add(zone)
        self.db.flush()
        return zone, True

    def _ensure_nap(self, olt: Olt, zone: Zone | None, name: str | None) -> tuple[Nap | None, bool]:
        if not zone or not name:
            return None, False
        nap = self.db.scalar(select(Nap).where(Nap.olt_id == olt.id, Nap.zone_id == zone.id, Nap.name == name))
        if nap:
            self._ensure_nap_ports(olt, nap)
            return nap, False
        nap = Nap(olt_id=olt.id, olt_code_snapshot=olt.olt_code, zone_id=zone.id, name=name, code=name, capacity=16, description="Detectada por importacion inicial OLT", source="imported", is_active=True)
        self.db.add(nap)
        self.db.flush()
        self._ensure_nap_ports(olt, nap)
        return nap, True

    def _upsert_onu(
        self,
        olt: Olt,
        job: ImportJob,
        parsed: ParsedOnu,
        zone_id: int | None,
        nap_id: int | None,
        service_mode_code: str | None = None,
    ) -> Onu:
        olt_id = olt.id
        onu = self.db.scalar(select(Onu).where(Onu.olt_id == olt_id, Onu.serial_number == parsed.serial_number))
        pon = self.db.scalar(select(PonPort).where(PonPort.olt_id == olt_id, PonPort.interface_name == parsed.pon_interface_name))
        if not onu:
            onu = Onu(
                olt_id=olt_id,
                olt_code_snapshot=olt.olt_code,
                customer_name=parsed.customer_name or parsed.serial_number,
                serial_number=parsed.serial_number,
                onu_interface=parsed.onu_interface,
                onu_type=parsed.onu_type,
                vlan=parsed.vlan or 0,
                speed_profile=parsed.downstream_profile or parsed.upstream_profile or "imported",
                speed_profile_up=parsed.upstream_profile,
                speed_profile_down=parsed.downstream_profile,
                status="unknown",
                import_source=self.IMPORT_SOURCE_BY_JOB_SOURCE.get(job.source, "manual"),
            )
            self.db.add(onu)
            self.db.flush()
        onu.pon_port_id = pon.id if pon else onu.pon_port_id
        onu.olt_code_snapshot = olt.olt_code
        onu.zone_id = zone_id
        onu.nap_id = nap_id
        onu.customer_name = parsed.customer_name or onu.customer_name
        onu.onu_interface = parsed.onu_interface
        onu.onu_type = parsed.onu_type
        onu.vlan = parsed.vlan or onu.vlan
        onu.speed_profile = parsed.downstream_profile or parsed.upstream_profile or onu.speed_profile
        onu.speed_profile_up = parsed.upstream_profile
        onu.speed_profile_down = parsed.downstream_profile
        onu.nap_port = parsed.parsed_nap_port
        onu.imported_from_config = True
        onu.auth_date = parsed.auth_date
        onu.raw_description = parsed.raw_description
        onu.description_original = onu.description_original or parsed.raw_description
        onu.description_generated = onu.description_generated or parsed.raw_description
        onu.parsed_zone_name = parsed.parsed_zone_name
        onu.parsed_nap_name = parsed.parsed_nap_name
        onu.parsed_nap_port = parsed.parsed_nap_port
        onu.parsed_odn = parsed.parsed_odn
        onu.zone_name = parsed.parsed_zone_name
        onu.address_reference = parsed.address_reference
        onu.nap_name = parsed.parsed_nap_name
        onu.nap_port_label = str(parsed.parsed_nap_port) if parsed.parsed_nap_port is not None else None
        onu.odb_name = parsed.parsed_odn
        onu.external_id = parsed.external_id or parsed.serial_number
        onu.description_parse_status = parsed.description_parse_status
        onu.description_parse_warnings = json.dumps(parsed.description_parse_warnings, ensure_ascii=True)
        if parsed.description_parse_status in {"partial", "unknown"} and not onu.technician_notes:
            onu.technician_notes = parsed.raw_description
        onu.service_mode_code = service_mode_code if service_mode_code != "unknown" else onu.service_mode_code
        onu.source = "cli_import"
        onu.import_source = self.IMPORT_SOURCE_BY_JOB_SOURCE.get(job.source, "manual")
        return onu

    def _sync_onu_service_modes(self, olt: Olt, parsed_modes: list) -> None:
        known_modes = [mode for mode in parsed_modes if mode.mode_code in SERVICE_MODE_DEFINITIONS]
        counts: dict[str, int] = {}
        samples: dict[str, object] = {}
        for mode in known_modes:
            counts[mode.mode_code] = counts.get(mode.mode_code, 0) + 1
            samples.setdefault(mode.mode_code, mode)

        manual_default = self.db.scalar(
            select(OnuServiceModeTemplate).where(
                OnuServiceModeTemplate.olt_id == olt.id,
                OnuServiceModeTemplate.source == "manual",
                OnuServiceModeTemplate.default_for_provisioning.is_(True),
            )
        )
        default_code = max(counts, key=counts.get) if counts and not manual_default else None

        for mode_code, sample in samples.items():
            definition = SERVICE_MODE_DEFINITIONS[mode_code]
            item = self.db.scalar(
                select(OnuServiceModeTemplate).where(
                    OnuServiceModeTemplate.olt_id == olt.id,
                    OnuServiceModeTemplate.mode_code == mode_code,
                )
            )
            if item and item.source == "manual":
                continue
            if not item:
                item = OnuServiceModeTemplate(olt_id=olt.id, mode_code=mode_code, name=definition["name"], template_body=definition["template_body"])
                self.db.add(item)
            item.vendor = olt.vendor
            item.model = olt.model
            item.firmware = olt.firmware or "V1.2.5P3"
            item.name = definition["name"]
            item.description = f'{definition["description"]} Detectado en {counts[mode_code]} ONUs.'
            item.vlan_mode = sample.vlan_mode
            item.dhcp_source = sample.dhcp_source
            item.use_iphost = sample.has_iphost
            item.use_veip = sample.has_veip
            item.use_vlan_filter = sample.has_vlan_filter
            item.use_loop_detect = sample.loop_detect_enabled
            item.disable_wifi = sample.wifi_disabled
            item.default_for_provisioning = mode_code == default_code
            item.template_body = definition["template_body"]
            item.source = "imported"
            item.is_active = True

    def _sync_speed_profiles(self, olt_id: int, parsed_profiles: list | None = None) -> None:
        olt = self.db.get(Olt, olt_id)
        profiles = parsed_profiles if parsed_profiles is not None else list(self.db.scalars(select(GponProfile).where(GponProfile.olt_id == olt_id)))
        ups = [profile for profile in profiles if profile.profile_type == "tcont"]
        downs = [profile for profile in profiles if profile.profile_type == "traffic"]
        used_down_names: set[str] = set()
        for up in ups:
            base = self._profile_base(up.name)
            down = next((candidate for candidate in downs if self._profile_base(candidate.name) == base), None)
            if not down:
                down = next((candidate for candidate in downs if candidate.name not in used_down_names), None)
            if down:
                used_down_names.add(down.name)
                self._upsert_speed_profile(olt, olt_id, up, down, base)

    def _upsert_speed_profile(self, olt: Olt | None, olt_id: int, up: GponProfile, down: GponProfile, base: str) -> SpeedProfile:
        code = base.upper()
        speed = self.db.scalar(select(SpeedProfile).where(SpeedProfile.olt_id == olt_id, SpeedProfile.profile_code == code))
        if not speed:
            speed = SpeedProfile(olt_id=olt_id, profile_code=code)
            self.db.add(speed)
        speed.olt_code_snapshot = olt.olt_code if olt else speed.olt_code_snapshot
        speed.vendor = olt.vendor if olt else speed.vendor
        speed.model = olt.model if olt else speed.model
        speed.firmware = olt.firmware if olt else speed.firmware
        speed.name = base
        speed.upstream_profile_name = up.name
        speed.downstream_profile_name = down.name
        upload_catalog = self.db.scalar(
            select(ProfileCatalog).where(
                ProfileCatalog.olt_id == olt_id,
                ProfileCatalog.profile_kind == "tcont",
                ProfileCatalog.name == up.name,
                ProfileCatalog.is_active.is_(True),
            )
        )
        download_catalog = self.db.scalar(
            select(ProfileCatalog).where(
                ProfileCatalog.olt_id == olt_id,
                ProfileCatalog.profile_kind == "traffic",
                ProfileCatalog.name == down.name,
                ProfileCatalog.is_active.is_(True),
            )
        )
        speed.upload_profile_id = upload_catalog.id if upload_catalog else None
        speed.download_profile_id = download_catalog.id if download_catalog else None
        speed.upstream_kbps = up.upstream_rate
        speed.downstream_kbps = down.downstream_rate
        speed.technology = "GPON"
        speed.source = "imported"
        speed.is_active = True
        return speed

    @staticmethod
    def _profile_base(name: str) -> str:
        upper = name.upper()
        for suffix in ("-UP", "_UP", "-DOWN", "_DOWN"):
            if upper.endswith(suffix):
                return name[: -len(suffix)]
        return name

    def _ensure_nap_ports(self, olt: Olt, nap: Nap) -> None:
        existing = set(self.db.scalars(select(NapPort.port_number).where(NapPort.nap_id == nap.id)))
        pending = {
            item.port_number
            for item in self.db.new
            if isinstance(item, NapPort) and item.nap_id == nap.id and item.port_number is not None
        }
        existing.update(pending)
        created = False
        for port_number in range(1, (nap.capacity or 16) + 1):
            if port_number not in existing:
                self.db.add(NapPort(olt_id=olt.id, olt_code_snapshot=olt.olt_code, nap_id=nap.id, port_number=port_number, label=f"Puerto {port_number}", status="free"))
                created = True
        if created:
            self.db.flush()

    def _occupy_nap_port(self, nap: Nap, onu: Onu) -> None:
        olt = self.db.get(Olt, onu.olt_id)
        if not olt:
            return
        self._ensure_nap_ports(olt, nap)
        port = self.db.scalar(select(NapPort).where(NapPort.nap_id == nap.id, NapPort.port_number == onu.nap_port))
        if not port:
            port = next(
                (
                    item
                    for item in self.db.new
                    if isinstance(item, NapPort) and item.nap_id == nap.id and item.port_number == onu.nap_port
                ),
                None,
            )
        if not port:
            port = NapPort(olt_id=olt.id, olt_code_snapshot=olt.olt_code, nap_id=nap.id, port_number=onu.nap_port, label=f"Puerto {onu.nap_port}")
            self.db.add(port)
            self.db.flush()
        port.status = "occupied"
        port.onu_id = onu.id
        port.customer_name_snapshot = onu.customer_name

    def _job_to_dict(self, job: ImportJob) -> dict:
        return {
            "id": job.id,
            "olt_id": job.olt_id,
            "status": job.status,
            "source": job.source,
            "raw_config_snapshot_id": job.raw_config_snapshot_id,
            "parsed_summary": json.loads(job.parsed_summary_json),
            "created_at": job.created_at,
            "confirmed_at": job.confirmed_at,
        }

    def _log_command(self, olt_id: int, command: str, success: bool, output: str | None = None, error: str | None = None) -> None:
        self.db.add(
            DriverCommandLog(
                olt_id=olt_id,
                command=command,
                success=success,
                error_message=error,
                output_excerpt=(output or "")[:2000] if output else None,
            )
        )
