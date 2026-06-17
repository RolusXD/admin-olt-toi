"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { AppShell } from "@/components/layout/AppShell";
import { Panel } from "@/components/ui/panel";
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

  const current = onu.data;
  const olt = olts.data.find((item) => item.id === current?.olt_id);
  const zone = zones.data.find((item) => item.id === current?.zone_id);
  const nap = naps.data.find((item) => item.id === current?.nap_id);
  const pon = ponPorts.data.find((item) => item.id === current?.pon_port_id);

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
            <Panel className="p-4">
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
