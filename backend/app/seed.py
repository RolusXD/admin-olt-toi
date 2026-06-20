import os

from app.core.database import SessionLocal
from app.core.security import encrypt_secret
from app.models.entities import Nap, Olt, Onu, OnuPowerHistory, PonPort, Zone


def run() -> None:
    with SessionLocal() as db:
        if db.query(Olt).first():
            return
        olt_username = (os.getenv("SEED_OLT_USERNAME") or "").strip()
        olt_password = os.getenv("SEED_OLT_PASSWORD") or ""
        if not olt_username or not olt_password:
            raise RuntimeError("SEED_OLT_USERNAME and SEED_OLT_PASSWORD are required to create demo OLT data")
        olt = Olt(
            olt_code="OLT-0001",
            name="OLT Principal ZTE C300",
            vendor="ZTE",
            model="C300",
            firmware="V1.2.5P3",
            ip_address="10.0.0.2",
            telnet_port=23,
            username=olt_username,
            password_encrypted=encrypt_secret(olt_password),
            status="online",
        )
        zone = Zone(name="Zona Central", description="Anillo urbano principal")
        db.add_all([olt, zone])
        db.commit()
        db.refresh(olt)
        db.refresh(zone)

        pon = PonPort(olt_id=olt.id, slot=1, port=2, description="PON Centro")
        nap = Nap(zone_id=zone.id, name="NAP-CEN-001", latitude=-17.7833, longitude=-63.1821, capacity=8)
        db.add_all([pon, nap])
        db.commit()
        db.refresh(pon)
        db.refresh(nap)

        onu = Onu(
            olt_id=olt.id,
            pon_port_id=pon.id,
            zone_id=zone.id,
            nap_id=nap.id,
            customer_name="Cliente Piloto",
            serial_number="ZTEG12345678",
            onu_interface="gpon-onu_1/2/1:1",
            onu_type="F660",
            vlan=100,
            speed_profile="50M",
            nap_port=1,
            distance_m=820,
            status="online",
        )
        db.add(onu)
        db.commit()
        db.refresh(onu)
        db.add_all(
            [
                OnuPowerHistory(onu_id=onu.id, rx_power=-21.4, tx_power=2.1),
                OnuPowerHistory(onu_id=onu.id, rx_power=-23.2, tx_power=2.0),
            ]
        )
        db.commit()


if __name__ == "__main__":
    run()
