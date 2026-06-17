from dataclasses import asdict
from datetime import UTC, datetime
import json
from time import perf_counter

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.drivers.errors import DriverCommandError
from app.drivers.transports import TelnetlibTransport
from app.models.entities import DriverCommandLog, MonitoringExecution, Olt, Onu, OnuEventHistory, OnuPowerHistory
from app.services.event_service import EventService
from app.services.olt_service import OltService

CLI_EVENT_CAUSES = {"LOS", "DyingGasp", "Offline", "Working"}


class OltCliService:
    def __init__(self, db: Session):
        self.db = db
        self.olt_service = OltService(db)
        self.events = EventService(db)

    def _log_command(
        self,
        olt_id: int,
        command: str,
        success: bool,
        output: str | None = None,
        error: str | None = None,
        duration_ms: int | None = None,
        read_only: bool = True,
    ) -> None:
        self.db.add(
            DriverCommandLog(
                olt_id=olt_id,
                command=command,
                success=success,
                read_only=read_only,
                duration_ms=duration_ms,
                error_message=error,
                output_excerpt=(output or "")[:2000] if output else None,
            )
        )

    def _call_read_only(self, olt_id: int, command: str, func):
        started = perf_counter()
        try:
            result = func()
            self._log_command(
                olt_id,
                command,
                True,
                str(result),
                duration_ms=int((perf_counter() - started) * 1000),
                read_only=True,
            )
            return result
        except DriverCommandError as exc:
            self._log_command(
                olt_id,
                exc.command or command,
                False,
                exc.output,
                exc.message,
                duration_ms=int((perf_counter() - started) * 1000),
                read_only=True,
            )
            raise

    def _record_monitoring_execution(
        self,
        olt_id: int,
        task_type: str,
        started_at: datetime,
        finished_at: datetime,
        processed_count: int,
        success_count: int,
        error_count: int,
        details: dict,
    ) -> None:
        self.db.add(
            MonitoringExecution(
                olt_id=olt_id,
                task_type=task_type,
                started_at=started_at,
                finished_at=finished_at,
                duration_ms=int((finished_at - started_at).total_seconds() * 1000),
                processed_count=processed_count,
                success_count=success_count,
                error_count=error_count,
                details_json=json.dumps(details, ensure_ascii=False),
            )
        )

    def telnet_test(self, olt: Olt) -> dict:
        driver = self.olt_service.driver_for(olt)
        try:
            driver.connect(disable_paging=False)
            version_raw = self._call_read_only(olt.id, "show version-running", driver.show_version_running)
            cards = self._call_read_only(olt.id, "show card", driver.show_card)
            olt.status = "online"
            self.db.commit()
            return {
                "healthy": True,
                "prompt_modes": ["normal", "config"],
                "version_raw": version_raw,
                "cards": [asdict(card) for card in cards],
            }
        except DriverCommandError:
            self.db.commit()
            raise
        finally:
            driver.disconnect()

    def telnet_debug(self, olt: Olt, capture_seconds: int = 15, transport=None) -> dict:
        started = perf_counter()
        raw_banner = ""
        bytes_received = 0
        timeout = False
        success = False
        transport = transport or TelnetlibTransport(olt.ip_address, olt.telnet_port, capture_seconds)
        try:
            transport.connect()
            raw_banner, bytes_received = transport.capture_initial_banner(capture_seconds)
            success = True
        except TimeoutError as exc:
            timeout = True
            self._log_command(
                olt.id,
                "TELNET_DEBUG",
                False,
                raw_banner,
                error=str(exc),
                duration_ms=int((perf_counter() - started) * 1000),
                read_only=True,
            )
            self.db.commit()
            raise
        except Exception as exc:
            self._log_command(
                olt.id,
                "TELNET_DEBUG",
                False,
                raw_banner,
                error=str(exc),
                duration_ms=int((perf_counter() - started) * 1000),
                read_only=True,
            )
            self.db.commit()
            raise
        finally:
            try:
                transport.close()
            finally:
                if success:
                    self._log_command(
                        olt.id,
                        "TELNET_DEBUG",
                        True,
                        raw_banner,
                        duration_ms=int((perf_counter() - started) * 1000),
                        read_only=True,
                    )
                    self.db.commit()
        return {
            "raw_banner": raw_banner,
            "bytes_received": bytes_received,
            "timeout": timeout,
        }

    def sync_onus(self, olt: Olt) -> dict:
        driver = self.olt_service.driver_for(olt)
        started_at = datetime.now(UTC)
        started = perf_counter()
        summary = {
            "olt_id": olt.id,
            "cli_onus": 0,
            "matched_onus": 0,
            "updated_status": 0,
            "power_samples": 0,
            "events": 0,
            "unauthorized": 0,
            "total_processed": 0,
            "working": 0,
            "offline": 0,
            "los": 0,
            "dying_gasp": 0,
            "duration_ms": 0,
        }
        try:
            driver.connect(disable_paging=False)
            states = self._call_read_only(olt.id, "show gpon onu state", driver.show_onu_state)
            summary["cli_onus"] = len(states)
            counts = self._state_counts(states)
            summary["total_processed"] = counts["total"]
            summary["working"] = counts["working"]
            summary["offline"] = counts["offline"]
            summary["los"] = counts["los"]
            summary["dying_gasp"] = counts["dying_gasp"]

            for state in states:
                onu = self.db.scalar(
                    select(Onu).where(
                        Onu.olt_id == olt.id,
                        or_(Onu.onu_interface == state.interface, Onu.serial_number == state.serial_number),
                    )
                )
                if not onu:
                    continue
                summary["matched_onus"] += 1
                old_status = onu.status
                old_cause = onu.last_down_cause
                onu.status = state.status
                onu.last_down_cause = self._normalize_down_cause(state.last_down_cause)
                onu.last_monitored_at = datetime.now(UTC)
                if old_status != onu.status:
                    summary["updated_status"] += 1

                event_type = self._event_for_state(onu.status, onu.last_down_cause)
                if event_type in CLI_EVENT_CAUSES:
                    state_changed = old_status != onu.status or old_cause != onu.last_down_cause
                    if state_changed:
                        self._record_onu_event(olt.id, onu, event_type)
                        summary["events"] += 1

            summary["duration_ms"] = int((perf_counter() - started) * 1000)
            finished_at = datetime.now(UTC)
            self._record_monitoring_execution(
                olt.id,
                "sync_onus",
                started_at,
                finished_at,
                summary["total_processed"],
                summary["total_processed"],
                0,
                summary,
            )
            self.db.commit()
            return summary
        except Exception as exc:
            summary["duration_ms"] = int((perf_counter() - started) * 1000)
            finished_at = datetime.now(UTC)
            self._record_monitoring_execution(
                olt.id,
                "sync_onus",
                started_at,
                finished_at,
                summary["total_processed"],
                summary["total_processed"],
                1,
                {**summary, "error": str(exc)},
            )
            self.db.commit()
            raise
        finally:
            driver.disconnect()

    def sync_power(self, olt: Olt, limit: int | None = None, only_onu_interfaces: list[str] | None = None) -> dict:
        driver = self.olt_service.driver_for(olt)
        started_at = datetime.now(UTC)
        started = perf_counter()
        statement = select(Onu).where(
            Onu.olt_id == olt.id,
            Onu.status.in_(["online", "working"]),
        )
        if only_onu_interfaces:
            statement = statement.where(Onu.onu_interface.in_(only_onu_interfaces))
        statement = statement.order_by(Onu.onu_interface)
        if limit is not None:
            statement = statement.limit(limit)
        working_onus = list(self.db.scalars(statement))
        has_imported_onus = self.db.scalar(select(Onu.id).where(Onu.olt_id == olt.id).limit(1))
        if not has_imported_onus:
            raise ValueError("No hay ONUs importadas para esta OLT. Realice importación inicial o seleccione la OLT correcta.")
        summary = {
            "olt_id": olt.id,
            "working_onus": len(working_onus),
            "power_samples": 0,
            "rx_warning": 0,
            "rx_critical": 0,
            "commands": 0,
            "processed": len(working_onus),
            "success": 0,
            "failed": 0,
            "duration_ms": 0,
            "errors": [],
            "onu_results": [],
        }
        try:
            driver.connect(disable_paging=False)
            for onu in working_onus:
                onu_started = perf_counter()
                rx_command = f"show pon power onu-rx {onu.onu_interface}"
                tx_command = f"show pon power onu-tx {onu.onu_interface}"
                try:
                    rx = self._call_read_only(olt.id, rx_command, lambda interface=onu.onu_interface: driver.show_onu_rx_power(interface))
                    summary["commands"] += 1
                    tx = self._call_read_only(olt.id, tx_command, lambda interface=onu.onu_interface: driver.show_onu_tx_power(interface))
                    summary["commands"] += 1
                    if not rx or not tx:
                        raise ValueError("No se pudo parsear RX/TX")
                except Exception as exc:
                    summary["failed"] += 1
                    error = {
                        "onu_id": onu.id,
                        "onu_interface": onu.onu_interface,
                        "error": str(exc),
                        "duration_ms": int((perf_counter() - onu_started) * 1000),
                    }
                    summary["errors"].append(error)
                    summary["onu_results"].append({**error, "success": False})
                    continue

                signal_status = self._signal_status(rx.power_dbm)
                onu.rx_power = rx.power_dbm
                onu.tx_power = tx.power_dbm
                onu.signal_status = signal_status
                onu.last_monitored_at = datetime.now(UTC)
                self.db.add(OnuPowerHistory(onu_id=onu.id, rx_power=rx.power_dbm, tx_power=tx.power_dbm))
                summary["power_samples"] += 1
                summary["success"] += 1
                if signal_status == "warning":
                    summary["rx_warning"] += 1
                elif signal_status == "critical":
                    summary["rx_critical"] += 1
                summary["onu_results"].append(
                    {
                        "onu_id": onu.id,
                        "onu_interface": onu.onu_interface,
                        "success": True,
                        "rx_power": rx.power_dbm,
                        "tx_power": tx.power_dbm,
                        "signal_status": signal_status,
                        "duration_ms": int((perf_counter() - onu_started) * 1000),
                    }
                )

            summary["duration_ms"] = int((perf_counter() - started) * 1000)
            finished_at = datetime.now(UTC)
            self._record_monitoring_execution(
                olt.id,
                "sync_power",
                started_at,
                finished_at,
                summary["processed"],
                summary["success"],
                summary["failed"],
                summary,
            )
            self.db.commit()
            return summary
        except Exception as exc:
            summary["duration_ms"] = int((perf_counter() - started) * 1000)
            finished_at = datetime.now(UTC)
            self._record_monitoring_execution(
                olt.id,
                "sync_power",
                started_at,
                finished_at,
                summary["processed"],
                summary["success"],
                summary["failed"] + 1,
                {**summary, "error": str(exc)},
            )
            self.db.commit()
            raise
        finally:
            driver.disconnect()

    def read_only_check(self, olt: Olt) -> dict:
        if not olt.has_password:
            raise ValueError("Esta OLT no tiene contraseña guardada. Edite la OLT y registre una contraseña antes de probar conexión.")
        driver = self.olt_service.driver_for(olt)
        started = perf_counter()
        errors: list[dict] = []
        firmware = None
        cards = []
        states = []
        connection_success = False
        try:
            try:
                driver.connect(disable_paging=False)
                connection_success = True
            except Exception as exc:
                errors.append({"command": "connect", "error": str(exc)})
                self.db.commit()
                return {
                    "olt_id": olt.id,
                    "connection_success": False,
                    "firmware_detected": None,
                    "cards": [],
                    "onu_counts": {"total": 0, "working": 0, "offline": 0, "los": 0, "dying_gasp": 0},
                    "prompt_detected": None,
                    "duration_ms": int((perf_counter() - started) * 1000),
                    "errors": errors,
                }
            try:
                version_raw = self._call_read_only(
                    olt.id,
                    "show version-running",
                    lambda: driver.execute("show version-running", read_only=True),
                )
                firmware = self._detect_firmware(version_raw)
            except DriverCommandError as exc:
                errors.append({"command": exc.command, "error": exc.message})
            try:
                cards = self._call_read_only(olt.id, "show card", driver.show_card)
            except DriverCommandError as exc:
                errors.append({"command": exc.command, "error": exc.message})
            try:
                states = self._call_read_only(olt.id, "show gpon onu state", driver.show_onu_state)
            except DriverCommandError as exc:
                errors.append({"command": exc.command, "error": exc.message})
            self.db.commit()
            return {
                "olt_id": olt.id,
                "connection_success": connection_success,
                "firmware_detected": firmware,
                "cards": [asdict(card) for card in cards],
                "onu_counts": self._state_counts(states),
                "prompt_detected": getattr(driver, "last_prompt", None),
                "duration_ms": int((perf_counter() - started) * 1000),
                "errors": errors,
            }
        finally:
            driver.disconnect()

    def _state_counts(self, states) -> dict:
        counts = {"total": len(states), "working": 0, "offline": 0, "los": 0, "dying_gasp": 0}
        for state in states:
            cause = self._normalize_down_cause(state.last_down_cause)
            if state.status == "online":
                counts["working"] += 1
            elif cause == "LOS":
                counts["los"] += 1
            elif cause == "DyingGasp":
                counts["dying_gasp"] += 1
            else:
                counts["offline"] += 1
        return counts

    def _detect_firmware(self, output: str) -> str | None:
        for line in output.splitlines():
            stripped = line.strip()
            if stripped.lower().startswith("show "):
                continue
            if "version" in stripped.lower() or "software" in stripped.lower() or "V1.2.5P3" in stripped:
                return stripped
            if "V" in stripped and any(char.isdigit() for char in stripped):
                return line.strip()
        return output.splitlines()[0].strip() if output.splitlines() else None

    def _normalize_down_cause(self, cause: str | None) -> str | None:
        if not cause:
            return None
        normalized = cause.lower()
        if normalized == "los":
            return "LOS"
        if normalized == "dyinggasp":
            return "DyingGasp"
        if normalized == "offline":
            return "Offline"
        if normalized == "pwrfail":
            return "PWRFail"
        return cause

    def _event_for_state(self, status: str, cause: str | None) -> str:
        if status in {"online", "working"}:
            return "Working"
        return cause or "Offline"

    def _record_onu_event(self, olt_id: int, onu: Onu, event_type: str) -> None:
        self.db.add(
            OnuEventHistory(
                onu_id=onu.id,
                olt_id=olt_id,
                onu_interface=onu.onu_interface,
                event_type=event_type,
                description=f"ONU {onu.onu_interface} reporto {event_type}",
            )
        )
        self.events.record(event_type, "onu", onu.id, f"ONU {onu.onu_interface} reporto {event_type}")

    def _signal_status(self, rx_power: float) -> str:
        if rx_power < -27:
            return "critical"
        if rx_power < -24:
            return "warning"
        return "normal"
