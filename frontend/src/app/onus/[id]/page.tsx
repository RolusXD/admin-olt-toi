"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { FormEvent, useState } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { Panel } from "@/components/ui/panel";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/services/api";
import { useApiData } from "@/hooks/useApiData";
import type { Nap, Olt, Onu, OnuEvent, PonPort, PowerSample, Zone } from "@/types";

export default function OnuDetailPage() {
  const params = useParams<{ id: string }>();
  const onu = useApiData<Onu | null>(() => api.onu(params.id), null);
  const olts = useApiData<Olt[]>(api.olts, []);
  const zones = useApiData<Zone[]>(api.zones, []);
  const naps = useApiData<Nap[]>(api.naps, []);
  const ponPorts = useApiData<PonPort[]>(() => api.ponPorts(), []);
  const history = useApiData<PowerSample[]>(() => api.onuPowerHistory(params.id), []);
  const events = useApiData<OnuEvent[]>(() => api.onuEvents(params.id), []);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const current = onu.data;
  const olt = olts.data.find((item) => item.id === current?.olt_id);
  const zone = zones.data.find((item) => item.id === current?.zone_id);
  const nap = naps.data.find((item) => item.id === current?.nap_id);
  const pon = ponPorts.data.find((item) => item.id === current?.pon_port_id);

  async function saveInternalInfo(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!current) return;
    const form = new FormData(event.currentTarget);
    setSaving(true); setMessage(null);
    try {
      const updated = await api.updateOnuInternalInfo(current.id, {
        zone_id: form.get("zone_id") ? Number(form.get("zone_id")) : null,
        nap_id: form.get("nap_id") ? Number(form.get("nap_id")) : null,
        nap_port: form.get("nap_port") ? Number(form.get("nap_port")) : null,
        zone_name: String(form.get("zone_name") || "") || null,
        nap_name: String(form.get("nap_name") || "") || null,
        nap_port_label: String(form.get("nap_port") || "") || null,
        address_reference: String(form.get("address_reference") || "") || null,
        odb_name: String(form.get("odb_name") || "") || null,
        external_id: String(form.get("external_id") || "") || null,
        auth_date: String(form.get("auth_date") || "") || null,
        technician_notes: String(form.get("technician_notes") || "") || null,
      });
      onu.setData(updated); setMessage("Informacion interna actualizada. No se enviaron comandos a la OLT.");
    } catch (exc) { setMessage(exc instanceof Error ? exc.message : "No se pudo guardar"); }
    finally { setSaving(false); }
  }

  return (
    <AppShell>
      <div className="space-y-5">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-slate-950">{current?.customer_name ?? "Detalle ONU"}</h1>
            <p className="text-sm text-muted">{current?.serial_number ?? "Cargando informacion"}</p>
          </div>
          <Link className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700" href="/onus">
            Volver a ONUs
          </Link>
        </div>

        {current && (
          <div className="grid gap-5 xl:grid-cols-[1fr_360px]">
            <Panel className="p-4 space-y-4">
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                <Field label="Cliente" value={current.customer_name} />
                <Field label="Serial" value={current.serial_number} />
                <Field label="OLT" value={current.olt_code ? `${current.olt_code} - ${current.olt_name ?? ""}` : olt?.name ?? current.olt_id} />
                <Field label="OLT snapshot" value={current.olt_code_snapshot ?? ""} />
                <Field label="PON" value={pon?.interface_name ?? current.pon_port_id ?? ""} />
                <Field label="Zona" value={zone?.name ?? ""} />
                <Field label="NAP" value={nap?.name ?? ""} />
                <Field label="VLAN" value={current.vlan} />
                <Field label="Perfil UP" value={current.speed_profile_up ?? ""} />
                <Field label="Perfil DOWN" value={current.speed_profile_down ?? current.speed_profile} />
                <Field label="Estado actual" value={current.status} />
                <Field label="RX actual" value={formatDbm(current.rx_power)} />
                <Field label="TX actual" value={formatDbm(current.tx_power)} />
              </div>

              <div className="border-t border-slate-200 pt-4">
                <h2 className="mb-2 text-sm font-semibold text-slate-950">Comportamiento ONU</h2>
                <p className="mb-3 text-xs text-muted">
                  Vista de solo lectura a partir de datos importados y catálogos actuales. No envía comandos a la OLT ni permite edición.
                </p>

                <OnuBehaviorSection onu={current} />
              </div>
            </Panel>

            <Panel className="p-4">
              <h2 className="mb-3 text-sm font-semibold text-slate-950">Senal actual</h2>
              <div className={`inline-flex rounded-md px-3 py-2 text-sm ${signalTone(current.signal_status)}`}>
                {current.signal_status ?? "sin muestra"}
              </div>
              <div className="mt-4 text-sm text-muted">Ultima actualizacion</div>
              <div className="text-sm text-slate-800">{formatDate(current.last_monitored_at)}</div>
            </Panel>
          </div>
        )}

        {current && (
          <Panel className="p-4">
            <h2 className="mb-1 text-sm font-semibold text-slate-950">Informacion importada / Observaciones</h2>
            <p className="mb-4 text-xs text-muted">Edicion exclusiva de la base interna. No modifica la description ni la configuracion de la OLT.</p>
            <div className="mb-4 grid gap-3 md:grid-cols-[180px_1fr]">
              <div className="text-sm text-muted">Description original</div>
              <div className="whitespace-pre-wrap break-all rounded-md border border-slate-200 bg-slate-50 p-3 font-mono text-xs text-slate-800">{current.description_original || current.raw_description || "Sin description"}</div>
              <div className="text-sm text-muted">Estado de interpretacion</div><div className="text-sm font-medium text-slate-800">{current.description_parse_status ?? "unknown"}</div>
            </div>
            <form key={current.updated_at ?? current.id} className="grid gap-3 md:grid-cols-3" onSubmit={saveInternalInfo}>
              <select name="zone_id" defaultValue={current.zone_id ?? ""} className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm"><option value="">Zona interna</option>{zones.data.filter((item) => item.olt_id === current.olt_id || item.id === current.zone_id).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select>
              <select name="nap_id" defaultValue={current.nap_id ?? ""} className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm"><option value="">NAP interna</option>{naps.data.filter((item) => item.olt_id === current.olt_id || item.id === current.nap_id).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select>
              <Input name="nap_port" type="number" defaultValue={current.nap_port ?? ""} placeholder="Puerto NAP" />
              <Input name="zone_name" defaultValue={current.zone_name ?? zone?.name ?? ""} placeholder="Zona descriptiva" />
              <Input name="nap_name" defaultValue={current.nap_name ?? nap?.name ?? ""} placeholder="NAP descriptiva" />
              <Input name="address_reference" defaultValue={current.address_reference ?? ""} placeholder="Direccion / referencia" />
              <Input name="odb_name" defaultValue={current.odb_name ?? ""} placeholder="ODB / ODN" />
              <Input name="external_id" defaultValue={current.external_id ?? ""} placeholder="ID externo" />
              <Input name="auth_date" type="date" defaultValue={current.auth_date?.slice(0, 10) ?? ""} />
              <textarea name="technician_notes" defaultValue={current.technician_notes ?? ""} className="min-h-28 rounded-md border border-slate-200 bg-white p-3 text-sm md:col-span-3" placeholder="Observaciones internas editables" />
              <div className="flex items-center gap-3 md:col-span-3"><Button disabled={saving}>{saving ? "Guardando..." : "Guardar observaciones"}</Button>{message && <span className="text-sm text-slate-700">{message}</span>}</div>
            </form>
          </Panel>
        )}

        <Panel className="overflow-hidden">
          <div className="border-b border-slate-200 px-4 py-3">
            <h2 className="text-sm font-semibold text-slate-950">Historico de potencia</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase text-muted">
                <tr>
                  <th className="px-4 py-3">Fecha</th>
                  <th className="px-4 py-3">RX</th>
                  <th className="px-4 py-3">TX</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {history.data.map((sample) => (
                  <tr key={sample.id}>
                    <td className="px-4 py-3 text-slate-700">{formatDate(sample.created_at)}</td>
                    <td className="px-4 py-3 text-slate-700">{formatDbm(sample.rx_power)}</td>
                    <td className="px-4 py-3 text-slate-700">{formatDbm(sample.tx_power)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>

        <Panel className="overflow-hidden">
          <div className="border-b border-slate-200 px-4 py-3">
            <h2 className="text-sm font-semibold text-slate-950">Eventos recientes</h2>
          </div>
          <div className="divide-y divide-slate-100">
            {events.data.map((event) => (
              <div key={event.id} className="grid gap-1 px-4 py-3 text-sm md:grid-cols-[180px_120px_1fr]">
                <div className="text-muted">{formatDate(event.created_at)}</div>
                <div className="font-medium text-slate-800">{event.event_type}</div>
                <div className="text-slate-700">{event.description}</div>
              </div>
            ))}
            {!events.data.length && <div className="px-4 py-6 text-sm text-muted">Sin eventos registrados.</div>}
          </div>
        </Panel>
      </div>
    </AppShell>
  );
}

function Field({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <div className="text-xs uppercase text-muted">{label}</div>
      <div className="mt-1 text-sm font-medium text-slate-900">{value}</div>
    </div>
  );
}

function OnuBehaviorSection({ onu }: { onu: Onu }) {
  const behavior = onu.behavior;

  if (!behavior) {
    return (
      <div className="rounded-md border border-amber-100 bg-amber-50 p-3 text-sm text-amber-900">
        <div className="font-medium">Desconocido/importado</div>
        <div className="mt-1 text-xs text-amber-900/80">
          ONU importada sin clasificación operacional. Requiere saneamiento manual.
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {behavior.mode_simple === "unknown" && (
        <div className="rounded-md border border-amber-100 bg-amber-50 p-3 text-sm text-amber-900">
          <div className="font-medium">ONU importada sin clasificación operacional. Requiere saneamiento manual.</div>
        </div>
      )}

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        <Field label="Modo ONU" value={behavior.mode_label} />
        <Field label="Plantilla" value={behavior.template_name ?? behavior.mode_code ?? onu.service_mode_code ?? "-"} />
        <Field
          label="VLAN WAN"
          value={behavior.vlan_name ? `${behavior.vlan_id} – ${behavior.vlan_name}` : behavior.vlan_id}
        />
        <Field label="Perfil subida" value={behavior.speed_profile_up ?? onu.speed_profile_up ?? ""} />
        <Field
          label="Perfil bajada"
          value={behavior.speed_profile_down ?? onu.speed_profile_down ?? onu.speed_profile ?? ""}
        />
        <Field label="DHCP Source" value={behavior.dhcp_source ?? "-"} />
        <Field label="IPHost" value={behavior.use_iphost ? "Sí" : "No"} />
        <Field label="VEIP" value={behavior.use_veip ? "Sí" : "No"} />
        <Field label="VLAN Filter" value={behavior.use_vlan_filter ? "Sí" : "No"} />
        <Field label="Loop Detect" value={behavior.use_loop_detect ? "Sí" : "No"} />
        <Field label="WiFi deshabilitado" value={behavior.disable_wifi ? "Sí" : "No"} />
        <Field
          label="Estado de calidad documental"
          value={behavior.data_quality_status ?? onu.description_parse_status ?? "-"}
        />
      </div>
    </div>
  );
}

function formatDbm(value?: number | null) {
  return typeof value === "number" ? `${value.toFixed(2)} dBm` : "";
}

function formatDate(value?: string | null) {
  return value ? new Date(value).toLocaleString() : "";
}

function signalTone(value?: string | null) {
  if (value === "critical") return "bg-red-100 text-red-800";
  if (value === "warning") return "bg-amber-100 text-amber-800";
  if (value === "normal") return "bg-emerald-100 text-emerald-800";
  return "bg-slate-100 text-slate-700";
}
