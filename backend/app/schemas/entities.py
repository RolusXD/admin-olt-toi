from datetime import datetime
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator


OLT_CODE_RE = re.compile(r"^[A-Z0-9_-]+$")
ENVIRONMENTS = {"production", "lab"}


def normalize_olt_code(value: str) -> str:
    normalized = (value or "").strip().upper()
    if not normalized:
        raise ValueError("olt_code is required")
    if " " in normalized or not OLT_CODE_RE.match(normalized):
        raise ValueError("olt_code solo permite letras, numeros, guion y guion bajo")
    return normalized


class OltBase(BaseModel):
    olt_code: str
    name: str
    display_name: str | None = None
    environment: str = "production"
    vendor: str = "ZTE"
    model: str = "C300"
    firmware: str = "V1.2.5P3"
    hardware_version: str | None = None
    software_version: str | None = None
    pon_supported_types: str = "GPON"
    ip_address: str
    telnet_port: int = Field(default=23, ge=1)
    username: str
    snmp_udp_port: int = Field(default=161, ge=1)
    connection_type: str = "telnet"
    status: str = "unknown"

    @field_validator("olt_code")
    @classmethod
    def validate_olt_code(cls, value: str) -> str:
        return normalize_olt_code(value)

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, value: str) -> str:
        normalized = (value or "production").strip().lower()
        if normalized not in ENVIRONMENTS:
            raise ValueError("environment must be production or lab")
        return normalized


class OltCreate(OltBase):
    password: str = Field(min_length=1)
    snmp_ro_community: str | None = None
    snmp_rw_community: str | None = None

    @field_validator("password")
    @classmethod
    def password_must_not_be_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("password is required")
        return value


class OltUpdate(BaseModel):
    olt_code: str | None = None
    name: str | None = None
    display_name: str | None = None
    environment: str | None = None
    vendor: str | None = None
    model: str | None = None
    firmware: str | None = None
    hardware_version: str | None = None
    software_version: str | None = None
    pon_supported_types: str | None = None
    ip_address: str | None = None
    telnet_port: int | None = Field(default=None, ge=1)
    username: str | None = None
    password: str | None = None
    snmp_ro_community: str | None = None
    snmp_rw_community: str | None = None
    snmp_udp_port: int | None = Field(default=None, ge=1)
    connection_type: str | None = None
    status: str | None = None

    @field_validator("olt_code")
    @classmethod
    def validate_optional_olt_code(cls, value: str | None) -> str | None:
        return normalize_olt_code(value) if value is not None else None

    @field_validator("environment")
    @classmethod
    def validate_optional_environment(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if normalized not in ENVIRONMENTS:
            raise ValueError("environment must be production or lab")
        return normalized


class OltRead(OltBase):
    id: int
    has_password: bool
    initial_import_status: str
    last_import_job_id: int | None = None
    last_import_confirmed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class OltInventorySummary(BaseModel):
    olt_id: int
    olt_code: str
    olt_name: str
    environment: str
    initial_import_status: str
    last_import_confirmed_at: datetime | None = None
    onus: int
    pon_ports: int
    vlans: int
    profiles: int
    last_confirmed_import: datetime | None = None


class OltDataQualitySummary(BaseModel):
    olt_id: int
    total_onus: int
    complete: int
    needs_review: int
    legacy_incomplete: int
    blocked: int
    quality_score: float


class ZoneSchema(BaseModel):
    olt_id: int | None = None
    olt_code_snapshot: str | None = None
    name: str
    code: str | None = None
    description: str | None = None
    is_active: bool = True
    source: str = "manual"
    notes: str | None = None


class ZoneRead(ZoneSchema):
    id: int
    model_config = ConfigDict(from_attributes=True)


class NapSchema(BaseModel):
    olt_id: int | None = None
    olt_code_snapshot: str | None = None
    zone_id: int
    name: str
    code: str | None = None
    nap_type: str = "NAP"
    latitude: float | None = None
    longitude: float | None = None
    capacity: int = 8
    address_reference: str | None = None
    description: str | None = None
    is_active: bool = True
    source: str = "manual"
    notes: str | None = None


class NapRead(NapSchema):
    id: int
    model_config = ConfigDict(from_attributes=True)


class PonPortSchema(BaseModel):
    olt_id: int
    rack: int | None = None
    shelf: int | None = None
    slot: int
    port: int
    interface_name: str | None = None
    description: str | None = None


class PonPortRead(PonPortSchema):
    id: int
    olt_code: str | None = None
    olt_name: str | None = None
    olt_environment: str | None = None
    model_config = ConfigDict(from_attributes=True)


class VlanRead(BaseModel):
    id: int
    olt_id: int
    olt_code: str | None = None
    olt_name: str | None = None
    olt_environment: str | None = None
    olt_code_snapshot: str | None = None
    vlan_id: int
    name: str | None = None
    description: str | None = None
    service_type: str = "internet"
    is_active: bool = True
    source: str = "imported"
    notes: str | None = None
    onu_count: int = 0
    is_default_for_provisioning: bool = False
    model_config = ConfigDict(from_attributes=True)


class VlanCreate(BaseModel):
    olt_id: int
    vlan_id: int
    name: str | None = None
    description: str | None = None
    service_type: str = "internet"
    is_active: bool = True
    source: str = "manual"
    notes: str | None = None
    is_default_for_provisioning: bool = False


class VlanUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    service_type: str | None = None
    is_active: bool | None = None
    notes: str | None = None
    is_default_for_provisioning: bool | None = None


class OnuTypeCreate(BaseModel):
    olt_id: int
    vendor: str = "ZTE"
    model: str = "C300"
    firmware: str = "V1.2.5P3"
    name: str
    display_name: str | None = None
    operational_alias: str | None = None
    vendor_detected: str | None = None
    model_detected: str | None = None
    technology: str = "GPON"
    pon_type: str = "GPON"
    channel_gpon: bool = True
    channel_xgpon: bool = False
    channel_xgspon: bool = False
    max_tcont: int | None = None
    max_gemport: int | None = None
    max_ports: int | None = None
    max_switch_perslot: int | None = None
    max_flow_perswitch: int | None = None
    max_iphost: int | None = None
    ethernet_ports: int | None = None
    wifi_ports: int | None = None
    pots_ports: int | None = None
    rf_ports: int | None = None
    allow_custom_profiles: bool = True
    default_custom_profile_id: int | None = None
    capability_mode: str = "bridging"
    is_active: bool = True
    is_provisioning_allowed: bool = False
    is_default_for_provisioning: bool = False
    source: str = "manual"
    notes: str | None = None


class OnuTypeUpdate(BaseModel):
    vendor: str | None = None
    model: str | None = None
    firmware: str | None = None
    name: str | None = None
    display_name: str | None = None
    operational_alias: str | None = None
    vendor_detected: str | None = None
    model_detected: str | None = None
    technology: str | None = None
    pon_type: str | None = None
    channel_gpon: bool | None = None
    channel_xgpon: bool | None = None
    channel_xgspon: bool | None = None
    max_tcont: int | None = None
    max_gemport: int | None = None
    max_ports: int | None = None
    max_switch_perslot: int | None = None
    max_flow_perswitch: int | None = None
    max_iphost: int | None = None
    ethernet_ports: int | None = None
    wifi_ports: int | None = None
    pots_ports: int | None = None
    rf_ports: int | None = None
    allow_custom_profiles: bool | None = None
    default_custom_profile_id: int | None = None
    capability_mode: str | None = None
    is_active: bool | None = None
    is_provisioning_allowed: bool | None = None
    is_default_for_provisioning: bool | None = None
    notes: str | None = None


class OnuTypeRead(OnuTypeCreate):
    id: int
    olt_code: str | None = None
    olt_name: str | None = None
    olt_environment: str | None = None
    olt_code_snapshot: str | None = None
    model_config = ConfigDict(from_attributes=True)


class SpeedProfileCreate(BaseModel):
    olt_id: int
    vendor: str = "ZTE"
    model: str = "C300"
    firmware: str = "V1.2.5P3"
    name: str
    profile_code: str
    upstream_profile_name: str
    downstream_profile_name: str
    upload_profile_id: int | None = None
    download_profile_id: int | None = None
    upstream_kbps: int | None = None
    downstream_kbps: int | None = None
    technology: str = "GPON"
    source: str = "manual"
    is_active: bool = True
    notes: str | None = None


class SpeedProfileUpdate(BaseModel):
    vendor: str | None = None
    model: str | None = None
    firmware: str | None = None
    name: str | None = None
    profile_code: str | None = None
    upstream_profile_name: str | None = None
    downstream_profile_name: str | None = None
    upload_profile_id: int | None = None
    download_profile_id: int | None = None
    upstream_kbps: int | None = None
    downstream_kbps: int | None = None
    technology: str | None = None
    is_active: bool | None = None
    notes: str | None = None


class SpeedProfileRead(SpeedProfileCreate):
    id: int
    olt_code: str | None = None
    olt_name: str | None = None
    olt_environment: str | None = None
    olt_code_snapshot: str | None = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class NapPortCreate(BaseModel):
    olt_id: int | None = None
    olt_code_snapshot: str | None = None
    nap_id: int
    port_number: int
    label: str | None = None
    status: str = "free"
    onu_id: int | None = None
    customer_name_snapshot: str | None = None
    notes: str | None = None


class NapPortUpdate(BaseModel):
    label: str | None = None
    status: str | None = None
    onu_id: int | None = None
    customer_name_snapshot: str | None = None
    notes: str | None = None


class NapPortRead(NapPortCreate):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ProfileCatalogCreate(BaseModel):
    olt_id: int
    vendor: str = "ZTE"
    model: str = "C300"
    firmware: str = "V1.2.5P3"
    direction: str
    profile_kind: str
    name: str
    service_type: str = "internet"
    speed_kbps: int | None = None
    is_default: bool = False
    type_value: int | None = None
    fixed_kbps: int | None = None
    assured_kbps: int | None = None
    maximum_kbps: int | None = None
    sir_kbps: int | None = None
    pir_kbps: int | None = None
    source: str = "manual"
    is_active: bool = True
    notes: str | None = None


class ProfileCatalogUpdate(BaseModel):
    vendor: str | None = None
    model: str | None = None
    firmware: str | None = None
    direction: str | None = None
    profile_kind: str | None = None
    name: str | None = None
    service_type: str | None = None
    speed_kbps: int | None = None
    is_default: bool | None = None
    type_value: int | None = None
    fixed_kbps: int | None = None
    assured_kbps: int | None = None
    maximum_kbps: int | None = None
    sir_kbps: int | None = None
    pir_kbps: int | None = None
    is_active: bool | None = None
    notes: str | None = None


class ProfileCatalogRead(ProfileCatalogCreate):
    id: int
    olt_code: str | None = None
    olt_name: str | None = None
    olt_environment: str | None = None
    olt_code_snapshot: str | None = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ProfileCatalogReadWithUsage(ProfileCatalogRead):
    onu_count: int = 0


class OltCardRead(BaseModel):
    id: int
    olt_id: int
    slot_number: str
    card_type: str | None = None
    real_type: str | None = None
    port_count: int | None = None
    firmware: str | None = None
    status: str
    role: str | None = None
    last_seen_at: datetime | None = None
    last_sync_at: datetime | None = None
    sync_source: str | None = None
    model_config = ConfigDict(from_attributes=True)


class OltUplinkRead(BaseModel):
    id: int
    olt_id: int
    interface_name: str
    description: str | None = None
    interface_type: str | None = None
    admin_status: str
    oper_status: str
    line_protocol: str = "unknown"
    negotiation: str | None = None
    speed_kbps: int | None = None
    mtu: int | None = None
    mode: str | None = None
    allowed_vlans: str | None = None
    pvid_untag: int | None = None
    raw_output: str | None = None
    last_seen_at: datetime | None = None
    sync_source: str | None = None
    model_config = ConfigDict(from_attributes=True)


class OltTechnicalSettingsRead(BaseModel):
    id: int
    olt_id: int
    show_disabled_onus: bool
    send_onu_description_to_olt: bool
    dhcp_option82_enabled: bool
    pppoe_plus_enabled: bool
    dhcp_snooping_enabled: bool
    ip_source_protection_enabled: bool
    max_mac_per_onu: int
    rx_warning_dbm: float
    rx_critical_dbm: float
    temperature_warning_c: float
    temperature_critical_c: float
    model_config = ConfigDict(from_attributes=True)


class PonPortTechnicalRead(PonPortRead):
    pon_type: str = "GPON"
    admin_status: str = "unknown"
    oper_status: str = "unknown"
    tx_power: float | None = None
    range_label: str | None = None
    online_count: int = 0
    offline_count: int = 0
    total_count: int = 0
    occupancy_percent: float = 0
    last_sync_at: datetime | None = None
    sync_source: str | None = None
    online_onus: int = 0
    total_onus: int = 0
    load_percent: float = 0
    avg_rx_power: float | None = None


class VlanTechnicalRead(VlanRead):
    onu_count: int = 0
    used_iptv: bool = False
    used_management_voip: bool = False
    dhcp_snooping: bool = False
    lan_to_lan: bool = False


class ProvisioningTemplateCreate(BaseModel):
    vendor: str = "ZTE"
    model: str = "C300"
    firmware: str | None = "V1.2.5P3"
    template_name: str
    template_body: str
    is_default: bool = False
    is_active: bool = True
    description: str | None = None


class ProvisioningTemplateUpdate(BaseModel):
    vendor: str | None = None
    model: str | None = None
    firmware: str | None = None
    template_name: str | None = None
    template_body: str | None = None
    is_default: bool | None = None
    is_active: bool | None = None
    description: str | None = None


class ProvisioningTemplateRead(ProvisioningTemplateCreate):
    id: int
    name: str
    commands: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class OnuServiceModeTemplateCreate(BaseModel):
    olt_id: int
    vendor: str = "ZTE"
    model: str = "C300"
    firmware: str = "V1.2.5P3"
    mode_code: str
    name: str
    description: str | None = None
    vlan_mode: str
    dhcp_source: str
    use_iphost: bool = False
    use_veip: bool = True
    use_vlan_filter: bool = False
    use_loop_detect: bool = False
    disable_wifi: bool = False
    default_for_provisioning: bool = False
    template_body: str
    source: str = "manual"
    is_active: bool = True


class OnuServiceModeTemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    vlan_mode: str | None = None
    dhcp_source: str | None = None
    use_iphost: bool | None = None
    use_veip: bool | None = None
    use_vlan_filter: bool | None = None
    use_loop_detect: bool | None = None
    disable_wifi: bool | None = None
    default_for_provisioning: bool | None = None
    template_body: str | None = None
    is_active: bool | None = None


class OnuServiceModeTemplateRead(OnuServiceModeTemplateCreate):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class OnuBehaviorRead(BaseModel):
    """Bloque de solo lectura para describir el comportamiento ONU efectivo.

    No se persiste en base de datos; se deriva a partir de Onu + catálogos
    (OnuServiceModeTemplate, Vlan, SpeedProfile) y se adjunta en el detalle
    de la ONU.

    Fase P3 – Ficha Operacional ONU:
    - Expone `service_mode_code` y un modo simple normalizado
      (`router` / `bridge` / `transparent` / `unknown`).
    - Proyecta la plantilla (`template_name` / `mode_code`) y flags
      de comportamiento (DHCP, IPHost, VEIP, VLAN filter, loop detect,
      WiFi).
    - Incluye un resumen de calidad documental (`data_quality_status`
      y `data_quality_missing_fields`).
    """

    # Identidad del modo
    service_mode_code: str | None = None
    mode_simple: str
    mode_label: str
    # Plantilla de comportamiento ONU por OLT
    template_name: str | None = None
    mode_code: str | None = None

    # WAN / perfiles
    vlan_id: int
    vlan_name: str | None = None
    speed_profile_up: str | None = None
    speed_profile_down: str | None = None
    speed_profile_code: str | None = None

    # Comportamiento operativo
    dhcp_source: str | None = None
    use_iphost: bool = False
    use_veip: bool = False
    use_vlan_filter: bool = False
    use_loop_detect: bool = False
    disable_wifi: bool = False

    # Calidad documental
    data_quality_status: str | None = None
    data_quality_missing_fields: list[str] = []

    # Advertencias suaves (por ejemplo, plantilla ausente)
    warnings: list[str] = []


class OnuSchema(BaseModel):
    olt_id: int
    olt_code_snapshot: str | None = None
    pon_port_id: int | None = None
    zone_id: int | None = None
    nap_id: int | None = None
    customer_name: str
    customer_reference: str | None = None
    external_customer_id: str | None = None
    serial_number: str
    onu_interface: str
    onu_type: str
    vlan: int
    speed_profile: str
    speed_profile_up: str | None = None
    speed_profile_down: str | None = None
    rx_power: float | None = None
    tx_power: float | None = None
    signal_status: str | None = None
    last_monitored_at: datetime | None = None
    nap_port: int | None = None
    distance_m: int | None = None
    status: str = "unknown"
    last_down_cause: str | None = None
    imported_from_config: bool = False
    auth_date: datetime | None = None
    raw_description: str | None = None
    parsed_zone_name: str | None = None
    parsed_nap_name: str | None = None
    parsed_nap_port: int | None = None
    parsed_odn: str | None = None
    description_original: str | None = None
    description_generated: str | None = None
    zone_name: str | None = None
    address_reference: str | None = None
    nap_name: str | None = None
    nap_port_label: str | None = None
    odb_name: str | None = None
    external_id: str | None = None
    description_parse_status: str | None = None
    description_parse_warnings: list[str] | str | None = None
    technician_notes: str | None = None
    service_mode_code: str | None = None
    source: str = "manual"
    import_source: str = "manual"


class OnuRead(OnuSchema):
    id: int
    olt_code: str | None = None
    olt_name: str | None = None
    olt_display_name: str | None = None
    olt_environment: str | None = None
    behavior: OnuBehaviorRead | None = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class OnuDataQualityRead(BaseModel):
    id: int
    olt_id: int
    serial_number: str
    customer_name: str
    zone_name: str | None = None
    nap_name: str | None = None
    nap_port: int | None = None
    data_quality_status: str | None = None
    missing_fields: list[str] = []


class OnuOperationalSanitySummary(BaseModel):
    """Resumen agregado del saneamiento operacional de ONUs históricas.

    Se utiliza en modo auditoría para cuantificar cuántas ONUs podrían
    beneficiarse de una corrección documental/operacional sin aplicar
    cambios automáticamente.
    """

    total_onus: int
    candidate_service_mode_updates: int
    candidate_zone_updates: int
    candidate_nap_updates: int
    candidate_auth_date_updates: int
    ambiguous_cases: int


class OnuOperationalSanityChange(BaseModel):
    """Cambio propuesto para una ONU en modo auditoría (no aplicado).

    Describe diferencias entre el estado actual y los valores sugeridos
    a partir de snapshots `pon-onu-mng` y del parser de descripciones.
    """

    onu_id: int
    olt_id: int
    olt_code: str | None = None
    onu_interface: str
    serial_number: str

    current_service_mode_code: str | None = None
    suggested_service_mode_code: str | None = None

    current_zone_name: str | None = None
    suggested_zone_name: str | None = None

    current_nap_name: str | None = None
    suggested_nap_name: str | None = None

    current_auth_date: datetime | None = None
    suggested_auth_date: datetime | None = None

    # Razones de la sugerencia (ej: service_mode_from_snapshot, zone_from_description).
    reasons: list[str] = []


class OnuOperationalSanityPreview(BaseModel):
    """Respuesta completa del modo auditoría de saneamiento ONU."""

    summary: OnuOperationalSanitySummary
    changes: list[OnuOperationalSanityChange] = []


class OnuInternalInfoUpdate(BaseModel):
    zone_id: int | None = None
    nap_id: int | None = None
    nap_port: int | None = None
    zone_name: str | None = None
    nap_name: str | None = None
    nap_port_label: str | None = None
    address_reference: str | None = None
    odb_name: str | None = None
    external_id: str | None = None
    auth_date: datetime | None = None
    technician_notes: str | None = None


class ZoneReconstructionOltSummary(BaseModel):
    """Resumen por OLT de la preview de reconstrucción de Zones (P4.1).

    Todos los campos son de solo lectura y se calculan a partir de las ONUs
    y las Zones existentes, sin aplicar cambios en BD.
    """

    olt_id: int
    olt_code: str
    olt_name: str

    total_onus: int

    # Listas de nombres de zonas existentes/propuestas (por nombre lógico).
    zones_existing: list[str] = []
    zones_missing_proposed: list[str] = []

    # Conteos de ONUs por categoría.
    onus_with_correct_zone: int
    onus_with_cross_olt_zone: int
    onus_without_zone: int
    onus_reassignable: int
    onus_blocked: int


class ZoneReconstructionOnuProposal(BaseModel):
    """Fila de matriz ONU actual vs propuesta para Zones por OLT (P4.1).

    Describe el estado territorial actual de la ONU y la propuesta de Zone
    por OLT con un nivel de confianza y razones documentales.
    """

    onu_id: int
    olt_id: int
    olt_code: str | None = None

    interface: str
    serial: str
    customer_name: str

    current_zone_id: int | None = None
    current_zone_name: str | None = None
    current_zone_olt_id: int | None = None
    current_zone_olt_code: str | None = None
    current_zone_olt_name: str | None = None

    proposed_zone_name: str | None = None
    proposed_zone_olt_id: int | None = None
    proposed_zone_olt_code: str | None = None
    proposed_zone_olt_name: str | None = None

    # Nivel de confianza de la propuesta territorial para esta ONU.
    # Valores esperados: "ALTA" | "MEDIA" | "BAJA" | "BLOQUEADO".
    confidence: str

    # Razones textuales (ej. from_parsed_zone_name, from_description_structured,
    # conflict_parsed_vs_description, no_zone_evidence, cross_olt_zone_detected).
    reasons: list[str] = []


class ZoneReconstructionPreview(BaseModel):
    """Resultado completo de la auditoría de preview de Zones por OLT (P4.1).

    - ``summaries``: resumen agregado por OLT.
    - ``catalog_proposals``: catálogo consolidado propuesto por OLT/zona.
    - ``onus``: matriz detallada ONU actual vs propuesta.
    """
    summaries: list[ZoneReconstructionOltSummary]
    catalog_proposals: list["ZoneReconstructionCatalogProposal"] = []
    onus: list[ZoneReconstructionOnuProposal] = []


class ZoneReconstructionCatalogProposal(BaseModel):
    """Entrada de catálogo consolidado de Zones propuestas por OLT.

    Se deriva agrupando ONUs por (olt_id, proposed_zone_name) y
    cuantificando evidencia y confianza para cada zona candidata.
    """

    olt_id: int
    olt_code: str
    olt_name: str

    proposed_zone_name: str

    # Estado actual en el catálogo territorial de esa OLT.
    exists_in_olt: bool
    existing_zone_id: int | None = None

    # Número de ONUs que respaldan esta propuesta en esa OLT.
    onu_count: int

    # Nivel de confianza agregado para la zona (`ALTA`/`MEDIA`/`BAJA`/`BLOQUEADO`).
    confidence: str

    # Razones agregadas (ej.: zone_missing_in_olt, zone_exists_in_olt,
    # from_parsed_zone_name, from_zone_name_field, affected_by_cross_olt_zone).
    reasons: list[str] = []

    # Campos de origen que aportan evidencia (parsed_zone_name, zone_name).
    source_fields: list[str] = []
    onus: list[ZoneReconstructionOnuProposal] = []


class NapReconstructionCatalogProposal(BaseModel):
    """Entrada consolidada de catálogo NAP/ODN/ODB propuesta por OLT.

    Se utiliza en P4.3 para agrupar evidencia por (OLT, zona, tipo de
    objeto territorial y nombre canónico) sin modificar la BD.
    """

    olt_id: int
    olt_code: str
    olt_name: str

    proposed_zone_name: str | None = None
    object_type: str
    canonical_name: str
    display_name: str
    code: str
    notes: str | None = None

    exists_in_olt: bool
    existing_nap_id: int | None = None

    onu_count: int

    identity_score: int
    evidence_score: int
    state: str
    confidence: str

    reasons: list[str] = []
    source_fields: list[str] = []
    supporting_onu_ids: list[int] = []


class NapReconstructionOnuProposal(BaseModel):
    """Fila ONU actual vs propuesta para NAP/ODN/ODB (P4.3).

    Describe cómo quedaría la ONU respecto a NAP/ODN/ODB propuestos
    para su misma OLT, sin aplicar cambios.
    """

    onu_id: int
    olt_id: int
    olt_code: str | None = None

    interface: str
    serial: str
    customer_name: str

    current_nap_id: int | None = None
    current_nap_name: str | None = None
    current_nap_olt_id: int | None = None
    current_nap_olt_code: str | None = None

    parsed_nap_name: str | None = None
    parsed_odn: str | None = None
    odb_name: str | None = None

    proposed_zone_name: str | None = None
    proposed_object_type: str | None = None
    proposed_canonical_name: str | None = None
    proposed_olt_id: int | None = None

    state: str
    confidence: str
    identity_score: int
    evidence_score: int
    reasons: list[str] = []


class NapReconstructionOltSummary(BaseModel):
    """Resumen por OLT de la preview de reconstrucción NAP/ODN/ODB (P4.3)."""

    olt_id: int
    olt_code: str
    olt_name: str

    total_onus: int

    existing_naps: list[str] = []
    proposed_catalog_count: int
    proposed_new_count: int
    proposed_exists_count: int
    proposed_review_count: int
    proposed_blocked_count: int

    onus_with_nap_id: int
    onus_with_cross_olt_nap: int
    onus_without_nap_id: int
    onus_reassignable: int
    onus_blocked: int


class NapReconstructionPreview(BaseModel):
    """Resultado completo de la preview de reconstrucción NAP/ODN/ODB (P4.3).

    - ``summaries``: resumen agregado por OLT.
    - ``catalog_proposals``: catálogo consolidado propuesto por OLT/zona/tipo.
    - ``onus``: matriz detallada ONU actual vs propuesta.
    """

    summaries: list[NapReconstructionOltSummary]
    catalog_proposals: list[NapReconstructionCatalogProposal] = []
    onus: list[NapReconstructionOnuProposal] = []


class TerritorialAuditOltSummary(BaseModel):
    """Resumen consolidado de auditoría territorial por OLT (P4.5).

    Agrega en una sola vista los indicadores clave de Zones y NAP/ODN/ODB
    reutilizando los previews existentes, sin modificar la base de datos.
    """

    olt_id: int
    olt_code: str
    olt_name: str

    total_onus: int

    zones_existing_count: int
    zones_missing_count: int
    zones_reassignable_onus: int
    zones_blocked_onus: int

    naps_existing_count: int
    naps_proposed_count: int
    naps_new_count: int
    naps_exists_count: int
    naps_review_count: int
    naps_blocked_count: int

    onus_with_cross_olt_zone: int
    onus_with_cross_olt_nap: int

    territorial_health_score: int
    status: str


class TerritorialAuditStateSummary(BaseModel):
    """Resumen por estado de candidatos territoriales.

    Se usa tanto para Zones como para NAP/ODN/ODB.
    """

    new_count: int = 0
    exists_count: int = 0
    review_count: int = 0
    blocked_count: int = 0
    merge_count: int = 0


class TerritorialAuditConfidenceSummary(BaseModel):
    """Resumen por nivel de confianza agregado (ALTA/MEDIA/BAJA/BLOQUEADO)."""

    alta_count: int = 0
    media_count: int = 0
    baja_count: int = 0
    bloqueado_count: int = 0


class TerritorialAuditIssue(BaseModel):
    """Issue crítico o relevante detectado por el Centro de Auditoría."""

    issue_type: str
    severity: str

    olt_id: int | None = None
    olt_code: str | None = None

    entity_type: str
    entity_name: str | None = None

    affected_onu_count: int | None = None

    message: str
    recommendation: str | None = None


class TerritorialAuditCenter(BaseModel):
    """Vista consolidada del Centro de Auditoría Territorial (P4.5).

    Read-only, construida a partir de los previews de Zones y NAP/ODN/ODB.
    """

    generated_at: datetime

    olt_summaries: list[TerritorialAuditOltSummary] = []
    zone_state_summary: TerritorialAuditStateSummary
    nap_state_summary: TerritorialAuditStateSummary
    confidence_summary: TerritorialAuditConfidenceSummary

    critical_issues: list[TerritorialAuditIssue] = []
    recommendations: list[str] = []


class PowerSampleCreate(BaseModel):
    onu_id: int
    rx_power: float
    tx_power: float


class PowerSampleRead(PowerSampleCreate):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class OnuEventRead(BaseModel):
    id: int
    onu_id: int | None
    olt_id: int
    onu_interface: str
    event_type: str
    description: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class EventRead(BaseModel):
    id: int
    event_type: str
    entity_type: str
    entity_id: int | None
    description: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class DriverCommandLogRead(BaseModel):
    id: int
    olt_id: int | None = None
    olt_code: str | None = None
    olt_name: str | None = None
    olt_environment: str | None = None
    command: str
    success: bool
    read_only: bool
    duration_ms: int | None
    error_message: str | None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class DashboardSummary(BaseModel):
    online: int
    offline: int
    unauthorized: int
    low_signal: int
    los: int
    dying_gasp: int
    pwr_fail: int
    rx_warning: int
    rx_critical: int
    unauthorized_pending: int = 0
    unauthorized_ignored: int = 0
    unauthorized_ready_for_provisioning: int = 0
    provisioning_draft: int = 0
    provisioning_validated: int = 0
    provisioning_approved: int = 0
    provisioning_validation_failed: int = 0
    provisioning_cancelled: int = 0
    last_sync_onus: "MonitoringExecutionRead | None" = None
    last_sync_power: "MonitoringExecutionRead | None" = None


class DashboardEnvironmentStats(BaseModel):
    environment: str
    olts: int
    onus: int
    online: int


class DashboardEnvironmentSummary(BaseModel):
    production: DashboardEnvironmentStats
    lab: DashboardEnvironmentStats


class TelnetTestResult(BaseModel):
    healthy: bool
    prompt_modes: list[str]
    version_raw: str
    cards: list[dict]


class TelnetDebugResult(BaseModel):
    raw_banner: str
    bytes_received: int
    timeout: bool


class OltSyncResult(BaseModel):
    olt_id: int
    cli_onus: int
    matched_onus: int
    updated_status: int
    power_samples: int
    events: int
    unauthorized: int
    total_processed: int = 0
    working: int = 0
    offline: int = 0
    los: int = 0
    dying_gasp: int = 0
    duration_ms: int = 0


class OltPowerSyncResult(BaseModel):
    olt_id: int
    working_onus: int
    power_samples: int
    rx_warning: int
    rx_critical: int
    commands: int
    processed: int = 0
    success: int = 0
    failed: int = 0
    duration_ms: int = 0
    errors: list[dict] = []
    onu_results: list[dict] = []


class UnauthorizedOnuRead(BaseModel):
    id: int
    olt_id: int
    olt_code: str | None = None
    olt_name: str | None = None
    olt_environment: str | None = None
    olt_code_snapshot: str | None = None
    pon_type: str | None = None
    slot: int | None = None
    port: int | None = None
    pon_port_interface: str | None = None
    serial_number: str
    detected_type: str | None = None
    detected_vendor: str | None = None
    suggested_service_mode_code: str | None = None
    raw_output: str | None = None
    status: str
    first_seen_at: datetime
    last_seen_at: datetime
    times_detected: int
    notes: str | None = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class UnauthorizedOnuDiscoveryResult(BaseModel):
    detected: int
    new: int
    existing: int
    ignored: int
    duration_ms: int


class UnauthorizedOnuEventRead(BaseModel):
    id: int
    unauthorized_onu_id: int
    event_type: str
    description: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


PROVISIONING_STATUSES = {"draft", "validated", "validation_failed", "approved", "preflight_passed", "preflight_failed", "executed", "cancelled"}


class ProvisioningPlanCreate(BaseModel):
    unauthorized_onu_id: int
    customer_name: str
    customer_reference: str | None = None
    onu_name: str | None = None
    onu_description: str | None = None
    description_original: str | None = None
    description_generated: str | None = None
    zone_name: str | None = None
    address_reference: str | None = None
    nap_name: str | None = None
    nap_port_label: str | None = None
    odb_name: str | None = None
    external_id: str | None = None
    auth_date: datetime | None = None
    description_parse_status: str | None = None
    description_parse_warnings: list[str] | str | None = None
    technical_comment: str | None = None
    address: str | None = None
    notes: str | None = None
    zone_id: int
    nap_id: int
    nap_port: int | None = Field(default=None, ge=1)
    onu_type: str
    vlan: int = Field(ge=1)
    speed_profile_up: str = ""
    speed_profile_down: str = ""
    speed_profile_id: int | None = None
    upload_profile_id: int = Field(ge=1)
    download_profile_id: int = Field(ge=1)
    selected_onu_id: int | None = Field(default=None, ge=1)
    allow_manual_onu_id: bool = False
    onu_mode: str = "router"
    vlan_lan_mode: str = "tag"
    ethernet_port: str = "eth_0/1"
    dhcp_mode: str = "from-internet"
    service_mode_code: str

    @field_validator("customer_name", "onu_type")
    @classmethod
    def required_text(cls, value: str) -> str:
        normalized = (value or "").strip()
        if not normalized:
            raise ValueError("field is required")
        return normalized


class ProvisioningPlanRead(BaseModel):
    id: int
    olt_id: int
    olt_code: str | None = None
    unauthorized_onu_id: int
    serial_number: str
    pon_port_interface: str | None = None
    customer_name: str
    customer_reference: str | None = None
    onu_name: str | None = None
    onu_description: str | None = None
    description_original: str | None = None
    description_generated: str | None = None
    zone_name: str | None = None
    address_reference: str | None = None
    nap_name: str | None = None
    nap_port_label: str | None = None
    odb_name: str | None = None
    external_id: str | None = None
    description_parse_status: str | None = None
    description_parse_warnings: list[str] | str | None = None
    onu_mode: str = "router"
    vlan_lan_mode: str = "tag"
    ethernet_port: str = "eth_0/1"
    dhcp_mode: str = "from-internet"
    allow_manual_onu_id: bool = False
    service_mode_template_id: int | None = None
    service_mode_code: str = "bridge_tag_internet"
    technical_comment: str | None = None
    address: str | None = None
    notes: str | None = None
    zone_id: int
    nap_id: int
    nap_port: int | None = None
    onu_type: str
    vlan: int
    speed_profile_up: str
    speed_profile_down: str
    speed_profile_id: int | None = None
    upload_profile_id: int | None = None
    download_profile_id: int | None = None
    selected_onu_id: int | None = None
    suggested_onu_id: int | None = None
    generated_cli: str | None = None
    validation_warnings: list[str] = []
    validation_errors: list[str] = []
    validation_result: "ProvisioningValidationResultRead | None" = None
    validated_at: datetime | None = None
    status: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ProvisioningPlanValidationResponse(BaseModel):
    plan: ProvisioningPlanRead
    warnings: list[str]
    errors: list[str]
    is_valid: bool = False
    suggested_onu_id: int | None = None
    cli_preview: str | None = None


class ProvisioningPlanCounts(BaseModel):
    draft: int = 0
    validated: int = 0
    validation_failed: int = 0
    approved: int = 0
    preflight_passed: int = 0
    preflight_failed: int = 0
    executed: int = 0
    cancelled: int = 0


class ProvisioningValidationResultRead(BaseModel):
    id: int | None = None
    provisioning_plan_id: int
    is_valid: bool
    warnings: list[str]
    errors: list[str]
    suggested_onu_id: int | None = None
    selected_onu_id: int | None = None
    occupied_onu_ids: list[int] = []
    cli_preview: str | None = None
    preflight_checks: dict = {}
    validated_at: datetime


class ProvisioningPreflightResponse(BaseModel):
    plan: ProvisioningPlanRead
    is_valid: bool
    checks: dict
    warnings: list[str]
    errors: list[str]


class MonitoringExecutionRead(BaseModel):
    id: int
    olt_id: int
    olt_code: str | None = None
    olt_name: str | None = None
    olt_environment: str | None = None
    task_type: str
    started_at: datetime
    finished_at: datetime | None
    duration_ms: int | None
    processed_count: int
    success_count: int
    error_count: int
    details_json: str | None = None
    model_config = ConfigDict(from_attributes=True)


class MonitoringLatestResponse(BaseModel):
    sync_onus: MonitoringExecutionRead | None = None
    sync_power: MonitoringExecutionRead | None = None


class AlertsResponse(BaseModel):
    offline: list[OnuRead]
    los: list[OnuRead]
    dying_gasp: list[OnuRead]
    rx_warning: list[OnuRead]
    rx_critical: list[OnuRead]


class ImportPreviewTextRequest(BaseModel):
    raw_config: str


class ImportPreviewResponse(BaseModel):
    import_job_id: int
    snapshot_id: int
    vlans: int
    tcont_profiles: int
    traffic_profiles: int
    gpon_profiles: int
    onu_types: int
    pon_ports: int
    uplinks: int = 0
    onus: int
    onu_management_modes: int = 0
    zones_detected: list[str]
    naps_detected: list[str]
    warnings: list[str]
    legacy_incomplete: list[str] = Field(default_factory=list)
    critical_errors: list[str] = Field(default_factory=list)


class ImportConfirmResponse(BaseModel):
    import_job_id: int
    status: str
    vlans_upserted: int
    gpon_profiles_upserted: int
    onu_types_upserted: int
    pon_ports_upserted: int
    uplinks_upserted: int = 0
    onus_upserted: int
    zones_upserted: int
    naps_upserted: int
    warnings: list[str]


class ImportJobRead(BaseModel):
    id: int
    olt_id: int
    status: str
    source: str
    raw_config_snapshot_id: int
    parsed_summary: dict
    snapshot_status: str | None = None
    snapshot_warnings: list[str] | None = None
    created_at: datetime
    updated_at: datetime | None = None
    confirmed_at: datetime | None = None
