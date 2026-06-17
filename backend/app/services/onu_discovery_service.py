from datetime import UTC, datetime
from time import perf_counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.drivers.errors import DriverCommandError
from app.drivers.zte.c300_v125p3_telnet.zte_c300_uncfg_parser import ParsedUnauthorizedOnu, parse_show_gpon_onu_uncfg
from app.models.entities import DriverCommandLog, EventLog, Olt, UnauthorizedOnu, UnauthorizedOnuEvent
from app.services.olt_service import OltService


DISCOVERY_COMMAND = "show gpon onu uncfg"
DISCOVERY_STATUSES = {"pending", "ignored", "ready_for_provisioning", "provisioned"}


class OnuDiscoveryService:
    def __init__(self, db: Session):
        self.db = db
        self.olt_service = OltService(db)

    def discover(self, olt: Olt) -> dict:
        driver = self.olt_service.driver_for(olt)
        started = perf_counter()
        raw_output = ""
        try:
            driver.connect(disable_paging=False)
            try:
                raw_output = driver.show_uncfg_raw()
                duration_ms = int((perf_counter() - started) * 1000)
                self._log_command(olt.id, True, raw_output, duration_ms=duration_ms)
            except DriverCommandError as exc:
                duration_ms = int((perf_counter() - started) * 1000)
                self._log_command(olt.id, False, exc.output, error=exc.message, duration_ms=duration_ms)
                self.db.commit()
                raise
        finally:
            driver.disconnect()

        parsed = parse_show_gpon_onu_uncfg(raw_output)
        summary = {"detected": len(parsed), "new": 0, "existing": 0, "ignored": 0, "duration_ms": int((perf_counter() - started) * 1000)}
        for item in parsed:
            onu, created = self._upsert_detected(olt, item, raw_output)
            if created:
                summary["new"] += 1
                self._record_event(onu, "detected", f"ONU no autorizada {onu.serial_number} detectada")
            else:
                summary["existing"] += 1
                if onu.status == "ignored":
                    summary["ignored"] += 1
            if onu.times_detected > 3 and onu.status != "provisioned":
                self._record_recurrent_alert(onu)

        self.db.commit()
        return summary

    def list(
        self,
        olt_id: int | None = None,
        olt_code: str | None = None,
        status: str | None = None,
        serial_number: str | None = None,
        pon_port_interface: str | None = None,
        detected_type: str | None = None,
        detected_vendor: str | None = None,
        environment: str | None = None,
    ) -> list[UnauthorizedOnu]:
        statement = select(UnauthorizedOnu)
        if olt_code:
            statement = statement.join(Olt, UnauthorizedOnu.olt_id == Olt.id).where(Olt.olt_code == olt_code.strip().upper())
        if environment and environment != "all":
            if not olt_code:
                statement = statement.join(Olt, UnauthorizedOnu.olt_id == Olt.id)
            statement = statement.where(Olt.environment == environment.strip().lower())
        if olt_id is not None:
            statement = statement.where(UnauthorizedOnu.olt_id == olt_id)
        if status:
            statement = statement.where(UnauthorizedOnu.status == status)
        if serial_number:
            statement = statement.where(UnauthorizedOnu.serial_number.ilike(f"%{serial_number}%"))
        if pon_port_interface:
            statement = statement.where(UnauthorizedOnu.pon_port_interface.ilike(f"%{pon_port_interface}%"))
        if detected_type:
            statement = statement.where(UnauthorizedOnu.detected_type.ilike(f"%{detected_type}%"))
        if detected_vendor:
            statement = statement.where(UnauthorizedOnu.detected_vendor.ilike(f"%{detected_vendor}%"))
        return list(self.db.scalars(statement.order_by(UnauthorizedOnu.last_seen_at.desc(), UnauthorizedOnu.id.desc())).all())

    def get(self, unauthorized_onu_id: int) -> UnauthorizedOnu | None:
        return self.db.get(UnauthorizedOnu, unauthorized_onu_id)

    def set_status(self, unauthorized_onu: UnauthorizedOnu, status: str) -> UnauthorizedOnu:
        if status not in DISCOVERY_STATUSES:
            raise ValueError("Invalid unauthorized ONU status")
        old_status = unauthorized_onu.status
        unauthorized_onu.status = status
        event_type = {
            "ignored": "ignored",
            "pending": "restored",
            "ready_for_provisioning": "ready_for_provisioning",
            "provisioned": "provisioned",
        }[status]
        if old_status != status:
            self._record_event(unauthorized_onu, event_type, f"ONU {unauthorized_onu.serial_number} cambio a {status}")
        self.db.commit()
        self.db.refresh(unauthorized_onu)
        return unauthorized_onu

    def _upsert_detected(self, olt: Olt, item: ParsedUnauthorizedOnu, raw_output: str) -> tuple[UnauthorizedOnu, bool]:
        now = datetime.now(UTC)
        onu = self.db.scalar(
            select(UnauthorizedOnu).where(UnauthorizedOnu.olt_id == olt.id, UnauthorizedOnu.serial_number == item.serial_number)
        )
        created = onu is None
        if onu is None:
            onu = UnauthorizedOnu(
                olt_id=olt.id,
                olt_code_snapshot=olt.olt_code,
                serial_number=item.serial_number,
                status="pending",
                first_seen_at=now,
                times_detected=0,
            )
            self.db.add(onu)
            self.db.flush()
        onu.olt_code_snapshot = olt.olt_code
        onu.pon_type = item.pon_type
        onu.slot = item.slot
        onu.port = item.port
        onu.pon_port_interface = item.pon_port_interface
        onu.detected_type = item.detected_type
        onu.detected_vendor = item.detected_vendor
        onu.raw_output = raw_output
        onu.last_seen_at = now
        onu.times_detected = (onu.times_detected or 0) + 1
        return onu, created

    def _record_event(self, onu: UnauthorizedOnu, event_type: str, description: str) -> None:
        self.db.add(UnauthorizedOnuEvent(unauthorized_onu_id=onu.id, event_type=event_type, description=description))

    def _record_recurrent_alert(self, onu: UnauthorizedOnu) -> None:
        exists = self.db.scalar(
            select(EventLog.id)
            .where(
                EventLog.event_type == "UNAUTHORIZED_ONU_RECURRENT",
                EventLog.entity_type == "unauthorized_onu",
                EventLog.entity_id == onu.id,
            )
            .limit(1)
        )
        if not exists:
            self.db.add(
                EventLog(
                    event_type="UNAUTHORIZED_ONU_RECURRENT",
                    entity_type="unauthorized_onu",
                    entity_id=onu.id,
                    description=f"ONU pendiente recurrente {onu.serial_number} detectada {onu.times_detected} veces",
                )
            )

    def _log_command(self, olt_id: int, success: bool, output: str | None, error: str | None = None, duration_ms: int | None = None) -> None:
        self.db.add(
            DriverCommandLog(
                olt_id=olt_id,
                command=DISCOVERY_COMMAND,
                success=success,
                read_only=True,
                duration_ms=duration_ms,
                error_message=error,
                output_excerpt=(output or "")[:2000] if output else None,
            )
        )
