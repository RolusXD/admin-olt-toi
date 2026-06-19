"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { CheckCircle2, ClipboardCheck, FileText, ShieldAlert, XCircle } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/button";
import { EnvironmentBadge } from "@/components/ui/environment-badge";
import { Input } from "@/components/ui/input";
import { Panel } from "@/components/ui/panel";
import { api } from "@/services/api";
import { useApiData } from "@/hooks/useApiData";
import type { Nap, NapPort, Olt, Onu, OnuType, ProfileCatalog, ProvisioningPlan, UnauthorizedOnu, Vlan, Zone } from "@/types";

export default function ProvisioningPage() {
  const [showLab, setShowLab] = useState(false);
  const environment = showLab ? "all" : "production";
  const [selectedOltId, setSelectedOltId] = useState<string>("");
  const [selectedUnauthorizedId, setSelectedUnauthorizedId] = useState<string>("");
  const [selectedZoneId, setSelectedZoneId] = useState<string>("");
  const [selectedNapId, setSelectedNapId] = useState<string>("");
  const [overrideOnuId, setOverrideOnuId] = useState(false);
  const [suggestedOnuId, setSuggestedOnuId] = useState<string>("");
  const [plan, setPlan] = useState<ProvisioningPlan | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const olts = useApiData<Olt[]>(() => api.olts(showLab ? {} : { environment: "production" }), [], [showLab]);
  const pending = useApiData<UnauthorizedOnu[]>(
    () => api.unauthorizedOnus({ environment, status: "pending" }),
    [],
    [environment],
  );
  const zones = useApiData<Zone[]>(api.zones, []);
  const naps = useApiData<Nap[]>(api.naps, []);
  const vlans = useApiData<Vlan[]>(() => api.vlans(selectedOltId ? { olt_id: selectedOltId } : {}), [], [selectedOltId]);
  const onuTypes = useApiData<OnuType[]>(() => api.onuTypes({ is_active: 1 }), []);
  const uploadProfiles = useApiData<ProfileCatalog[]>(
    () => api.profileCatalogs({ direction: "upload", profile_kind: "tcont", is_active: true }),
    [],
    [],
  );
  const downloadProfiles = useApiData<ProfileCatalog[]>(
    () => api.profileCatalogs({ direction: "download", profile_kind: "traffic", is_active: true }),
    [],
    [],
  );
  const napPorts = useApiData<NapPort[]>(() => api.napPorts(), []);
  const onus = useApiData<Onu[]>(() => api.onus({ environment }), [], [environment]);

  const selectedPending = useMemo(
    () => pending.data.find((onu) => String(onu.id) === selectedUnauthorizedId) ?? null,
    [pending.data, selectedUnauthorizedId],
  );
  const selectedOlt = useMemo(
    () => olts.data.find((olt) => String(olt.id) === (selectedOltId || String(selectedPending?.olt_id ?? ""))) ?? null,
    [olts.data, selectedOltId, selectedPending],
  );
  const napsForZone = useMemo(
    () => naps.data.filter((nap) => !selectedZoneId || String(nap.zone_id) === selectedZoneId),
    [naps.data, selectedZoneId],
  );
  const selectedNap = useMemo(() => naps.data.find((nap) => String(nap.id) === selectedNapId) ?? null, [naps.data, selectedNapId]);
  const selectedDefaultVlan = useMemo(
    () => vlans.data.find((vlan) => vlan.is_default_for_provisioning) ?? vlans.data.find((vlan) => vlan.vlan_id === 600) ?? vlans.data[0],
    [vlans.data],
  );
  const selectedDefaultType = useMemo(
    () => onuTypes.data.find((type) => type.is_default_for_provisioning && String(type.olt_id) === selectedOltId) ?? onuTypes.data.find((type) => type.is_provisioning_allowed && String(type.olt_id) === selectedOltId),
    [onuTypes.data, selectedOltId],
  );
  const defaultUpload = useMemo(
    () => uploadProfiles.data.find((profile) => profile.is_default && String(profile.olt_id) === selectedOltId) ?? uploadProfiles.data.find((profile) => profile.name === "SMARTOLT-1G-UP" && String(profile.olt_id) === selectedOltId),
    [uploadProfiles.data, selectedOltId],
  );
  const defaultDownload = useMemo(
    () => downloadProfiles.data.find((profile) => profile.is_default && String(profile.olt_id) === selectedOltId) ?? downloadProfiles.data.find((profile) => profile.name === "SMARTOLT-1G-DOWN" && String(profile.olt_id) === selectedOltId),
    [downloadProfiles.data, selectedOltId],
  );

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const oltId = params.get("olt_id");
    const unauthorizedId = params.get("unauthorized_onu_id");
    const onuId = params.get("onu_id");
    if (oltId) setSelectedOltId(oltId);
    if (unauthorizedId) setSelectedUnauthorizedId(unauthorizedId);
    if (onuId) setSuggestedOnuId(onuId);
  }, []);

  useEffect(() => {
    if (selectedPending && !suggestedOnuId) {
      setSuggestedOnuId(extractSuggestedOnuId(selectedPending) || "1");
    }
  }, [selectedPending, suggestedOnuId]);

  useEffect(() => {
    if (selectedNap) setSelectedZoneId(String(selectedNap.zone_id));
  }, [selectedNap]);

  function selectPending(id: string) {
    const item = pending.data.find((onu) => String(onu.id) === id);
    setSelectedUnauthorizedId(id);
    if (item) setSelectedOltId(String(item.olt_id));
    setSuggestedOnuId(item ? extractSuggestedOnuId(item) || "1" : "");
    setPlan(null);
    setMessage(null);
    setError(null);
  }

  async function createPlan(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    setMessage(null);
    const form = new FormData(event.currentTarget);
    const uploadProfileId = Number(form.get("upload_profile_id") || 0);
    const downloadProfileId = Number(form.get("download_profile_id") || 0);
    const selectedUploadProfile = uploadProfiles.data.find((profile) => profile.id === uploadProfileId);
    const selectedDownloadProfile = downloadProfiles.data.find((profile) => profile.id === downloadProfileId);
    const payload = {
      unauthorized_onu_id: Number(selectedUnauthorizedId),
      customer_name: String(form.get("customer_name") ?? ""),
      customer_reference: String(form.get("customer_reference") ?? ""),
      address_reference: String(form.get("address_reference") ?? ""),
      odb_name: String(form.get("odb_name") ?? ""),
      technical_comment: String(form.get("technical_comment") ?? ""),
      address: String(form.get("address") ?? ""),
      notes: String(form.get("notes") ?? ""),
      zone_id: Number(selectedZoneId || form.get("zone_id")),
      nap_id: Number(selectedNapId || form.get("nap_id")),
      nap_port: form.get("nap_port") ? Number(form.get("nap_port")) : undefined,
      onu_type: String(form.get("onu_type") ?? ""),
      vlan: Number(form.get("vlan")),
      upload_profile_id: uploadProfileId || undefined,
      download_profile_id: downloadProfileId || undefined,
      speed_profile_up: selectedUploadProfile?.name ?? "",
      speed_profile_down: selectedDownloadProfile?.name ?? "",
      selected_onu_id: form.get("selected_onu_id") ? Number(form.get("selected_onu_id")) : undefined,
      allow_manual_onu_id: overrideOnuId,
      onu_mode: String(form.get("onu_mode") ?? "router"),
      vlan_lan_mode: String(form.get("vlan_lan_mode") ?? "tag"),
      ethernet_port: String(form.get("ethernet_port") ?? "eth_0/1"),
      dhcp_mode: String(form.get("dhcp_mode") ?? "from-internet"),
    };
    try {
      const created = await api.createProvisioningPlan(payload);
      setPlan(created);
      setMessage("Seleccion validada y CLI generado. No se ejecuto ningun comando sobre la OLT.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo crear el plan.");
    } finally {
      setLoading(false);
    }
  }

  async function validatePlan() {
    if (!plan) return;
    setLoading(true);
    setError(null);
    try {
      const result = await api.revalidateProvisioningPlan(plan.id);
      setPlan(result.plan);
      setMessage(result.errors.length ? "Validacion completada con errores." : "Plan validado correctamente.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo validar el plan.");
    } finally {
      setLoading(false);
    }
  }

  async function approvePlan() {
    if (!plan) return;
    setLoading(true);
    setError(null);
    try {
      const approved = await api.approveProvisioningPlan(plan.id);
      setPlan(approved);
      setMessage("Plan aprobado. Sigue sin ejecutarse ningun comando sobre la OLT.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo aprobar el plan.");
    } finally {
      setLoading(false);
    }
  }

  async function preflightPlan() {
    if (!plan) return;
    setLoading(true);
    setError(null);
    try {
      const result = await api.preflightProvisioningPlan(plan.id);
      setPlan(result.plan);
      setMessage(result.is_valid ? "Preflight tecnico aprobado en modo read-only." : "Preflight tecnico finalizo con errores.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo ejecutar el preflight tecnico.");
    } finally {
      setLoading(false);
    }
  }

  async function cancelPlan() {
    if (!plan) return;
    setLoading(true);
    setError(null);
    try {
      const cancelled = await api.cancelProvisioningPlan(plan.id);
      setPlan(cancelled);
      setMessage("Plan cancelado.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo cancelar el plan.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AppShell>
      <div className="space-y-5">
        <div>
          <h2 className="text-2xl font-semibold text-slate-950">Asistente de Aprovisionamiento</h2>
          <p className="mt-1 text-sm text-muted">Seleccion manual, validacion tecnica y preview CLI antes de la ejecucion controlada.</p>
        </div>

        <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950">
          No se ejecutan comandos de configuracion. Seleccione manualmente cada dato tecnico antes de generar el CLI.
        </div>
        {message && <div className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">{message}</div>}
        {error && <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">{error}</div>}

        <Panel className="p-4">
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-2">
              <ClipboardCheck className="h-4 w-4 text-primary" />
              <h3 className="text-sm font-semibold text-slate-950">Paso 1: Seleccionar manualmente ONU pendiente</h3>
            </div>
            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input type="checkbox" checked={showLab} onChange={(event) => setShowLab(event.target.checked)} />
              Mostrar laboratorio
            </label>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <label className="text-sm font-medium text-slate-700">
              OLT
              <select
                className="mt-1 h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm"
                value={selectedOltId}
                onChange={(event) => setSelectedOltId(event.target.value)}
              >
                <option value="">Todas las OLTs visibles</option>
                {olts.data.map((olt) => (
                  <option key={olt.id} value={olt.id}>
                    {olt.olt_code} - {olt.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm font-medium text-slate-700">
              ONU pendiente
              <select
                className="mt-1 h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm"
                value={selectedUnauthorizedId}
                onChange={(event) => selectPending(event.target.value)}
              >
                <option value="">Seleccione una ONU</option>
                {pending.data
                  .filter((onu) => !selectedOltId || String(onu.olt_id) === selectedOltId)
                  .map((onu) => (
                    <option key={onu.id} value={onu.id}>
                      {onu.serial_number} - {onu.pon_port_interface ?? "sin PON"} - {onu.olt_code_snapshot ?? onu.olt_code}
                    </option>
                  ))}
              </select>
            </label>
          </div>
          {selectedPending && (
            <div className="mt-4 grid gap-3 text-sm md:grid-cols-5">
              <Info label="OLT" value={selectedPending.olt_name ?? selectedPending.olt_code ?? selectedPending.olt_id} />
              <Info label="OLT Code" value={selectedPending.olt_code_snapshot ?? selectedPending.olt_code ?? "-"} />
              <Info label="Puerto PON" value={selectedPending.pon_port_interface ?? "-"} />
              <Info label="Serial" value={selectedPending.serial_number} />
              <div>
                <div className="text-xs text-muted">Entorno</div>
                <div className="mt-1">{selectedOlt ? <EnvironmentBadge environment={selectedOlt.environment} /> : "-"}</div>
              </div>
            </div>
          )}
        </Panel>

        <form className="space-y-5" onSubmit={createPlan}>
          <Panel className="p-4">
            <h3 className="mb-4 text-sm font-semibold text-slate-950">Paso 2: Datos cliente</h3>
            <div className="grid gap-3 md:grid-cols-2">
              <Input name="customer_name" placeholder="Nombre cliente" required />
              <Input name="customer_reference" placeholder="Referencia cliente" />
              <Input name="technical_comment" placeholder="Comentario tecnico" />
              <Input name="address" placeholder="Direccion" />
              <Input className="md:col-span-2" name="notes" placeholder="Observaciones" />
            </div>
          </Panel>

          <Panel className="p-4">
            <h3 className="mb-4 text-sm font-semibold text-slate-950">Paso 3: Ubicacion / Localizacion</h3>
            <div className="grid gap-3 md:grid-cols-3">
              <Select
                name="zone_id"
                label="Zona"
                value={selectedZoneId}
                onChange={setSelectedZoneId}
                items={zones.data.filter((zone) => zone.is_active !== false).map((zone) => ({ value: zone.id, label: zone.name }))}
              />
              <Select
                name="nap_id"
                label="NAP"
                value={selectedNapId}
                onChange={(value) => {
                  setSelectedNapId(value);
                  const nap = naps.data.find((item) => String(item.id) === value);
                  if (nap) setSelectedZoneId(String(nap.zone_id));
                }}
                items={napsForZone.filter((nap) => nap.is_active !== false).map((nap) => ({ value: nap.id, label: nap.name }))}
              />
              <Select
                name="nap_port"
                label="Puerto NAP opcional"
                required={false}
                items={napPorts.data
                  .filter((port) => (!selectedNapId || String(port.nap_id) === selectedNapId) && (port.status === "free" || port.status === "reserved"))
                  .map((port) => ({ value: port.port_number, label: `NAP ${port.nap_id} - Puerto ${port.port_number} - ${port.status}` }))}
              />
              <Input name="address_reference" placeholder="Direccion / referencia" />
              <Input name="odb_name" placeholder="ODB/ODN opcional" />
            </div>
            <NapOccupation onus={onus.data} />
          </Panel>

          <Panel className="p-4">
            <h3 className="mb-4 text-sm font-semibold text-slate-950">Paso 4: Perfiles y VLANs</h3>
            <div className="grid gap-3 md:grid-cols-4">
              <Select
                name="onu_type"
                label="Tipo ONU"
                defaultValue={selectedDefaultType?.name}
                items={onuTypes.data
                  .filter((type) => !selectedOltId || String(type.olt_id) === selectedOltId)
                  .map((type) => ({
                    value: type.name,
                    label: `${type.display_name || type.operational_alias || type.name} - ZTE: ${type.name}${
                      type.is_provisioning_allowed ? "" : " (no permitido)"
                    }`,
                  }))}
              />
              <label className="text-sm font-medium text-slate-700">
                ONU ID sugerido
                <Input name="selected_onu_id" placeholder="ONU ID" type="number" min={1} value={suggestedOnuId} onChange={(event) => setSuggestedOnuId(event.target.value)} readOnly={!overrideOnuId} required />
              </label>
              <Select
                name="vlan"
                label="VLAN"
                defaultValue={selectedDefaultVlan?.vlan_id}
                items={vlans.data
                  .filter((vlan) => vlan.is_active !== false && (!selectedOltId || String(vlan.olt_id) === selectedOltId))
                  .map((vlan) => ({ value: vlan.vlan_id, label: `${vlan.vlan_id} - ${vlan.description ?? vlan.name ?? "-"} - ${vlan.onu_count ?? 0} ONUs` }))}
              />
              <Select
                name="upload_profile_id"
                label="Perfil UP"
                defaultValue={defaultUpload?.id}
                items={uploadProfiles.data
                  .filter((profile) => !selectedOltId || String(profile.olt_id) === selectedOltId)
                  .map((profile) => ({ value: profile.id, label: `${profile.name} (${profile.maximum_kbps ?? "-"} kbps)` }))}
              />
              <Select
                name="download_profile_id"
                label="Perfil DOWN"
                defaultValue={defaultDownload?.id}
                items={downloadProfiles.data
                  .filter((profile) => !selectedOltId || String(profile.olt_id) === selectedOltId)
                  .map((profile) => ({ value: profile.id, label: `${profile.name} (${profile.pir_kbps ?? "-"} kbps)` }))}
              />
            </div>
            <label className="mt-3 inline-flex items-center gap-2 text-sm text-slate-700">
              <input type="checkbox" checked={overrideOnuId} onChange={(event) => setOverrideOnuId(event.target.checked)} />
              Modificar ONU ID manualmente
            </label>
          </Panel>

          <Panel className="p-4">
            <h3 className="mb-4 text-sm font-semibold text-slate-950">Paso 5: Comportamiento ONU / Puertos</h3>
            <div className="grid gap-3 md:grid-cols-4">
              <Select name="onu_mode" label="Modo ONU" defaultValue="router" items={[{ value: "router", label: "Router" }, { value: "bridge", label: "Bridge" }]} />
              <Select name="vlan_lan_mode" label="Modo VLAN LAN" defaultValue="tag" items={[{ value: "tag", label: "tag" }, { value: "untag", label: "untag" }, { value: "transparent", label: "transparent" }]} />
              <Select name="ethernet_port" label="Puerto Ethernet principal" defaultValue="eth_0/1" items={[{ value: "eth_0/1", label: "eth_0/1" }, { value: "eth_0/2", label: "eth_0/2" }]} />
              <Select name="dhcp_mode" label="DHCP" defaultValue="from-internet" items={[{ value: "from-internet", label: "from-internet" }, { value: "from-onu", label: "from-onu" }, { value: "none", label: "none" }]} />
            </div>
          </Panel>

          <div className="flex flex-wrap gap-2">
            <Button disabled={!selectedUnauthorizedId || loading}>
              <FileText className="h-4 w-4" /> Generar CLI
            </Button>
            <Button type="button" variant="secondary" onClick={validatePlan} disabled={!plan || loading}>
              <CheckCircle2 className="h-4 w-4" /> Validar seleccion
            </Button>
            <Button type="button" variant="secondary" onClick={approvePlan} disabled={!plan || loading || plan.status === "approved"}>
              <ClipboardCheck className="h-4 w-4" /> Aprobar plan
            </Button>
            <Button type="button" variant="secondary" onClick={preflightPlan} disabled={!plan || loading || plan.status !== "approved"}>
              <ShieldAlert className="h-4 w-4" /> Preflight
            </Button>
            <Button type="button" variant="secondary" disabled>
              Ejecucion controlada
            </Button>
            <Button type="button" variant="danger" onClick={cancelPlan} disabled={!plan || loading || plan.status === "cancelled"}>
              <XCircle className="h-4 w-4" /> Cancelar
            </Button>
          </div>
        </form>

        {plan && <PlanPreview plan={plan} />}
      </div>
    </AppShell>
  );
}

function Select({
  name,
  label,
  items,
  value,
  defaultValue,
  required = true,
  onChange,
}: {
  name: string;
  label: string;
  items: Array<{ value: string | number; label: string }>;
  value?: string;
  defaultValue?: string | number;
  required?: boolean;
  onChange?: (value: string) => void;
}) {
  return (
    <label className="text-sm font-medium text-slate-700">
      {label}
      <select
        name={name}
        className="mt-1 h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm"
        required={required}
        value={value}
        defaultValue={value === undefined ? defaultValue ?? "" : undefined}
        onChange={(event) => onChange?.(event.target.value)}
      >
        <option value="">Seleccione</option>
        {items.map((item) => (
          <option key={item.value} value={item.value}>
            {item.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function Info({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <div className="text-xs text-muted">{label}</div>
      <div className="mt-1 font-medium text-slate-900">{value}</div>
    </div>
  );
}

function NapOccupation({ onus }: { onus: Onu[] }) {
  const occupied = onus
    .filter((onu) => onu.nap_id && onu.nap_port)
    .slice(0, 12)
    .map((onu) => `${onu.nap_id}:${onu.nap_port}`);
  return (
    <div className="mt-4 rounded-md border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
      <div className="font-medium text-slate-950">Ocupacion actual visible</div>
      <div className="mt-2">{occupied.length ? occupied.join(", ") : "Sin puertos ocupados en la vista actual."}</div>
    </div>
  );
}

function PlanPreview({ plan }: { plan: ProvisioningPlan }) {
  return (
    <Panel className="p-4">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-slate-950">Preview del plan</h3>
          <p className="mt-1 text-xs text-muted">Estado: {plan.status}</p>
        </div>
        <ShieldAlert className="h-5 w-5 text-warning" />
      </div>
      <div className="grid gap-3 text-sm md:grid-cols-3">
        <Info label="Serial" value={plan.serial_number} />
        <Info label="PON" value={plan.pon_port_interface ?? "-"} />
        <Info label="Cliente" value={plan.customer_name} />
        <Info label="Description generado" value={plan.description_generated ?? plan.onu_description ?? "-"} />
        <Info label="NAP puerto" value={plan.nap_port ?? "Opcional"} />
        <Info label="VLAN" value={plan.vlan} />
        <Info label="Perfiles" value={`${plan.speed_profile_up} / ${plan.speed_profile_down}`} />
        <Info label="ONU ID seleccionado" value={plan.selected_onu_id ?? "-"} />
        <Info label="ONU ID sugerido" value={plan.suggested_onu_id ?? "-"} />
        <Info
          label="Diferencia ONU ID"
          value={
            plan.selected_onu_id && plan.suggested_onu_id && plan.selected_onu_id !== plan.suggested_onu_id
              ? `${plan.selected_onu_id} vs ${plan.suggested_onu_id}`
              : "Sin diferencia"
          }
        />
      </div>
      <TechnicalValidation plan={plan} />
      <PreflightChecks plan={plan} />
      {(plan.validation_errors.length > 0 || plan.validation_warnings.length > 0) && (
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <ValidationBox title="Errors" items={plan.validation_errors} tone="red" />
          <ValidationBox title="Warnings" items={plan.validation_warnings} tone="amber" />
        </div>
      )}
      <pre className="mt-4 max-h-[420px] overflow-auto rounded-md bg-slate-950 p-4 text-xs leading-5 text-slate-50">
        {plan.generated_cli ?? "Sin CLI generado."}
      </pre>
    </Panel>
  );
}

function PreflightChecks({ plan }: { plan: ProvisioningPlan }) {
  const checks = plan.validation_result?.preflight_checks ?? {};
  const hasChecks = Object.keys(checks).length > 0;
  const items = [
    ["olt_accessible", "OLT"],
    ["card_exists", "Tarjeta"],
    ["pon_exists", "Puerto"],
    ["onu_detected", "ONU"],
    ["serial_detected", "Serial"],
    ["onu_id_available", "ONU ID"],
    ["vlan_exists", "VLAN"],
    ["upload_profile_exists", "Upload"],
    ["download_profile_exists", "Download"],
    ["onu_type_exists", "ONU Type"],
  ] as const;
  return (
    <div className="mt-4 rounded-md border border-slate-200 bg-white p-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="text-sm font-semibold text-slate-950">Preflight Tecnico</div>
          <div className="mt-1 text-xs text-muted">Lectura real read-only antes de permitir ejecucion controlada.</div>
        </div>
        <div className="text-xs font-medium text-slate-700">{plan.status}</div>
      </div>
      <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
        {items.map(([key, label]) => {
          const value = checks[key];
          const tone = !hasChecks ? "border-amber-200 bg-amber-50 text-amber-900" : value ? "border-emerald-200 bg-emerald-50 text-emerald-900" : "border-red-200 bg-red-50 text-red-900";
          const symbol = !hasChecks ? "!" : value ? "OK" : "ERR";
          return (
            <div key={key} className={`rounded-md border px-3 py-2 text-sm ${tone}`}>
              <div className="text-xs font-semibold">{symbol}</div>
              <div className="mt-1 font-medium">{label}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function TechnicalValidation({ plan }: { plan: ProvisioningPlan }) {
  const result = plan.validation_result;
  const isValid = result?.is_valid ?? plan.validation_errors.length === 0;
  return (
    <div
      className={`mt-4 rounded-md border p-4 text-sm ${
        isValid ? "border-emerald-200 bg-emerald-50 text-emerald-950" : "border-red-200 bg-red-50 text-red-950"
      }`}
    >
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="font-semibold">Validacion Tecnica</div>
          <div className="mt-1">{isValid ? "Apto para ejecutar" : "No apto para ejecutar"}</div>
        </div>
        <div className="text-xs">
          {result?.validated_at ? `Validado: ${new Date(result.validated_at).toLocaleString()}` : "Pendiente de validacion"}
        </div>
      </div>
      {result && (
        <div className="mt-3 grid gap-3 sm:grid-cols-3">
          <Info label="ONU ID sugerido" value={result.suggested_onu_id ?? "-"} />
          <Info label="ONU ID seleccionado" value={result.selected_onu_id ?? "-"} />
          <Info label="IDs ocupados" value={result.occupied_onu_ids.length ? result.occupied_onu_ids.join(", ") : "Ninguno"} />
        </div>
      )}
    </div>
  );
}

function ValidationBox({ title, items, tone }: { title: string; items: string[]; tone: "red" | "amber" }) {
  const classes =
    tone === "red"
      ? "border-red-200 bg-red-50 text-red-900"
      : "border-amber-200 bg-amber-50 text-amber-900";
  return (
    <div className={`rounded-md border p-3 text-sm ${classes}`}>
      <div className="font-medium">{title}</div>
      <ul className="mt-2 list-disc space-y-1 pl-5">
        {items.length ? items.map((item) => <li key={item}>{item}</li>) : <li>Sin registros.</li>}
      </ul>
    </div>
  );
}

function extractSuggestedOnuId(onu: UnauthorizedOnu) {
  const interfaceMatch = onu.raw_output?.match(/gpon-onu_\d+\/\d+\/\d+:(\d+)/i);
  return interfaceMatch?.[1] ?? "";
}
