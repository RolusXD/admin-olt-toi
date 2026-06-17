export type Olt = {
  id: number;
  olt_code: string;
  name: string;
  display_name?: string | null;
  environment: "production" | "lab" | string;
  vendor: string;
  model: string;
  firmware: string;
  ip_address: string;
  telnet_port: number;
  username: string;
  connection_type: string;
  status: string;
  has_password: boolean;
  initial_import_status: "pending" | "preview_created" | "confirmed" | "failed" | string;
  last_import_job_id?: number | null;
  last_import_confirmed_at?: string | null;
};

export type OltInventorySummary = {
  olt_id: number;
  olt_code: string;
  olt_name: string;
  environment: string;
  initial_import_status: string;
  last_import_confirmed_at?: string | null;
  onus: number;
  pon_ports: number;
  vlans: number;
  profiles: number;
  last_confirmed_import?: string | null;
};

export type Zone = {
  id: number;
  name: string;
  code?: string | null;
  description?: string | null;
  is_active?: boolean;
  source?: string;
  notes?: string | null;
};

export type Nap = {
  id: number;
  zone_id: number;
  name: string;
  code?: string | null;
  nap_type?: string;
  capacity: number;
  latitude?: number | null;
  longitude?: number | null;
  address_reference?: string | null;
  description?: string | null;
  is_active?: boolean;
  source?: string;
  notes?: string | null;
};

export type Vlan = {
  id: number;
  olt_id: number;
  olt_code?: string | null;
  olt_name?: string | null;
  olt_environment?: string | null;
  olt_code_snapshot?: string | null;
  vlan_id: number;
  name?: string | null;
  description?: string | null;
  service_type?: string;
  is_active?: boolean;
  source?: string;
  notes?: string | null;
};

export type OnuType = {
  id: number;
  olt_id: number;
  olt_code?: string | null;
  olt_name?: string | null;
  olt_environment?: string | null;
  olt_code_snapshot?: string | null;
  vendor: string;
  model: string;
  firmware: string;
  name: string;
  vendor_detected?: string | null;
  model_detected?: string | null;
  technology: string;
  max_tcont?: number | null;
  max_gemport?: number | null;
  max_ports?: number | null;
  max_switch_perslot?: number | null;
  max_flow_perswitch?: number | null;
  max_iphost?: number | null;
  ethernet_ports?: number | null;
  wifi_ports?: number | null;
  pots_ports?: number | null;
  rf_ports?: number | null;
  is_active: boolean;
  source: string;
  notes?: string | null;
};

export type SpeedProfile = {
  id: number;
  olt_id: number;
  olt_code?: string | null;
  olt_name?: string | null;
  olt_environment?: string | null;
  olt_code_snapshot?: string | null;
  vendor: string;
  model: string;
  firmware: string;
  name: string;
  profile_code: string;
  upstream_profile_name: string;
  downstream_profile_name: string;
  upload_profile_id?: number | null;
  download_profile_id?: number | null;
  upstream_kbps?: number | null;
  downstream_kbps?: number | null;
  technology: string;
  source: string;
  is_active: boolean;
  notes?: string | null;
  created_at: string;
  updated_at: string;
};

export type ProfileCatalog = {
  id: number;
  olt_id: number;
  olt_code?: string | null;
  olt_name?: string | null;
  olt_environment?: string | null;
  olt_code_snapshot?: string | null;
  vendor: string;
  model: string;
  firmware: string;
  direction: "upload" | "download" | string;
  profile_kind: "tcont" | "traffic" | string;
  name: string;
  type_value?: number | null;
  fixed_kbps?: number | null;
  assured_kbps?: number | null;
  maximum_kbps?: number | null;
  sir_kbps?: number | null;
  pir_kbps?: number | null;
  source: string;
  is_active: boolean;
  notes?: string | null;
  created_at: string;
  updated_at: string;
};

export type NapPort = {
  id: number;
  nap_id: number;
  port_number: number;
  label?: string | null;
  status: string;
  onu_id?: number | null;
  customer_name_snapshot?: string | null;
  notes?: string | null;
  created_at: string;
  updated_at: string;
};

export type ProvisioningTemplate = {
  id: number;
  name: string;
  vendor: string;
  model: string;
  firmware?: string | null;
  template_name: string;
  template_body: string;
  commands: string;
  is_default: boolean;
  is_active: boolean;
  description?: string | null;
  created_at: string;
  updated_at: string;
};

export type PonPort = {
  id: number;
  olt_id: number;
  olt_code?: string | null;
  olt_name?: string | null;
  olt_environment?: string | null;
  rack?: number | null;
  shelf?: number | null;
  slot: number;
  port: number;
  interface_name?: string | null;
  description?: string | null;
};

export type Onu = {
  id: number;
  olt_id: number;
  olt_code?: string | null;
  olt_name?: string | null;
  olt_display_name?: string | null;
  olt_environment?: string | null;
  olt_code_snapshot?: string | null;
  pon_port_id?: number | null;
  zone_id?: number | null;
  nap_id?: number | null;
  customer_name: string;
  customer_reference?: string | null;
  external_customer_id?: string | null;
  serial_number: string;
  onu_interface: string;
  onu_type: string;
  vlan: number;
  speed_profile: string;
  speed_profile_up?: string | null;
  speed_profile_down?: string | null;
  rx_power?: number | null;
  tx_power?: number | null;
  signal_status?: "normal" | "warning" | "critical" | string | null;
  last_monitored_at?: string | null;
  status: string;
  last_down_cause?: string | null;
  distance_m?: number | null;
  nap_port?: number | null;
  import_source?: string | null;
};

export type PowerSample = {
  id: number;
  onu_id: number;
  rx_power: number;
  tx_power: number;
  created_at: string;
};

export type OnuEvent = {
  id: number;
  onu_id?: number | null;
  olt_id: number;
  onu_interface: string;
  event_type: string;
  description: string;
  created_at: string;
};

export type Alerts = {
  offline: Onu[];
  los: Onu[];
  dying_gasp: Onu[];
  rx_warning: Onu[];
  rx_critical: Onu[];
};

export type UnauthorizedOnu = {
  id: number;
  olt_id: number;
  olt_code?: string | null;
  olt_name?: string | null;
  olt_environment?: string | null;
  olt_code_snapshot?: string | null;
  pon_type?: string | null;
  slot?: number | null;
  port?: number | null;
  pon_port_interface?: string | null;
  serial_number: string;
  detected_type?: string | null;
  detected_vendor?: string | null;
  raw_output?: string | null;
  status: "pending" | "ignored" | "ready_for_provisioning" | "provisioned" | string;
  first_seen_at: string;
  last_seen_at: string;
  times_detected: number;
  notes?: string | null;
  created_at: string;
  updated_at: string;
};

export type UnauthorizedOnuDiscoveryResult = {
  detected: number;
  new: number;
  existing: number;
  ignored: number;
  duration_ms: number;
};

export type ImportPreview = {
  import_job_id: number;
  snapshot_id: number;
  vlans: number;
  tcont_profiles: number;
  traffic_profiles: number;
  gpon_profiles: number;
  onu_types: number;
  pon_ports: number;
  onus: number;
  zones_detected: string[];
  naps_detected: string[];
  warnings: string[];
};

export type ImportConfirmResult = {
  import_job_id: number;
  status: string;
  vlans_upserted: number;
  gpon_profiles_upserted: number;
  onu_types_upserted: number;
  pon_ports_upserted: number;
  onus_upserted: number;
  zones_upserted: number;
  naps_upserted: number;
  warnings: string[];
};

export type ReadOnlyCheckResult = {
  olt_id: number;
  connection_success: boolean;
  firmware_detected?: string | null;
  cards: Array<Record<string, string | number | null>>;
  onu_counts: {
    total: number;
    working: number;
    offline: number;
    los: number;
    dying_gasp: number;
  };
  prompt_detected?: string | null;
  duration_ms: number;
  errors: Array<{ command?: string | null; error: string }>;
};

export type DriverCommandLog = {
  id: number;
  olt_id?: number | null;
  olt_code?: string | null;
  olt_name?: string | null;
  olt_environment?: string | null;
  command: string;
  success: boolean;
  read_only: boolean;
  duration_ms?: number | null;
  error_message?: string | null;
  created_at: string;
};

export type OltSyncResult = {
  olt_id: number;
  cli_onus: number;
  matched_onus: number;
  updated_status: number;
  power_samples: number;
  events: number;
  unauthorized: number;
  total_processed: number;
  working: number;
  offline: number;
  los: number;
  dying_gasp: number;
  duration_ms: number;
};

export type OltPowerSyncResult = {
  olt_id: number;
  working_onus: number;
  power_samples: number;
  rx_warning: number;
  rx_critical: number;
  commands: number;
  processed: number;
  success: number;
  failed: number;
  duration_ms: number;
  errors: Array<Record<string, string | number | boolean | null>>;
  onu_results: Array<Record<string, string | number | boolean | null>>;
};

export type MonitoringExecution = {
  id: number;
  olt_id: number;
  olt_code?: string | null;
  olt_name?: string | null;
  olt_environment?: string | null;
  task_type: "sync_onus" | "sync_power" | string;
  started_at: string;
  finished_at?: string | null;
  duration_ms?: number | null;
  processed_count: number;
  success_count: number;
  error_count: number;
  details_json?: string | null;
};

export type MonitoringLatest = {
  sync_onus?: MonitoringExecution | null;
  sync_power?: MonitoringExecution | null;
};

export type DashboardSummary = {
  online: number;
  offline: number;
  unauthorized: number;
  low_signal: number;
  los: number;
  dying_gasp: number;
  pwr_fail: number;
  rx_warning: number;
  rx_critical: number;
  unauthorized_pending: number;
  unauthorized_ignored: number;
  unauthorized_ready_for_provisioning: number;
  provisioning_draft: number;
  provisioning_validated: number;
  provisioning_approved: number;
  provisioning_validation_failed: number;
  provisioning_cancelled: number;
  last_sync_onus?: MonitoringExecution | null;
  last_sync_power?: MonitoringExecution | null;
};

export type ProvisioningPlan = {
  id: number;
  olt_id: number;
  olt_code?: string | null;
  unauthorized_onu_id: number;
  serial_number: string;
  pon_port_interface?: string | null;
  customer_name: string;
  customer_reference?: string | null;
  technical_comment?: string | null;
  address?: string | null;
  notes?: string | null;
  zone_id: number;
  nap_id: number;
  nap_port: number;
  onu_type: string;
  vlan: number;
  speed_profile_up: string;
  speed_profile_down: string;
  speed_profile_id?: number | null;
  upload_profile_id?: number | null;
  download_profile_id?: number | null;
  selected_onu_id?: number | null;
  suggested_onu_id?: number | null;
  generated_cli?: string | null;
  validation_warnings: string[];
  validation_errors: string[];
  validation_result?: ProvisioningValidationResult | null;
  validated_at?: string | null;
  status: "draft" | "validated" | "validation_failed" | "approved" | "executed" | "cancelled" | string;
  created_at: string;
  updated_at: string;
};

export type ProvisioningPlanValidation = {
  plan: ProvisioningPlan;
  warnings: string[];
  errors: string[];
  is_valid: boolean;
  suggested_onu_id?: number | null;
  cli_preview?: string | null;
};

export type ProvisioningValidationResult = {
  id?: number | null;
  provisioning_plan_id: number;
  is_valid: boolean;
  warnings: string[];
  errors: string[];
  suggested_onu_id?: number | null;
  selected_onu_id?: number | null;
  occupied_onu_ids: number[];
  cli_preview?: string | null;
  validated_at: string;
};

export type DashboardEnvironmentSummary = {
  production: {
    environment: string;
    olts: number;
    onus: number;
    online: number;
  };
  lab: {
    environment: string;
    olts: number;
    onus: number;
    online: number;
  };
};
