from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decrypt_secret, encrypt_secret
from app.drivers.zte.c300_v125p3_telnet import ZteC300V125P3TelnetDriver
from app.models.entities import BackupFile, Olt
from app.repositories.entities import OltRepository
from app.services.event_service import EventService


class OltService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = OltRepository(db)
        self.events = EventService(db)

    def create(self, data: dict) -> Olt:
        password = data.pop("password")
        snmp_ro = data.pop("snmp_ro_community", None)
        snmp_rw = data.pop("snmp_rw_community", None)
        data["olt_code"] = self._normalize_olt_code(data["olt_code"])
        data["environment"] = self._normalize_environment(data.get("environment", "production"))
        self._ensure_unique_olt_code(data["olt_code"])
        data.setdefault("initial_import_status", "pending")
        if snmp_ro and snmp_ro.strip():
            data["snmp_ro_community_encrypted"] = encrypt_secret(snmp_ro)
        if snmp_rw and snmp_rw.strip():
            data["snmp_rw_community_encrypted"] = encrypt_secret(snmp_rw)
        olt = self.repo.create({**data, "password_encrypted": encrypt_secret(password)})
        self.events.record("OLT_CREATED", "olt", olt.id, f"OLT {olt.name} registrada")
        return olt

    def update(self, olt: Olt, data: dict) -> Olt:
        if data.get("olt_code") is not None:
            data["olt_code"] = self._normalize_olt_code(data["olt_code"])
            self._ensure_unique_olt_code(data["olt_code"], exclude_id=olt.id)
        if data.get("environment") is not None:
            data["environment"] = self._normalize_environment(data["environment"])
        if data.get("password"):
            data["password_encrypted"] = encrypt_secret(data.pop("password"))
        else:
            data.pop("password", None)
        if data.get("snmp_ro_community"):
            data["snmp_ro_community_encrypted"] = encrypt_secret(data.pop("snmp_ro_community"))
        else:
            data.pop("snmp_ro_community", None)
        if data.get("snmp_rw_community"):
            data["snmp_rw_community_encrypted"] = encrypt_secret(data.pop("snmp_rw_community"))
        else:
            data.pop("snmp_rw_community", None)
        updated = self.repo.update(olt, {key: value for key, value in data.items() if value is not None})
        self.events.record("OLT_UPDATED", "olt", updated.id, f"OLT {updated.name} actualizada")
        return updated

    def can_provision(self, olt_id: int) -> bool:
        olt = self.db.get(Olt, olt_id)
        return bool(olt and olt.initial_import_status == "confirmed")

    def is_production_olt(self, olt_id: int) -> bool:
        olt = self.db.get(Olt, olt_id)
        return bool(olt and olt.environment == "production")

    def _normalize_olt_code(self, value: str) -> str:
        return value.strip().upper()

    def _normalize_environment(self, value: str) -> str:
        normalized = (value or "production").strip().lower()
        if normalized not in {"production", "lab"}:
            raise ValueError("environment must be production or lab")
        return normalized

    def _ensure_unique_olt_code(self, olt_code: str, exclude_id: int | None = None) -> None:
        statement = select(Olt).where(Olt.olt_code == olt_code)
        if exclude_id is not None:
            statement = statement.where(Olt.id != exclude_id)
        if self.db.scalar(statement):
            raise ValueError("olt_code already exists")

    def driver_for(self, olt: Olt) -> ZteC300V125P3TelnetDriver:
        return ZteC300V125P3TelnetDriver(
            host=olt.ip_address,
            port=olt.telnet_port,
            username=olt.username,
            password=decrypt_secret(olt.password_encrypted),
        )

    def test_connection(self, olt: Olt) -> bool:
        driver = self.driver_for(olt)
        try:
            driver.connect()
            healthy = driver.health_check()
            olt.status = "online" if healthy else "degraded"
            self.db.commit()
            return healthy
        finally:
            driver.disconnect()

    def backup(self, olt: Olt) -> BackupFile:
        driver = self.driver_for(olt)
        try:
            driver.connect()
            content = driver.backup()
        finally:
            driver.disconnect()
        backup_dir = Path("storage/backups")
        backup_dir.mkdir(parents=True, exist_ok=True)
        file_path = backup_dir / f"olt-{olt.id}-running-config.txt"
        file_path.write_text(content, encoding="utf-8")
        record = BackupFile(olt_id=olt.id, file_path=str(file_path))
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        self.events.record("BACKUP_CREATED", "olt", olt.id, f"Backup ejecutado para {olt.name}")
        return record
