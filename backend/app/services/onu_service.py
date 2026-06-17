from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Onu, OnuPowerHistory
from app.repositories.entities import OnuRepository
from app.services.event_service import EventService

CRITICAL_RX = -27
WARNING_RX = -24


class OnuService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = OnuRepository(db)
        self.events = EventService(db)

    def add_power_sample(self, onu_id: int, rx_power: float, tx_power: float) -> OnuPowerHistory:
        sample = OnuPowerHistory(onu_id=onu_id, rx_power=rx_power, tx_power=tx_power)
        self.db.add(sample)
        onu = self.db.get(Onu, onu_id)
        if onu:
            onu.rx_power = rx_power
            onu.tx_power = tx_power
            onu.last_monitored_at = datetime.now(UTC)
            if rx_power < CRITICAL_RX:
                onu.signal_status = "critical"
            elif rx_power < WARNING_RX:
                onu.signal_status = "warning"
            else:
                onu.signal_status = "normal"
        if rx_power < CRITICAL_RX:
            self.events.record("RX_CRITICAL", "onu", onu_id, f"Potencia critica RX {rx_power} dBm")
        elif WARNING_RX > rx_power >= CRITICAL_RX:
            self.events.record("RX_WARNING", "onu", onu_id, f"Potencia advertencia RX {rx_power} dBm")
        self.db.commit()
        self.db.refresh(sample)
        return sample

    def low_signal_count(self) -> int:
        return self.rx_warning_count() + self.rx_critical_count()

    def rx_warning_count(self) -> int:
        return len(self.db.scalars(select(Onu).where(Onu.signal_status == "warning")).all())

    def rx_critical_count(self) -> int:
        return len(self.db.scalars(select(Onu).where(Onu.signal_status == "critical")).all())
