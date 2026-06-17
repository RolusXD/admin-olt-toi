"use client";

import { FormEvent, useMemo, useState } from "react";
import { CheckCircle2, EyeOff, Filter, RefreshCcw, RotateCcw, Search } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Panel } from "@/components/ui/panel";
import { EnvironmentBadge } from "@/components/ui/environment-badge";
import { api } from "@/services/api";
import { useApiData } from "@/hooks/useApiData";
import type { Olt, UnauthorizedOnu, UnauthorizedOnuDiscoveryResult } from "@/types";

type Filters = {
  olt_id: string;
  olt_code: string;
  serial_number: string;
  status: string;
  detected_type: string;
  detected_vendor: string;
  environment: string;
};

const emptyFilters: Filters = {
  olt_id: "",
  olt_code: "",
  serial_number: "",
  status: "",
  detected_type: "",
  detected_vendor: "",
  environment: "production",
};

export default function PendingOnusPage() {
  const olts = useApiData<Olt[]>(() => api.olts({ environment: "production" }), []);
  const [filters, setFilters] = useState<Filters>(emptyFilters);
  const [query, setQuery] = useState<Filters>(emptyFilters);
  const pending = useApiData<UnauthorizedOnu[]>(() => api.unauthorizedOnus(query), []);
  const [selectedOltId, setSelectedOltId] = useState("");
  const [showLab, setShowLab] = useState(false);
  const [discoveryResult, setDiscoveryResult] = useState<UnauthorizedOnuDiscoveryResult | null>(null);
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const selectedOlt = useMemo(
    () => olts.data.find((olt) => String(olt.id) === selectedOltId) ?? olts.data[0] ?? null,
    [olts.data, selectedOltId],
  );

  function updateFilter(field: keyof Filters, value: string) {
    setFilters((current) => ({ ...current, [field]: value }));
  }

  function applyFilters(event: FormEvent) {
    event.preventDefault();
    setQuery(filters);
  }

  function clearFilters() {
    setFilters(emptyFilters);
    setQuery(emptyFilters);
  }

  async function refreshList() {
    pending.setData(await api.unauthorizedOnus(query));
  }

  async function discover() {
    if (!selectedOlt) return;
    setError(null);
    setLoading("discover");
    try {
      const result = await api.discoverUnauthorizedOnus(selectedOlt.id);
      setDiscoveryResult(result);
      await refreshList();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "No se pudo ejecutar Discovery");
    } finally {
      setLoading(null);
    }
  }

  async function changeStatus(id: number, action: "ignore" | "restore" | "ready") {
    setError(null);
    setLoading(`${action}-${id}`);
    try {
      if (action === "ignore") await api.ignoreUnauthorizedOnu(id);
      if (action === "restore") await api.restoreUnauthorizedOnu(id);
      if (action === "ready") await api.readyUnauthorizedOnu(id);
      await refreshList();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "No se pudo actualizar estado");
    } finally {
      setLoading(null);
    }
  }

  return (
    <AppShell>
      <div className="space-y-5">
        <div>
          <h1 className="text-xl font-semibold text-slate-950">ONUs Pendientes</h1>
          <p className="text-sm text-muted">Discovery read-only de ONUs conectadas y no autorizadas.</p>
        </div>

        {error && <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">{error}</div>}

        <Panel className="p-4">
          <div className="grid gap-4 xl:grid-cols-[360px_1fr]">
            <label className="block text-sm">
              <span className="mb-1 block text-slate-700">OLT para Discovery</span>
              <select
                className="h-9 w-full rounded-md border border-slate-200 bg-white px-3 text-sm"
                value={selectedOltId || olts.data[0]?.id || ""}
                onChange={(event) => setSelectedOltId(event.target.value)}
              >
                {olts.data.map((olt) => (
                  <option key={olt.id} value={olt.id}>
                    {olt.olt_code} - {olt.display_name || olt.name}
                  </option>
                ))}
              </select>
              <label className="mt-2 inline-flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={showLab}
                  onChange={async (event) => {
                    const checked = event.target.checked;
                    setShowLab(checked);
                    olts.setData(await api.olts(checked ? {} : { environment: "production" }));
                    setFilters((current) => ({ ...current, environment: checked ? "" : "production" }));
                    setQuery((current) => ({ ...current, environment: checked ? "all" : "production" }));
                  }}
                />
                Mostrar laboratorio
              </label>
            </label>
            <div className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-950">
              Discovery solo ejecuta show gpon onu uncfg. No autoriza ONUs, no entra a configure terminal y no modifica la OLT.
            </div>
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <Button type="button" onClick={discover} disabled={!selectedOlt || loading !== null}>
              <Search className="h-4 w-4" /> Ejecutar Discovery Read-Only
            </Button>
            {discoveryResult && (
              <span className="text-sm text-slate-700">
                Detectadas {discoveryResult.detected}, nuevas {discoveryResult.new}, existentes {discoveryResult.existing}, ignoradas{" "}
                {discoveryResult.ignored}, {discoveryResult.duration_ms} ms
              </span>
            )}
            {selectedOlt && <EnvironmentBadge environment={selectedOlt.environment} />}
          </div>
        </Panel>

        <Panel className="p-4">
          <form className="grid gap-3 xl:grid-cols-[180px_180px_1fr_160px_160px_160px_150px_auto]" onSubmit={applyFilters}>
            <select
              className="h-9 rounded-md border border-slate-200 bg-white px-3 text-sm"
              value={filters.olt_id}
              onChange={(event) => updateFilter("olt_id", event.target.value)}
            >
              <option value="">OLT</option>
              {olts.data.map((olt) => (
                <option key={olt.id} value={olt.id}>
                  {olt.olt_code} - {olt.name}
                </option>
              ))}
            </select>
            <Input placeholder="Codigo OLT" value={filters.olt_code} onChange={(event) => updateFilter("olt_code", event.target.value.toUpperCase())} />
            <Input placeholder="Serial" value={filters.serial_number} onChange={(event) => updateFilter("serial_number", event.target.value)} />
            <select
              className="h-9 rounded-md border border-slate-200 bg-white px-3 text-sm"
              value={filters.status}
              onChange={(event) => updateFilter("status", event.target.value)}
            >
              <option value="">Estado</option>
              <option value="pending">Pendiente</option>
              <option value="ignored">Ignorada</option>
              <option value="ready_for_provisioning">Lista</option>
              <option value="provisioned">Provisionada</option>
            </select>
            <Input placeholder="Tipo ONU" value={filters.detected_type} onChange={(event) => updateFilter("detected_type", event.target.value)} />
            <Input placeholder="Fabricante" value={filters.detected_vendor} onChange={(event) => updateFilter("detected_vendor", event.target.value)} />
            <select
              className="h-9 rounded-md border border-slate-200 bg-white px-3 text-sm"
              value={filters.environment}
              onChange={(event) => updateFilter("environment", event.target.value)}
            >
              <option value="production">Produccion</option>
              <option value="lab">Laboratorio</option>
              <option value="all">Todos</option>
            </select>
            <div className="flex gap-2">
              <Button type="submit">
                <Filter className="h-4 w-4" /> Filtrar
              </Button>
              <Button type="button" variant="secondary" onClick={clearFilters}>
                <RefreshCcw className="h-4 w-4" />
              </Button>
            </div>
          </form>
        </Panel>

        <Panel className="overflow-hidden">
          <div className="border-b border-slate-200 px-4 py-3">
            <h2 className="text-sm font-semibold text-slate-950">Bandeja Discovery</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1320px] text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase text-muted">
                <tr>
                  {[
                    "OLT Code",
                    "OLT",
                    "Tipo PON",
                    "Tarjeta",
                    "Puerto",
                    "Serial",
                    "Tipo Detectado",
                    "Fabricante",
                    "Primera deteccion",
                    "Ultima deteccion",
                    "Veces",
                    "Estado",
                    "Acciones",
                  ].map((heading) => (
                    <th key={heading} className="px-4 py-3 font-medium">
                      {heading}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {pending.data.map((onu) => (
                  <tr key={onu.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 font-mono text-xs text-slate-700">{onu.olt_code ?? onu.olt_code_snapshot}</td>
                    <td className="px-4 py-3 text-slate-700">
                      <div className="flex flex-col gap-1">
                        <span>{onu.olt_name}</span>
                        <EnvironmentBadge environment={onu.olt_environment} />
                      </div>
                    </td>
                    <td className="px-4 py-3 text-slate-700">{onu.pon_type ?? ""}</td>
                    <td className="px-4 py-3 text-slate-700">{onu.slot ?? ""}</td>
                    <td className="px-4 py-3 text-slate-700">{onu.port ?? ""}</td>
                    <td className="px-4 py-3 font-mono text-xs text-slate-700">{onu.serial_number}</td>
                    <td className="px-4 py-3 text-slate-700">{onu.detected_type ?? ""}</td>
                    <td className="px-4 py-3 text-slate-700">{onu.detected_vendor ?? ""}</td>
                    <td className="px-4 py-3 text-slate-700">{formatDate(onu.first_seen_at)}</td>
                    <td className="px-4 py-3 text-slate-700">{formatDate(onu.last_seen_at)}</td>
                    <td className="px-4 py-3 text-slate-700">{onu.times_detected}</td>
                    <td className="px-4 py-3">
                      <span className={`rounded-md px-2 py-1 text-xs ${statusTone(onu.status)}`}>{statusLabel(onu.status)}</span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-2">
                        <Button type="button" variant="secondary" onClick={() => changeStatus(onu.id, "restore")} disabled={loading !== null || onu.status === "pending"}>
                          <RotateCcw className="h-4 w-4" /> Pendiente
                        </Button>
                        <Button type="button" variant="secondary" onClick={() => changeStatus(onu.id, "ignore")} disabled={loading !== null || onu.status === "ignored"}>
                          <EyeOff className="h-4 w-4" /> Ignorar
                        </Button>
                        <Button type="button" onClick={() => changeStatus(onu.id, "ready")} disabled={loading !== null || onu.status === "ready_for_provisioning"}>
                          <CheckCircle2 className="h-4 w-4" /> Lista
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
                {!pending.data.length && (
                  <tr>
                    <td className="px-4 py-6 text-sm text-muted" colSpan={13}>
                      Sin ONUs pendientes para los filtros seleccionados.
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

function formatDate(value?: string | null) {
  return value ? new Date(value).toLocaleString() : "";
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    pending: "Pendiente",
    ignored: "Ignorada",
    ready_for_provisioning: "Lista",
    provisioned: "Provisionada",
  };
  return labels[status] ?? status;
}

function statusTone(status: string) {
  if (status === "ready_for_provisioning") return "bg-emerald-100 text-emerald-800";
  if (status === "ignored") return "bg-slate-100 text-slate-700";
  if (status === "provisioned") return "bg-blue-100 text-blue-800";
  return "bg-amber-100 text-amber-800";
}
