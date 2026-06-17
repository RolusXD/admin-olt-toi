"use client";

import { FormEvent, useMemo, useState } from "react";
import Link from "next/link";
import { Filter, RefreshCcw } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Panel } from "@/components/ui/panel";
import { EnvironmentBadge } from "@/components/ui/environment-badge";
import { api } from "@/services/api";
import { useApiData } from "@/hooks/useApiData";
import type { Nap, Olt, Onu, PonPort, Zone } from "@/types";

type Filters = {
  customer_name: string;
  serial_number: string;
  zone_id: string;
  nap_id: string;
  olt_id: string;
  olt_code: string;
  status: string;
  environment: string;
};

const emptyFilters: Filters = {
  customer_name: "",
  serial_number: "",
  zone_id: "",
  nap_id: "",
  olt_id: "",
  olt_code: "",
  status: "",
  environment: "production",
};

export default function OnusPage() {
  const olts = useApiData<Olt[]>(() => api.olts({ environment: "production" }), []);
  const zones = useApiData<Zone[]>(api.zones, []);
  const naps = useApiData<Nap[]>(api.naps, []);
  const ponPorts = useApiData<PonPort[]>(() => api.ponPorts(), []);
  const [filters, setFilters] = useState<Filters>(emptyFilters);
  const [query, setQuery] = useState<Filters>(emptyFilters);
  const [showLab, setShowLab] = useState(false);
  const onus = useApiData<Onu[]>(() => api.onus(query), []);

  const oltById = useMemo(() => new Map(olts.data.map((olt) => [olt.id, `${olt.olt_code} - ${olt.display_name || olt.name}`])), [olts.data]);
  const zoneById = useMemo(() => new Map(zones.data.map((zone) => [zone.id, zone.name])), [zones.data]);
  const napById = useMemo(() => new Map(naps.data.map((nap) => [nap.id, nap.name])), [naps.data]);
  const ponById = useMemo(
    () => new Map(ponPorts.data.map((pon) => [pon.id, pon.interface_name || `slot ${pon.slot}/${pon.port}`])),
    [ponPorts.data],
  );

  function submit(event: FormEvent) {
    event.preventDefault();
    setQuery(filters);
  }

  function clear() {
    setFilters(emptyFilters);
    setQuery(emptyFilters);
  }

  return (
    <AppShell>
      <div className="space-y-5">
        <div>
          <h1 className="text-xl font-semibold text-slate-950">ONUs</h1>
          <p className="text-sm text-muted">Inventario importado y estado operativo por OLT, zona y NAP.</p>
        </div>

        <Panel className="p-4">
          <form className="grid gap-3 xl:grid-cols-[1fr_1fr_160px_160px_180px_180px_140px_150px_auto]" onSubmit={submit}>
            <Input
              placeholder="Cliente"
              value={filters.customer_name}
              onChange={(event) => setFilters((current) => ({ ...current, customer_name: event.target.value }))}
            />
            <Input
              placeholder="Serial"
              value={filters.serial_number}
              onChange={(event) => setFilters((current) => ({ ...current, serial_number: event.target.value }))}
            />
            <select
              className="h-9 rounded-md border border-slate-200 bg-white px-3 text-sm"
              value={filters.zone_id}
              onChange={(event) => setFilters((current) => ({ ...current, zone_id: event.target.value, nap_id: "" }))}
            >
              <option value="">Zona</option>
              {zones.data.map((zone) => (
                <option key={zone.id} value={zone.id}>
                  {zone.name}
                </option>
              ))}
            </select>
            <select
              className="h-9 rounded-md border border-slate-200 bg-white px-3 text-sm"
              value={filters.nap_id}
              onChange={(event) => setFilters((current) => ({ ...current, nap_id: event.target.value }))}
            >
              <option value="">NAP</option>
              {naps.data
                .filter((nap) => !filters.zone_id || String(nap.zone_id) === filters.zone_id)
                .map((nap) => (
                  <option key={nap.id} value={nap.id}>
                    {nap.name}
                  </option>
                ))}
            </select>
            <select
              className="h-9 rounded-md border border-slate-200 bg-white px-3 text-sm"
              value={filters.olt_id}
              onChange={(event) => setFilters((current) => ({ ...current, olt_id: event.target.value }))}
            >
              <option value="">OLT</option>
              {olts.data.map((olt) => (
                <option key={olt.id} value={olt.id}>
                  {olt.olt_code} - {olt.name}
                </option>
              ))}
            </select>
            <Input
              placeholder="Codigo OLT"
              value={filters.olt_code}
              onChange={(event) => setFilters((current) => ({ ...current, olt_code: event.target.value.toUpperCase() }))}
            />
            <select
              className="h-9 rounded-md border border-slate-200 bg-white px-3 text-sm"
              value={filters.status}
              onChange={(event) => setFilters((current) => ({ ...current, status: event.target.value }))}
            >
              <option value="">Estado</option>
              <option value="online">online</option>
              <option value="offline">offline</option>
              <option value="unknown">unknown</option>
              <option value="unauthorized">unauthorized</option>
            </select>
            <label className="inline-flex items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={showLab}
                onChange={async (event) => {
                  const checked = event.target.checked;
                  setShowLab(checked);
                  olts.setData(await api.olts(checked ? {} : { environment: "production" }));
                  setFilters((current) => ({ ...current, environment: checked ? "" : "production" }));
                  setQuery((current) => ({ ...current, environment: checked ? "" : "production" }));
                }}
              />
              Mostrar laboratorio
            </label>
            <div className="flex gap-2">
              <Button type="submit">
                <Filter className="h-4 w-4" /> Filtrar
              </Button>
              <Button type="button" variant="secondary" onClick={clear}>
                <RefreshCcw className="h-4 w-4" />
              </Button>
            </div>
          </form>
        </Panel>

        <Panel className="overflow-hidden">
          <div className="border-b border-slate-200 px-4 py-3">
            <h2 className="text-sm font-semibold text-slate-950">Inventario ONU</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1280px] text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase text-muted">
                <tr>
                  {[
                    "Cliente",
                    "Serial",
                    "ONU Interface",
                    "OLT",
                    "PON",
                    "Zona",
                    "NAP",
                    "Puerto NAP",
                    "VLAN",
                    "Perfil UP",
                    "Perfil DOWN",
                    "RX",
                    "TX",
                    "Senal",
                    "Ultima actualizacion",
                    "Estado",
                  ].map((heading) => (
                    <th key={heading} className="px-4 py-3 font-medium">
                      {heading}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {onus.data.map((onu) => (
                  <tr key={onu.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 text-slate-800">
                      <Link className="font-medium text-primary hover:underline" href={`/onus/${onu.id}`}>
                        {onu.customer_name}
                      </Link>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-slate-700">{onu.serial_number}</td>
                    <td className="px-4 py-3 font-mono text-xs text-slate-700">{onu.onu_interface}</td>
                    <td className="px-4 py-3 text-slate-700">
                      <div className="flex flex-col gap-1">
                        <span>{onu.olt_code ? `${onu.olt_code} - ${onu.olt_name ?? ""}` : oltById.get(onu.olt_id) ?? onu.olt_id}</span>
                        <EnvironmentBadge environment={onu.olt_environment} />
                      </div>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-slate-700">
                      {onu.pon_port_id ? ponById.get(onu.pon_port_id) ?? onu.pon_port_id : ""}
                    </td>
                    <td className="px-4 py-3 text-slate-700">{onu.zone_id ? zoneById.get(onu.zone_id) : ""}</td>
                    <td className="px-4 py-3 text-slate-700">{onu.nap_id ? napById.get(onu.nap_id) : ""}</td>
                    <td className="px-4 py-3 text-slate-700">{onu.nap_port ?? ""}</td>
                    <td className="px-4 py-3 text-slate-700">{onu.vlan}</td>
                    <td className="px-4 py-3 text-slate-700">{onu.speed_profile_up ?? ""}</td>
                    <td className="px-4 py-3 text-slate-700">{onu.speed_profile_down ?? onu.speed_profile}</td>
                    <td className="px-4 py-3 text-slate-700">{formatDbm(onu.rx_power)}</td>
                    <td className="px-4 py-3 text-slate-700">{formatDbm(onu.tx_power)}</td>
                    <td className="px-4 py-3">
                      <span className={`rounded-md px-2 py-1 text-xs ${signalTone(onu.signal_status)}`}>
                        {onu.signal_status ?? ""}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-700">{formatDate(onu.last_monitored_at)}</td>
                    <td className="px-4 py-3">
                      <span className="rounded-md bg-slate-100 px-2 py-1 text-xs text-slate-700">{onu.status}</span>
                    </td>
                  </tr>
                ))}
                {!onus.data.length && (
                  <tr>
                    <td className="px-4 py-6 text-sm text-muted" colSpan={16}>
                      Sin ONUs para los filtros seleccionados.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Panel>
      </div>
    </AppShell>
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
