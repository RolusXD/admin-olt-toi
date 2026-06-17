"use client";

import { FormEvent, useMemo, useState } from "react";
import { CheckCircle2, ClipboardCheck, FileText, ShieldAlert, XCircle } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/button";
import { EnvironmentBadge } from "@/components/ui/environment-badge";
import { Input } from "@/components/ui/input";
import { Panel } from "@/components/ui/panel";
import { api } from "@/services/api";
import { useApiData } from "@/hooks/useApiData";
import type { Nap, Olt, Onu, ProvisioningPlan, UnauthorizedOnu, Vlan, Zone } from "@/types";

export default function ProvisioningPage() {
  const [showLab, setShowLab] = useState(false);
  const environment = showLab ? "all" : "production";
  const [selectedOltId, setSelectedOltId] = useState<string>("");
  const [selectedUnauthorizedId, setSelectedUnauthorizedId] = useState<string>("");
  const [plan, setPlan] = useState<ProvisioningPlan | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const olts = useApiData<Olt[]>(() => api.olts(showLab ? {} : { environment: "production" }), []);
  const pending = useApiData<UnauthorizedOnu[]>(
    () => api.unauthorizedOnus({ environment, status: "pending" }),
    [],
  );
  const zones = useApiData<Zone[]>(api.zones, []);
  const naps = useApiData<Nap[]>(api.naps, []);
  const vlans = useApiData<Vlan[]>(() => api.vlans(selectedOltId ? { olt_id: selectedOltId } : {}), []);
  const onus = useApiData<Onu[]>(() => api.onus({ environment }), []);

  const selectedPending = useMemo(
    () => pending.data.find((onu) => String(onu.id) === selectedUnauthorizedId) ?? null,
    [pending.data, selectedUnauthorizedId],
  );
  const selectedOlt = useMemo(
    () => olts.data.find((olt) => String(olt.id) === (selectedOltId || String(selectedPending?.olt_id ?? ""))) ?? null,
    [olts.data, selectedOltId, selectedPending],
  );
  const napsForZone = useMemo(() => naps.data, [naps.data]);

  function selectPending(id: string) {
    const item = pending.data.find((onu) => String(onu.id) === id);
    setSelectedUnauthorizedId(id);
    if (item) setSelectedOltId(String(item.olt_id));
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
    const payload = {
      unauthorized_onu_id: Number(selectedUnauthorizedId),
      customer_name: String(form.get("customer_name") ?? ""),
      customer_reference: String(form.get("customer_reference") ?? ""),
      technical_comment: String(form.get("technical_comment") ?? ""),
      address: String(form.get("address") ?? ""),
      notes: String(form.get("notes") ?? ""),
      zone_id: Number(form.get("zone_id")),
      nap_id: Number(form.get("nap_id")),
      nap_port: Number(form.get("nap_port")),
      onu_type: String(form.get("onu_type") ?? ""),
      vlan: Number(form.get("vlan")),
      speed_profile_up: String(form.get("speed_profile_up") ?? ""),
      speed_profile_down: String(form.get("speed_profile_down") ?? ""),
    };
    try {
      const created = await api.createProvisioningPlan(payload);
      setPlan(created);
      setMessage("Plan creado en modo dry-run. No se ejecuto ningun comando sobre la OLT.");
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
      const result = await api.validateProvisioningPlan(plan.id);
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
          <p className="mt-1 text-sm text-muted">Modo dry-run: genera, valida y guarda propuesta CLI sin conectarse a la OLT.</p>
        </div>

        <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950">
          No se ejecutan comandos Telnet, SSH ni configuracion. Esta fase solo genera texto y registra el plan.
        </div>
        {message && <div className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">{message}</div>}
        {error && <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">{error}</div>}

        <Panel className="p-4">
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-2">
              <ClipboardCheck className="h-4 w-4 text-primary" />
              <h3 className="text-sm font-semibold text-slate-950">Paso 1: ONU pendiente</h3>
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
            <h3 className="mb-4 text-sm font-semibold text-slate-950">Paso 3: Datos FTTH</h3>
            <div className="grid gap-3 md:grid-cols-3">
              <Select name="zone_id" label="Zona" items={zones.data.map((zone) => ({ value: zone.id, label: zone.name }))} />
              <Select name="nap_id" label="NAP" items={napsForZone.map((nap) => ({ value: nap.id, label: nap.name }))} />
              <Input name="nap_port" placeholder="Puerto NAP" type="number" min={1} required />
            </div>
            <NapOccupation onus={onus.data} />
          </Panel>

          <Panel className="p-4">
            <h3 className="mb-4 text-sm font-semibold text-slate-950">Paso 4: Datos tecnicos</h3>
            <div className="grid gap-3 md:grid-cols-4">
              <Input name="onu_type" placeholder="Tipo ONU" defaultValue={selectedPending?.detected_vendor ?? selectedPending?.detected_type ?? "VSOL"} required />
              <Select
                name="vlan"
                label="VLAN"
                items={vlans.data.map((vlan) => ({ value: vlan.vlan_id, label: `${vlan.vlan_id} ${vlan.description ?? vlan.name ?? ""}` }))}
              />
              <Input name="speed_profile_up" placeholder="Perfil UP" defaultValue="SMARTOLT-1G-UP" required />
              <Input name="speed_profile_down" placeholder="Perfil DOWN" defaultValue="SMARTOLT-1G-DOWN" required />
            </div>
          </Panel>

          <div className="flex flex-wrap gap-2">
            <Button disabled={!selectedUnauthorizedId || loading}>
              <FileText className="h-4 w-4" /> Crear preview dry-run
            </Button>
            <Button type="button" variant="secondary" onClick={validatePlan} disabled={!plan || loading}>
              <CheckCircle2 className="h-4 w-4" /> Validar
            </Button>
            <Button type="button" variant="secondary" onClick={approvePlan} disabled={!plan || loading || plan.status === "approved"}>
              <ClipboardCheck className="h-4 w-4" /> Aprobar plan
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

function Select({ name, label, items }: { name: string; label: string; items: Array<{ value: string | number; label: string }> }) {
  return (
    <label className="text-sm font-medium text-slate-700">
      {label}
      <select name={name} className="mt-1 h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm" required>
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
        <Info label="NAP puerto" value={plan.nap_port} />
        <Info label="VLAN" value={plan.vlan} />
        <Info label="Perfiles" value={`${plan.speed_profile_up} / ${plan.speed_profile_down}`} />
      </div>
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
