from __future__ import annotations

import re
from datetime import UTC, datetime
from time import perf_counter, sleep

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.drivers.errors import DriverCommandError
from app.drivers.zte.c300_v125p3_telnet.parsers import parse_onu_power, parse_onu_state
from app.models.entities import DriverCommandLog, Olt, Onu, PonPort, ProvisioningPlan, UnauthorizedOnu, UnauthorizedOnuEvent
from app.services.olt_service import OltService


FORBIDDEN_COMMAND = re.compile(r"(?i)^\s*(?:write|save|reboot|reload|reset|delete|erase)(?:\s|$)")
CLI_ERROR = re.compile(r"(?im)^\s*%\s*(?:incomplete|invalid|unrecognized|ambiguous|error|failed|failure)\b")


class ProvisioningExecutionService:
    """Execute one preflight-passed plan and verify it before marking executed."""

    def __init__(self, db: Session):
        self.db = db
        self.olt_service = OltService(db)

    def execute(self, plan_id: int) -> dict:
        plan = self.db.get(ProvisioningPlan, plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan de aprovisionamiento no encontrado")
        if plan.status == "executed":
            raise HTTPException(status_code=409, detail="El plan ya fue ejecutado y no puede ejecutarse nuevamente")
        if plan.status != "preflight_passed":
            raise HTTPException(status_code=409, detail="Solo se pueden ejecutar planes preflight_passed")
        if not plan.generated_cli or not plan.selected_onu_id or not plan.pon_port_interface:
            raise HTTPException(status_code=409, detail="El plan no tiene CLI, ONU ID o puerto PON valido")

        olt = self.db.get(Olt, plan.olt_id)
        if not olt:
            raise HTTPException(status_code=404, detail="OLT no encontrada")

        config_commands = [line.strip() for line in plan.generated_cli.splitlines() if line.strip()]
        dangerous = [command for command in config_commands if FORBIDDEN_COMMAND.match(command)]
        if dangerous:
            raise HTTPException(status_code=409, detail={"message": "CLI contiene comandos prohibidos", "commands": dangerous})

        executed_commands: list[dict] = []
        driver = self.olt_service.driver_for(olt)
        onu_interface = plan.pon_port_interface.replace("gpon-olt_", "gpon-onu_", 1) + f":{plan.selected_onu_id}"

        try:
            driver.connect(disable_paging=False)
            self._run(driver, olt.id, "configure terminal", False, executed_commands)
            for command in config_commands:
                self._run(driver, olt.id, command, False, executed_commands)

            # Each generated block exits to global config mode; this final exit returns to exec mode.
            self._run(driver, olt.id, "exit", False, executed_commands)
            sleep(2)

            state_output = self._run(driver, olt.id, "show gpon onu state", True, executed_commands)
            state = next((item for item in parse_onu_state(state_output) if item.interface == onu_interface), None)
            if not state or (state.status != "online" and (state.phase_state or "").lower() != "working"):
                raise DriverCommandError(
                    command="show gpon onu state",
                    message=f"ONU {onu_interface} no aparece en estado working/online",
                    output=state_output,
                )

            rx_command = f"show pon power onu-rx {onu_interface}"
            rx_output = self._run(driver, olt.id, rx_command, True, executed_commands)
            rx = parse_onu_power(rx_output, onu_interface)
            if rx is None:
                raise DriverCommandError(rx_command, "No se pudo interpretar potencia RX", rx_output)

            tx_command = f"show pon power onu-tx {onu_interface}"
            tx_output = self._run(driver, olt.id, tx_command, True, executed_commands)
            tx = parse_onu_power(tx_output, onu_interface)
            if tx is None:
                raise DriverCommandError(tx_command, "No se pudo interpretar potencia TX", tx_output)

            self._finalize_inventory(plan, olt, onu_interface, state.status, rx.power_dbm, tx.power_dbm)
            plan.status = "executed"
            self.db.commit()
            return {
                "plan_id": plan.id,
                "status": plan.status,
                "onu_interface": onu_interface,
                "onu_status": state.status,
                "phase_state": state.phase_state,
                "rx_power": rx.power_dbm,
                "tx_power": tx.power_dbm,
                "commands": executed_commands,
                "warnings": [],
                "errors": [],
            }
        except Exception as exc:
            self.db.rollback()
            detail = {
                "message": str(exc),
                "plan_id": plan_id,
                "status": "stopped",
                "commands": executed_commands,
            }
            raise HTTPException(status_code=409, detail=detail) from exc
        finally:
            driver.disconnect(send_exit=False)

    def resume_management(self, plan_id: int) -> dict:
        plan = self.db.get(ProvisioningPlan, plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan de aprovisionamiento no encontrado")
        if plan.status == "executed":
            raise HTTPException(status_code=409, detail="El plan ya fue ejecutado y no puede reanudarse")
        if plan.status != "preflight_passed":
            raise HTTPException(status_code=409, detail="Solo se puede reanudar un plan preflight_passed")
        if not plan.generated_cli or not plan.selected_onu_id or not plan.pon_port_interface:
            raise HTTPException(status_code=409, detail="El plan no tiene CLI o identificadores validos")

        olt = self.db.get(Olt, plan.olt_id)
        if not olt:
            raise HTTPException(status_code=404, detail="OLT no encontrada")

        onu_interface = plan.pon_port_interface.replace("gpon-olt_", "gpon-onu_", 1) + f":{plan.selected_onu_id}"
        management_commands = self._management_commands(plan.generated_cli, onu_interface)
        dangerous = [command for command in management_commands if FORBIDDEN_COMMAND.match(command)]
        if dangerous:
            raise HTTPException(status_code=409, detail={"message": "Bloque management contiene comandos prohibidos", "commands": dangerous})

        results: list[dict] = []
        driver = self.olt_service.driver_for(olt)
        try:
            driver.connect(disable_paging=False)
            # Required session context only; no ONU authorization/base commands are repeated.
            self._run(driver, olt.id, "configure terminal", False, results)
            for command in management_commands:
                self._run(driver, olt.id, command, False, results)
            self._run(driver, olt.id, "exit", False, results)
            sleep(2)

            state_output = self._run(driver, olt.id, "show gpon onu state", True, results)
            state = next((item for item in parse_onu_state(state_output) if item.interface == onu_interface), None)
            if not state or (state.status != "online" and (state.phase_state or "").lower() != "working"):
                raise DriverCommandError("show gpon onu state", f"ONU {onu_interface} no aparece working/online", state_output)

            rx_command = f"show pon power onu-rx {onu_interface}"
            rx_output = self._run(driver, olt.id, rx_command, True, results)
            rx = parse_onu_power(rx_output, onu_interface)
            if rx is None:
                raise DriverCommandError(rx_command, "No se pudo interpretar potencia RX", rx_output)

            tx_command = f"show pon power onu-tx {onu_interface}"
            tx_output = self._run(driver, olt.id, tx_command, True, results)
            tx = parse_onu_power(tx_output, onu_interface)
            if tx is None:
                raise DriverCommandError(tx_command, "No se pudo interpretar potencia TX", tx_output)

            self._finalize_inventory(plan, olt, onu_interface, state.status, rx.power_dbm, tx.power_dbm)
            plan.status = "executed"
            self.db.commit()
            return {
                "plan_id": plan.id,
                "status": plan.status,
                "onu_interface": onu_interface,
                "onu_status": state.status,
                "phase_state": state.phase_state,
                "rx_power": rx.power_dbm,
                "tx_power": tx.power_dbm,
                "management_commands": management_commands,
                "commands": results,
                "warnings": [],
                "errors": [],
            }
        except Exception as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=409,
                detail={
                    "message": str(exc),
                    "plan_id": plan_id,
                    "status": "stopped",
                    "management_commands": management_commands,
                    "commands": results,
                },
            ) from exc
        finally:
            driver.disconnect(send_exit=False)

    @staticmethod
    def _management_commands(generated_cli: str, onu_interface: str) -> list[str]:
        lines = [line.strip() for line in generated_cli.splitlines() if line.strip()]
        expected = f"pon-onu-mng {onu_interface}"
        try:
            start = lines.index(expected)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=f"El CLI no contiene {expected}") from exc
        block = lines[start:]
        try:
            end = block.index("exit")
        except ValueError as exc:
            raise HTTPException(status_code=409, detail="El bloque pon-onu-mng no contiene exit") from exc
        commands = block[: end + 1]
        if not commands or commands[0] != expected:
            raise HTTPException(status_code=409, detail="Bloque management invalido")
        return commands

    def finalize_executed_inventory(self, plan_id: int) -> Onu:
        """Reconcile local inventory for an already verified execution without contacting the OLT."""
        plan = self.db.get(ProvisioningPlan, plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan de aprovisionamiento no encontrado")
        if plan.status != "executed":
            raise HTTPException(status_code=409, detail="Solo se puede cerrar inventario de un plan executed")
        olt = self.db.get(Olt, plan.olt_id)
        if not olt or not plan.selected_onu_id or not plan.pon_port_interface:
            raise HTTPException(status_code=409, detail="El plan ejecutado no tiene identificadores validos")
        onu_interface = plan.pon_port_interface.replace("gpon-olt_", "gpon-onu_", 1) + f":{plan.selected_onu_id}"
        onu = self._finalize_inventory(plan, olt, onu_interface, "unknown", None, None)
        self.db.commit()
        self.db.refresh(onu)
        return onu

    def _finalize_inventory(
        self,
        plan: ProvisioningPlan,
        olt: Olt,
        onu_interface: str,
        status: str,
        rx_power: float | None,
        tx_power: float | None,
    ) -> Onu:
        onu = self.db.scalar(select(Onu).where(Onu.olt_id == olt.id, Onu.serial_number == plan.serial_number))
        if onu is None:
            onu = Onu(
                olt_id=olt.id,
                serial_number=plan.serial_number,
                customer_name=plan.customer_name,
                onu_interface=onu_interface,
                onu_type=plan.onu_type,
                vlan=plan.vlan,
                speed_profile=plan.speed_profile_down,
            )
            self.db.add(onu)

        pon_port = self.db.scalar(
            select(PonPort).where(PonPort.olt_id == olt.id, PonPort.interface_name == plan.pon_port_interface)
        )
        onu.olt_code_snapshot = olt.olt_code
        onu.pon_port_id = pon_port.id if pon_port else None
        onu.zone_id = plan.zone_id
        onu.nap_id = plan.nap_id
        onu.customer_name = plan.customer_name
        onu.customer_reference = plan.customer_reference
        onu.serial_number = plan.serial_number
        onu.onu_interface = onu_interface
        onu.onu_type = plan.onu_type
        onu.vlan = plan.vlan
        onu.speed_profile = plan.speed_profile_down
        onu.speed_profile_up = plan.speed_profile_up
        onu.speed_profile_down = plan.speed_profile_down
        onu.nap_port = plan.nap_port
        if status != "unknown" or not onu.status:
            onu.status = status
        if rx_power is not None:
            onu.rx_power = rx_power
            onu.signal_status = self._signal_status(rx_power)
        if tx_power is not None:
            onu.tx_power = tx_power
        if rx_power is not None or tx_power is not None:
            onu.last_monitored_at = datetime.now(UTC)
        onu.raw_description = plan.onu_description
        onu.description_original = plan.description_original
        onu.description_generated = plan.description_generated or plan.onu_description
        onu.zone_name = plan.zone_name
        onu.address_reference = plan.address_reference or plan.address
        onu.nap_name = plan.nap_name
        onu.nap_port_label = plan.nap_port_label
        onu.odb_name = plan.odb_name
        onu.external_id = plan.external_id
        onu.service_mode_code = plan.service_mode_code
        onu.source = "provisioning"
        onu.import_source = "provisioning_plan"

        pending = self.db.get(UnauthorizedOnu, plan.unauthorized_onu_id)
        if pending and pending.status != "provisioned":
            pending.status = "provisioned"
            self.db.add(
                UnauthorizedOnuEvent(
                    unauthorized_onu_id=pending.id,
                    event_type="provisioned",
                    description=f"ONU {plan.serial_number} provisionada por plan {plan.id}",
                )
            )
        return onu

    @staticmethod
    def _signal_status(rx_power: float | None) -> str | None:
        if rx_power is None:
            return None
        if rx_power >= -24:
            return "normal"
        if rx_power >= -27:
            return "warning"
        return "critical"

    def _run(self, driver, olt_id: int, command: str, read_only: bool, results: list[dict]) -> str:
        started = perf_counter()
        try:
            output = driver.execute(command, read_only=read_only)
            if CLI_ERROR.search(output):
                raise DriverCommandError(command, "La OLT devolvio un error", output)
        except Exception as exc:
            duration_ms = int((perf_counter() - started) * 1000)
            output = getattr(exc, "output", "") or ""
            self._log(olt_id, command, read_only, False, duration_ms, output, str(exc))
            results.append(
                {
                    "command": command,
                    "success": False,
                    "read_only": read_only,
                    "duration_ms": duration_ms,
                    "output": output,
                    "error": str(exc),
                }
            )
            raise

        duration_ms = int((perf_counter() - started) * 1000)
        self._log(olt_id, command, read_only, True, duration_ms, output, None)
        results.append(
            {
                "command": command,
                "success": True,
                "read_only": read_only,
                "duration_ms": duration_ms,
                "output": output,
                "error": None,
            }
        )
        return output

    def _log(
        self,
        olt_id: int,
        command: str,
        read_only: bool,
        success: bool,
        duration_ms: int,
        output: str,
        error: str | None,
    ) -> None:
        self.db.add(
            DriverCommandLog(
                olt_id=olt_id,
                command=command,
                success=success,
                read_only=read_only,
                duration_ms=duration_ms,
                error_message=error,
                output_excerpt=output[-12000:] if output else "",
            )
        )
        self.db.commit()
