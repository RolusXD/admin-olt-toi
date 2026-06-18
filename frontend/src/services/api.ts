import type {
  Alerts,
  DashboardEnvironmentSummary,
  DashboardSummary,
  DriverCommandLog,
  ImportConfirmResult,
  ImportPreview,
  Nap,
  NapPort,
  Olt,
  OltCard,
  OltInventorySummary,
  OltPowerSyncResult,
  OltSyncResult,
  OltTechnicalSettings,
  OltUplink,
  MonitoringExecution,
  MonitoringLatest,
  Onu,
  OnuEvent,
  PonPort,
  PowerSample,
  ProfileCatalog,
  ProvisioningPlan,
  ProvisioningPlanValidation,
  ProvisioningTemplate,
  ProvisioningValidationResult,
  ReadOnlyCheckResult,
  OnuType,
  SpeedProfile,
  UnauthorizedOnu,
  UnauthorizedOnuDiscoveryResult,
  Vlan,
  Zone,
} from "@/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const isFormData = init?.body instanceof FormData;
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: isFormData
      ? init?.headers
      : {
          "Content-Type": "application/json",
          ...(init?.headers ?? {}),
        },
    cache: "no-store",
  });
  if (!response.ok) {
    let detail = "";
    try {
      const errorBody = await response.json();
      detail = typeof errorBody.detail === "string" ? errorBody.detail : "";
    } catch {
      detail = "";
    }
    throw new Error(detail || `API ${response.status}: ${response.statusText}`);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

function toQuery(params: Record<string, string | number | boolean | undefined | null>) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  });
  const query = search.toString();
  return query ? `?${query}` : "";
}

export const api = {
  summary: (params: { olt_id?: number | string; olt_code?: string; environment?: string } = {}) =>
    request<DashboardSummary>(`/dashboard/summary${toQuery(params)}`),
  environmentSummary: () => request<DashboardEnvironmentSummary>("/dashboard/environment-summary"),
  olts: (params: { environment?: string } = {}) => request<Olt[]>(`/olts${toQuery(params)}`),
  olt: (id: number | string) => request<Olt>(`/olts/${id}`),
  oltInventorySummary: (id: number | string) => request<OltInventorySummary>(`/olts/${id}/inventory-summary`),
  oltCards: (id: number | string) => request<OltCard[]>(`/olts/${id}/cards`),
  oltUplinks: (id: number | string) => request<OltUplink[]>(`/olts/${id}/uplinks`),
  oltAdvanced: (id: number | string) => request<OltTechnicalSettings>(`/olts/${id}/advanced`),
  oltPonPorts: (id: number | string) => request<PonPort[]>(`/olts/${id}/pon-ports`),
  oltVlans: (id: number | string) => request<Vlan[]>(`/olts/${id}/vlans`),
  zones: (params: Record<string, string | number | undefined | null> = {}) => request<Zone[]>(`/zones${toQuery(params)}`),
  naps: (params: Record<string, string | number | undefined | null> = {}) => request<Nap[]>(`/naps${toQuery(params)}`),
  napPorts: (params: Record<string, string | number | undefined | null> = {}) => request<NapPort[]>(`/nap-ports${toQuery(params)}`),
  vlans: (params: Record<string, string | number | undefined | null> = {}) => request<Vlan[]>(`/vlans${toQuery(params)}`),
  onuTypes: (params: Record<string, string | number | undefined | null> = {}) => request<OnuType[]>(`/onu-types${toQuery(params)}`),
  speedProfiles: (params: Record<string, string | number | undefined | null> = {}) =>
    request<SpeedProfile[]>(`/speed-profiles${toQuery(params)}`),
  profileCatalogs: (params: Record<string, string | number | boolean | undefined | null> = {}) =>
    request<ProfileCatalog[]>(`/profile-catalogs${toQuery(params)}`),
  provisioningTemplates: (params: Record<string, string | number | undefined | null> = {}) =>
    request<ProvisioningTemplate[]>(`/provisioning-templates${toQuery(params)}`),
  ponPorts: (params: { olt_id?: number | string; olt_code?: string } = {}) => request<PonPort[]>(`/pon-ports${toQuery(params)}`),
  onus: (params: Record<string, string | number | undefined | null> = {}) => request<Onu[]>(`/onus${toQuery(params)}`),
  onu: (id: number | string) => request<Onu>(`/onus/${id}`),
  onuPowerHistory: (id: number | string) => request<PowerSample[]>(`/onus/${id}/power-history`),
  onuEvents: (id: number | string) => request<OnuEvent[]>(`/onus/${id}/events`),
  alerts: (params: { olt_id?: number | string; olt_code?: string } = {}) => request<Alerts>(`/alerts${toQuery(params)}`),
  unauthorizedOnus: (params: Record<string, string | number | undefined | null> = {}) =>
    request<UnauthorizedOnu[]>(`/unauthorized-onus${toQuery(params)}`),
  discoverUnauthorizedOnus: (oltId: number) =>
    request<UnauthorizedOnuDiscoveryResult>(`/olts/${oltId}/discover-unauthorized-onus`, { method: "POST" }),
  ignoreUnauthorizedOnu: (id: number) => request<UnauthorizedOnu>(`/unauthorized-onus/${id}/ignore`, { method: "PUT" }),
  restoreUnauthorizedOnu: (id: number) => request<UnauthorizedOnu>(`/unauthorized-onus/${id}/restore`, { method: "PUT" }),
  readyUnauthorizedOnu: (id: number) => request<UnauthorizedOnu>(`/unauthorized-onus/${id}/ready`, { method: "PUT" }),
  readOnlyCheck: (oltId: number) => request<ReadOnlyCheckResult>(`/olts/${oltId}/read-only-check`, { method: "POST" }),
  commandLogs: (oltId: number, limit = 50) => request<DriverCommandLog[]>(`/olts/${oltId}/command-logs${toQuery({ limit })}`),
  monitoringExecutions: (params: Record<string, string | number | undefined | null> = {}) =>
    request<MonitoringExecution[]>(`/monitoring/executions${toQuery(params)}`),
  monitoringLatest: (params: { olt_id?: number | string; olt_code?: string } = {}) =>
    request<MonitoringLatest>(`/monitoring/latest${toQuery(params)}`),
  syncOnusReadOnly: (oltId: number) => request<OltSyncResult>(`/olts/${oltId}/sync-onus`, { method: "POST" }),
  syncPower: (oltId: number, options: { limit?: number | string; interfaces?: string[] }) =>
    request<OltPowerSyncResult>(`/olts/${oltId}/sync-power${toQuery({ limit: options.limit })}`, {
      method: "POST",
      body: options.interfaces?.length ? JSON.stringify(options.interfaces) : undefined,
    }),
  previewImportFromText: (oltId: number, rawConfig: string) =>
    request<ImportPreview>(`/olts/${oltId}/import/preview-from-text`, {
      method: "POST",
      body: JSON.stringify({ raw_config: rawConfig }),
    }),
  previewImportFromFile: (oltId: number, file: File) => {
    const formData = new FormData();
    formData.set("file", file);
    return request<ImportPreview>(`/olts/${oltId}/import/preview-from-file`, { method: "POST", body: formData });
  },
  previewImportFromTelnet: (oltId: number) =>
    request<ImportPreview>(`/olts/${oltId}/import/preview-from-telnet`, { method: "POST" }),
  confirmImport: (importJobId: number) =>
    request<ImportConfirmResult>(`/import-jobs/${importJobId}/confirm`, { method: "POST" }),
  createOlt: (payload: Record<string, unknown>) =>
    request<Olt>("/olts", { method: "POST", body: JSON.stringify(payload) }),
  updateOlt: (id: number | string, payload: Record<string, unknown>) =>
    request<Olt>(`/olts/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  createZone: (payload: Record<string, unknown>) =>
    request<Zone>("/zones", { method: "POST", body: JSON.stringify(payload) }),
  createNap: (payload: Record<string, unknown>) =>
    request<Nap>("/naps", { method: "POST", body: JSON.stringify(payload) }),
  createOnuType: (payload: Record<string, unknown>) =>
    request<OnuType>("/onu-types", { method: "POST", body: JSON.stringify(payload) }),
  updateOnuType: (id: number | string, payload: Record<string, unknown>) =>
    request<OnuType>(`/onu-types/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  createSpeedProfile: (payload: Record<string, unknown>) =>
    request<SpeedProfile>("/speed-profiles", { method: "POST", body: JSON.stringify(payload) }),
  createProfileCatalog: (payload: Record<string, unknown>) =>
    request<ProfileCatalog>("/profile-catalogs", { method: "POST", body: JSON.stringify(payload) }),
  createVlan: (payload: Record<string, unknown>) =>
    request<Vlan>("/vlans", { method: "POST", body: JSON.stringify(payload) }),
  createProvisioningTemplate: (payload: Record<string, unknown>) =>
    request<ProvisioningTemplate>("/provisioning-templates", { method: "POST", body: JSON.stringify(payload) }),
  createOnu: (payload: Record<string, unknown>) =>
    request<Onu>("/onus", { method: "POST", body: JSON.stringify(payload) }),
  provisioningPlans: (params: Record<string, string | number | undefined | null> = {}) =>
    request<ProvisioningPlan[]>(`/provisioning-plans${toQuery(params)}`),
  provisioningPlanById: (id: number | string) => request<ProvisioningPlan>(`/provisioning-plans/${id}`),
  createProvisioningPlan: (payload: Record<string, unknown>) =>
    request<ProvisioningPlan>("/provisioning-plans", { method: "POST", body: JSON.stringify(payload) }),
  validateProvisioningPlan: (id: number | string) =>
    request<ProvisioningPlanValidation>(`/provisioning-plans/${id}/validate`, { method: "PUT" }),
  revalidateProvisioningPlan: (id: number | string) =>
    request<ProvisioningPlanValidation>(`/provisioning-plans/${id}/revalidate`, { method: "PUT" }),
  provisioningValidationResult: (id: number | string) =>
    request<ProvisioningValidationResult>(`/provisioning-plans/${id}/validation-result`),
  approveProvisioningPlan: (id: number | string) =>
    request<ProvisioningPlan>(`/provisioning-plans/${id}/approve`, { method: "PUT" }),
  cancelProvisioningPlan: (id: number | string) =>
    request<ProvisioningPlan>(`/provisioning-plans/${id}/cancel`, { method: "PUT" }),
  unauthorized: () => request<Array<{ interface: string; serial_number: string; status: string }>>("/provisioning/unauthorized"),
  provisioningPlan: (payload: Record<string, unknown>) =>
    request<{ commands: string[] }>("/provisioning/plan", { method: "POST", body: JSON.stringify(payload) }),
};
