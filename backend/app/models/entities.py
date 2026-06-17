from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Olt(Base, TimestampMixin):
    __tablename__ = "olts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    olt_code: Mapped[str] = mapped_column(String(80), unique=True)
    display_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    environment: Mapped[str] = mapped_column(String(30), default="production")
    vendor: Mapped[str] = mapped_column(String(40), default="ZTE")
    model: Mapped[str] = mapped_column(String(80), default="C300")
    firmware: Mapped[str] = mapped_column(String(80), default="V1.2.5P3")
    ip_address: Mapped[str] = mapped_column(String(64))
    telnet_port: Mapped[int] = mapped_column(Integer, default=23)
    username: Mapped[str] = mapped_column(String(120))
    password_encrypted: Mapped[str] = mapped_column(Text)
    connection_type: Mapped[str] = mapped_column(String(30), default="telnet")
    status: Mapped[str] = mapped_column(String(30), default="unknown")
    initial_import_status: Mapped[str] = mapped_column(String(40), default="pending")
    last_import_job_id: Mapped[int | None] = mapped_column(ForeignKey("import_jobs.id", ondelete="SET NULL"), nullable=True)
    last_import_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    pon_ports: Mapped[list["PonPort"]] = relationship(back_populates="olt", cascade="all, delete-orphan")
    onus: Mapped[list["Onu"]] = relationship(back_populates="olt")

    @property
    def has_password(self) -> bool:
        return bool(self.password_encrypted and self.password_encrypted.strip())

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


class ConfigSnapshot(Base):
    __tablename__ = "config_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    olt_id: Mapped[int] = mapped_column(ForeignKey("olts.id", ondelete="CASCADE"))
    raw_config: Mapped[str] = mapped_column(Text)
    source_command: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ImportJob(Base):
    __tablename__ = "import_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    olt_id: Mapped[int] = mapped_column(ForeignKey("olts.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(40), default="preview")
    source: Mapped[str] = mapped_column(String(30), default="text")
    raw_config_snapshot_id: Mapped[int] = mapped_column(ForeignKey("config_snapshots.id", ondelete="CASCADE"))
    parsed_summary_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Vlan(Base):
    __tablename__ = "vlans"
    __table_args__ = (UniqueConstraint("olt_id", "vlan_id", name="uq_vlans_olt_vlan"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    olt_id: Mapped[int] = mapped_column(ForeignKey("olts.id", ondelete="CASCADE"))
    vlan_id: Mapped[int] = mapped_column(Integer)
    name: Mapped[str | None] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    olt: Mapped[Olt] = relationship()

    @property
    def olt_code(self) -> str | None:
        return self.olt.olt_code if self.olt else None

    @property
    def olt_name(self) -> str | None:
        return self.olt.name if self.olt else None

    @property
    def olt_environment(self) -> str | None:
        return self.olt.environment if self.olt else None


class GponProfile(Base):
    __tablename__ = "gpon_profiles"
    __table_args__ = (UniqueConstraint("olt_id", "profile_type", "name", name="uq_gpon_profiles_olt_type_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    olt_id: Mapped[int] = mapped_column(ForeignKey("olts.id", ondelete="CASCADE"))
    profile_type: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(120))
    upstream_rate: Mapped[int | None] = mapped_column(Integer)
    downstream_rate: Mapped[int | None] = mapped_column(Integer)


class OnuType(Base):
    __tablename__ = "onu_types"
    __table_args__ = (UniqueConstraint("olt_id", "name", name="uq_onu_types_olt_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    olt_id: Mapped[int] = mapped_column(ForeignKey("olts.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))
    vendor_detected: Mapped[str | None] = mapped_column(String(80))
    max_tcont: Mapped[int | None] = mapped_column(Integer)
    max_gemport: Mapped[int | None] = mapped_column(Integer)
    max_ports: Mapped[int | None] = mapped_column(Integer)


class Zone(Base):
    __tablename__ = "zones"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    description: Mapped[str | None] = mapped_column(Text)

    naps: Mapped[list["Nap"]] = relationship(back_populates="zone")


class Nap(Base):
    __tablename__ = "naps"
    __table_args__ = (UniqueConstraint("zone_id", "name", name="uq_naps_zone_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    zone_id: Mapped[int] = mapped_column(ForeignKey("zones.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    capacity: Mapped[int] = mapped_column(Integer, default=8)
    description: Mapped[str | None] = mapped_column(Text)

    zone: Mapped[Zone] = relationship(back_populates="naps")


class PonPort(Base):
    __tablename__ = "pon_ports"
    __table_args__ = (UniqueConstraint("olt_id", "interface_name", name="uq_pon_ports_olt_interface"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    olt_id: Mapped[int] = mapped_column(ForeignKey("olts.id", ondelete="CASCADE"))
    rack: Mapped[int | None] = mapped_column(Integer)
    shelf: Mapped[int | None] = mapped_column(Integer)
    slot: Mapped[int] = mapped_column(Integer)
    port: Mapped[int] = mapped_column(Integer)
    interface_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    description: Mapped[str | None] = mapped_column(Text)

    olt: Mapped[Olt] = relationship(back_populates="pon_ports")

    @property
    def olt_code(self) -> str | None:
        return self.olt.olt_code if self.olt else None

    @property
    def olt_name(self) -> str | None:
        return self.olt.name if self.olt else None

    @property
    def olt_environment(self) -> str | None:
        return self.olt.environment if self.olt else None


class Onu(Base, TimestampMixin):
    __tablename__ = "onus"
    __table_args__ = (UniqueConstraint("olt_id", "serial_number", name="uq_onus_olt_serial"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    olt_id: Mapped[int] = mapped_column(ForeignKey("olts.id", ondelete="CASCADE"))
    olt_code_snapshot: Mapped[str | None] = mapped_column(String(80), nullable=True)
    pon_port_id: Mapped[int | None] = mapped_column(ForeignKey("pon_ports.id", ondelete="SET NULL"))
    zone_id: Mapped[int | None] = mapped_column(ForeignKey("zones.id", ondelete="SET NULL"))
    nap_id: Mapped[int | None] = mapped_column(ForeignKey("naps.id", ondelete="SET NULL"))
    customer_name: Mapped[str] = mapped_column(String(160))
    customer_reference: Mapped[str | None] = mapped_column(String(160), nullable=True)
    external_customer_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    serial_number: Mapped[str] = mapped_column(String(80))
    onu_interface: Mapped[str] = mapped_column(String(80))
    onu_type: Mapped[str] = mapped_column(String(80))
    vlan: Mapped[int] = mapped_column(Integer)
    speed_profile: Mapped[str] = mapped_column(String(80))
    speed_profile_up: Mapped[str | None] = mapped_column(String(80), nullable=True)
    speed_profile_down: Mapped[str | None] = mapped_column(String(80), nullable=True)
    rx_power: Mapped[float | None] = mapped_column(Float, nullable=True)
    tx_power: Mapped[float | None] = mapped_column(Float, nullable=True)
    signal_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    last_monitored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    nap_port: Mapped[int | None] = mapped_column(Integer)
    distance_m: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default="unknown")
    last_down_cause: Mapped[str | None] = mapped_column(String(80))
    imported_from_config: Mapped[bool] = mapped_column(default=False)
    auth_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    raw_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    parsed_zone_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    parsed_nap_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    parsed_nap_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parsed_odn: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source: Mapped[str] = mapped_column(String(40), default="manual")
    import_source: Mapped[str] = mapped_column(String(40), default="manual")

    olt: Mapped[Olt] = relationship(back_populates="onus")
    power_history: Mapped[list["OnuPowerHistory"]] = relationship(back_populates="onu", cascade="all, delete-orphan")

    @property
    def olt_code(self) -> str | None:
        return self.olt.olt_code if self.olt else None

    @property
    def olt_name(self) -> str | None:
        return self.olt.name if self.olt else None

    @property
    def olt_display_name(self) -> str | None:
        return self.olt.display_name if self.olt else None

    @property
    def olt_environment(self) -> str | None:
        return self.olt.environment if self.olt else None


class UnauthorizedOnu(Base):
    __tablename__ = "unauthorized_onus"
    __table_args__ = (UniqueConstraint("olt_id", "serial_number", name="uq_unauthorized_onus_olt_serial"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    olt_id: Mapped[int] = mapped_column(ForeignKey("olts.id", ondelete="CASCADE"))
    olt_code_snapshot: Mapped[str | None] = mapped_column(String(80), nullable=True)
    pon_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    slot: Mapped[int | None] = mapped_column(Integer, nullable=True)
    port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pon_port_interface: Mapped[str | None] = mapped_column(String(80), nullable=True)
    serial_number: Mapped[str] = mapped_column(String(80))
    detected_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    detected_vendor: Mapped[str | None] = mapped_column(String(80), nullable=True)
    raw_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="pending")
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    times_detected: Mapped[int] = mapped_column(Integer, default=1)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    olt: Mapped[Olt] = relationship()
    events: Mapped[list["UnauthorizedOnuEvent"]] = relationship(back_populates="unauthorized_onu", cascade="all, delete-orphan")

    @property
    def olt_code(self) -> str | None:
        return self.olt.olt_code if self.olt else None

    @property
    def olt_name(self) -> str | None:
        return self.olt.name if self.olt else None

    @property
    def olt_environment(self) -> str | None:
        return self.olt.environment if self.olt else None


class UnauthorizedOnuEvent(Base):
    __tablename__ = "unauthorized_onu_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    unauthorized_onu_id: Mapped[int] = mapped_column(ForeignKey("unauthorized_onus.id", ondelete="CASCADE"))
    event_type: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    unauthorized_onu: Mapped[UnauthorizedOnu] = relationship(back_populates="events")


class OnuPowerHistory(Base):
    __tablename__ = "onu_power_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    onu_id: Mapped[int] = mapped_column(ForeignKey("onus.id", ondelete="CASCADE"))
    rx_power: Mapped[float] = mapped_column(Float)
    tx_power: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    onu: Mapped[Onu] = relationship(back_populates="power_history")


class OnuEventHistory(Base):
    __tablename__ = "onu_event_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    onu_id: Mapped[int | None] = mapped_column(ForeignKey("onus.id", ondelete="SET NULL"))
    olt_id: Mapped[int] = mapped_column(ForeignKey("olts.id", ondelete="CASCADE"))
    onu_interface: Mapped[str] = mapped_column(String(80))
    event_type: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProvisioningTemplate(Base):
    __tablename__ = "provisioning_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    vendor: Mapped[str] = mapped_column(String(40), default="ZTE")
    model: Mapped[str] = mapped_column(String(80), default="C300")
    firmware: Mapped[str | None] = mapped_column(String(80), nullable=True)
    template_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    template_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(default=False)
    commands: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProvisioningPlan(Base, TimestampMixin):
    __tablename__ = "provisioning_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    olt_id: Mapped[int] = mapped_column(ForeignKey("olts.id", ondelete="CASCADE"))
    olt_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    unauthorized_onu_id: Mapped[int] = mapped_column(ForeignKey("unauthorized_onus.id", ondelete="CASCADE"))
    serial_number: Mapped[str] = mapped_column(String(80))
    pon_port_interface: Mapped[str | None] = mapped_column(String(80), nullable=True)
    customer_name: Mapped[str] = mapped_column(String(160))
    customer_reference: Mapped[str | None] = mapped_column(String(160), nullable=True)
    technical_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    zone_id: Mapped[int] = mapped_column(ForeignKey("zones.id", ondelete="RESTRICT"))
    nap_id: Mapped[int] = mapped_column(ForeignKey("naps.id", ondelete="RESTRICT"))
    nap_port: Mapped[int] = mapped_column(Integer)
    onu_type: Mapped[str] = mapped_column(String(80))
    vlan: Mapped[int] = mapped_column(Integer)
    speed_profile_up: Mapped[str] = mapped_column(String(120))
    speed_profile_down: Mapped[str] = mapped_column(String(120))
    generated_cli: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_warnings_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_errors_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="draft")

    olt: Mapped[Olt] = relationship()
    unauthorized_onu: Mapped[UnauthorizedOnu] = relationship()
    zone: Mapped[Zone] = relationship()
    nap: Mapped[Nap] = relationship()


class DriverCommandLog(Base):
    __tablename__ = "driver_command_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    olt_id: Mapped[int | None] = mapped_column(ForeignKey("olts.id", ondelete="SET NULL"))
    command: Mapped[str] = mapped_column(Text)
    success: Mapped[bool] = mapped_column(default=True)
    read_only: Mapped[bool] = mapped_column(default=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    output_excerpt: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    olt: Mapped[Olt | None] = relationship()

    @property
    def olt_code(self) -> str | None:
        return self.olt.olt_code if self.olt else None

    @property
    def olt_name(self) -> str | None:
        return self.olt.name if self.olt else None

    @property
    def olt_environment(self) -> str | None:
        return self.olt.environment if self.olt else None


class MonitoringExecution(Base):
    __tablename__ = "monitoring_executions"

    id: Mapped[int] = mapped_column(primary_key=True)
    olt_id: Mapped[int] = mapped_column(ForeignKey("olts.id", ondelete="CASCADE"))
    task_type: Mapped[str] = mapped_column(String(40))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processed_count: Mapped[int] = mapped_column(Integer, default=0)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    details_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    olt: Mapped[Olt] = relationship()

    @property
    def olt_code(self) -> str | None:
        return self.olt.olt_code if self.olt else None

    @property
    def olt_name(self) -> str | None:
        return self.olt.name if self.olt else None

    @property
    def olt_environment(self) -> str | None:
        return self.olt.environment if self.olt else None


class EventLog(Base):
    __tablename__ = "event_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String(80))
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BackupFile(Base):
    __tablename__ = "backup_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    olt_id: Mapped[int] = mapped_column(ForeignKey("olts.id", ondelete="CASCADE"))
    file_path: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
