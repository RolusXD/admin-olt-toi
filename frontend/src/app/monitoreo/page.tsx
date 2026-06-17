"use client";

import { FormEvent, useEffect, useState } from "react";
import { Filter, RefreshCcw } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Panel } from "@/components/ui/panel";
import { EnvironmentBadge } from "@/components/ui/environment-badge";
import { api } from "@/services/api";
import { useApiData } from "@/hooks/useApiData";
import type { MonitoringExecution, Olt } from "@/types";

export default function MonitoringPage() {
  const olts = useApiData<Olt[]>(() => api.olts({ environment: "production" }), []);
  const [filters, setFilters] = useState({ olt_id: "", olt_code: "", environment: "production", task_type: "", date_from: "", date_to: "" });
  const [showLab, setShowLab] = useState(false);
  const [executions, setExecutions] = useState<MonitoringExecution[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function loadExecutions(params: Record<string, string> = {}) {
    setError(null);
    try {
      setExecutions(await api.monitoringExecutions(params));
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "No se pudo cargar el monitoreo");
    }
  }

  useEffect(() => {
    loadExecutions();
  }, []);

  function applyFilters(event: FormEvent) {
    event.preventDefault();
    loadExecutions({
      olt_id: filters.olt_id,
      olt_code: filters.olt_code,
      environment: filters.environment,
      task_type: filters.task_type,
      date_from: filters.date_from ? `${filters.date_from}T00:00:00Z` : "",
      date_to: filters.date_to ? `${filters.date_to}T23:59:59Z` : "",
    });
  }

  function refresh() {
    loadExecutions();
  }

  return (
    <AppShell>
      <div className="space-y-5">
        <div>
          <h1 className="text-xl font-semibold text-slate-950">Monitoreo</h1>
          <p className="text-sm text-muted">Historial operativo de sincronizaciones read-only.</p>
        </div>

        {error && <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">{error}</div>}

        <Panel className="p-4">
          <form className="grid gap-3 lg:grid-cols-[1fr_180px_150px_160px_160px_160px_auto_auto]" onSubmit={applyFilters}>
            <label className="block text-sm">
              <span className="mb-1 block text-slate-700">OLT</span>
              <select
                className="h-9 w-full rounded-md border border-slate-200 bg-white px-3 text-sm"
                value={filters.olt_id}
                onChange={(event) => setFilters((current) => ({ ...current, olt_id: event.target.value }))}
              >
                <option value="">Todas</option>
                {olts.data.map((olt) => (
                  <option key={olt.id} value={olt.id}>
                    {olt.olt_code} - {olt.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-slate-700">Entorno</span>
              <select
                className="h-9 w-full rounded-md border border-slate-200 bg-white px-3 text-sm"
                value={filters.environment}
                onChange={(event) => setFilters((current) => ({ ...current, environment: event.target.value }))}
              >
                <option value="production">Produccion</option>
                <option value="lab">Laboratorio</option>
                <option value="">Todos</option>
              </select>
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-slate-700">Codigo OLT</span>
              <Input
                value={filters.olt_code}
                onChange={(event) => setFilters((current) => ({ ...current, olt_code: event.target.value.toUpperCase() }))}
                placeholder="OLT-PCM-ZTE-01"
              />
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-slate-700">Tipo</span>
              <select
                className="h-9 w-full rounded-md border border-slate-200 bg-white px-3 text-sm"
                value={filters.task_type}
                onChange={(event) => setFilters((current) => ({ ...current, task_type: event.target.value }))}
              >
                <option value="">Todos</option>
                <option value="sync_onus">sync_onus</option>
                <option value="sync_power">sync_power</option>
              </select>
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-slate-700">Desde</span>
              <Input
                type="date"
                value={filters.date_from}
                onChange={(event) => setFilters((current) => ({ ...current, date_from: event.target.value }))}
              />
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-slate-700">Hasta</span>
              <Input
                type="date"
                value={filters.date_to}
                onChange={(event) => setFilters((current) => ({ ...current, date_to: event.target.value }))}
              />
            </label>
            <div className="flex items-end">
              <Button type="submit">
                <Filter className="h-4 w-4" /> Filtrar
              </Button>
            </div>
            <label className="flex items-end gap-2 pb-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={showLab}
                onChange={async (event) => {
                  const checked = event.target.checked;
                  setShowLab(checked);
                  olts.setData(await api.olts(checked ? {} : { environment: "production" }));
                  setFilters((current) => ({ ...current, environment: checked ? "" : "production" }));
                }}
              />
              Mostrar laboratorio
            </label>
            <div className="flex items-end">
              <Button type="button" variant="secondary" onClick={refresh}>
                <RefreshCcw className="h-4 w-4" /> Actualizar
              </Button>
            </div>
          </form>
        </Panel>

        <Panel className="overflow-hidden">
          <div className="border-b border-slate-200 px-4 py-3">
            <h2 className="text-sm font-semibold text-slate-950">Ejecuciones</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[820px] text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase text-muted">
                <tr>
                  <th className="px-4 py-3">Fecha</th>
                  <th className="px-4 py-3">Tipo</th>
                  <th className="px-4 py-3">Duracion</th>
                  <th className="px-4 py-3">Procesadas</th>
                  <th className="px-4 py-3">Correctas</th>
                  <th className="px-4 py-3">Errores</th>
                  <th className="px-4 py-3">OLT</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {executions.map((execution) => (
                  <tr key={execution.id}>
                    <td className="px-4 py-3 text-slate-700">{new Date(execution.started_at).toLocaleString()}</td>
                    <td className="px-4 py-3 font-mono text-xs text-slate-800">{execution.task_type}</td>
                    <td className="px-4 py-3 text-slate-700">{execution.duration_ms ?? 0} ms</td>
                    <td className="px-4 py-3 text-slate-700">{execution.processed_count}</td>
                    <td className="px-4 py-3 text-slate-700">{execution.success_count}</td>
                    <td className="px-4 py-3 text-slate-700">{execution.error_count}</td>
                    <td className="px-4 py-3 text-slate-700">
                      <div className="flex flex-col gap-1">
                        <span>{execution.olt_code ? `${execution.olt_code} - ${execution.olt_name ?? ""}` : olts.data.find((olt) => olt.id === execution.olt_id)?.name ?? execution.olt_id}</span>
                        <EnvironmentBadge environment={execution.olt_environment} />
                      </div>
                    </td>
                  </tr>
                ))}
                {!executions.length && (
                  <tr>
                    <td className="px-4 py-6 text-sm text-muted" colSpan={7}>
                      Sin ejecuciones registradas.
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
