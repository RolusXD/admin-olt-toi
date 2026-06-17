"use client";

import { RefreshCcw, Search } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { SummaryCards } from "@/components/dashboard/SummaryCards";
import { PowerChart } from "@/components/dashboard/PowerChart";
import { DataTable } from "@/components/modules/DataTable";
import { QuickCreateForms } from "@/components/modules/Forms";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/services/api";
import { useApiData } from "@/hooks/useApiData";
import { EnvironmentBadge } from "@/components/ui/environment-badge";
import type { DashboardEnvironmentSummary, DashboardSummary, Nap, Olt, Onu, Zone } from "@/types";

const emptySummary: DashboardSummary = {
  online: 0,
  offline: 0,
  unauthorized: 0,
  low_signal: 0,
  los: 0,
  dying_gasp: 0,
  pwr_fail: 0,
  rx_warning: 0,
  rx_critical: 0,
  unauthorized_pending: 0,
  unauthorized_ignored: 0,
  unauthorized_ready_for_provisioning: 0,
  provisioning_draft: 0,
  provisioning_validated: 0,
  provisioning_approved: 0,
  provisioning_cancelled: 0,
};

const demoOnus: Onu[] = [
  {
    id: 1,
    olt_id: 1,
    customer_name: "Cliente Piloto",
    serial_number: "ZTEG12345678",
    onu_interface: "gpon-onu_1/2/1:1",
    onu_type: "F660",
    vlan: 100,
    speed_profile: "50M",
    status: "online",
    last_down_cause: null,
    distance_m: 820,
    nap_port: 1,
  },
];

export default function Home() {
  const summary = useApiData(() => api.summary({ environment: "production" }), emptySummary);
  const envSummary = useApiData<DashboardEnvironmentSummary>(api.environmentSummary, {
    production: { environment: "production", olts: 0, onus: 0, online: 0 },
    lab: { environment: "lab", olts: 0, onus: 0, online: 0 },
  });
  const olts = useApiData<Olt[]>(() => api.olts({ environment: "production" }), []);
  const zones = useApiData<Zone[]>(api.zones, []);
  const naps = useApiData<Nap[]>(api.naps, []);
  const onus = useApiData<Onu[]>(() => api.onus({ environment: "production" }), demoOnus);

  function refresh() {
    window.location.reload();
  }

  return (
    <AppShell>
      <div className="space-y-5">
        {(summary.error || olts.error) && (
          <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            API no disponible. La interfaz queda cargada con datos de referencia mientras se inicia el backend.
          </div>
        )}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="relative w-full sm:max-w-sm">
            <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted" />
            <Input className="pl-9" placeholder="Buscar cliente, serial, ONU, zona, NAP u OLT" />
          </div>
          <Button variant="secondary" onClick={refresh}>
            <RefreshCcw className="h-4 w-4" /> Actualizar
          </Button>
        </div>

        <SummaryCards summary={summary.data} />

        <section className="grid gap-3 md:grid-cols-2">
          <EnvironmentStats title="Produccion" stats={envSummary.data.production} />
          <EnvironmentStats title="Laboratorio" stats={envSummary.data.lab} />
        </section>

        <section className="grid gap-3 md:grid-cols-2">
          <LastSyncCard title="Ultima sincronizacion ONUs" execution={summary.data.last_sync_onus} />
          <LastSyncCard title="Ultima sincronizacion potencia" execution={summary.data.last_sync_power} />
        </section>

        <div className="grid gap-5 xl:grid-cols-[1fr_420px]">
          <div className="space-y-5">
            <DataTable
              title="ONUs"
              items={onus.data}
              columns={[
                { key: "customer_name", label: "Cliente" },
                { key: "serial_number", label: "Serial" },
                { key: "onu_interface", label: "ONU Interface" },
                { key: "status", label: "Estado" },
                { key: "vlan", label: "VLAN" },
                { key: "speed_profile", label: "Perfil" },
                { key: "distance_m", label: "Distancia" },
              ]}
            />
          </div>
          <div className="space-y-5">
            <PowerChart />
            <DataTable
              title="OLTs"
              items={olts.data}
              columns={[
                { key: "olt_code", label: "Codigo OLT" },
                { key: "name", label: "Nombre" },
                { key: "environment", label: "Entorno" },
                { key: "initial_import_status", label: "Importacion" },
                { key: "ip_address", label: "IP" },
                { key: "status", label: "Estado" },
              ]}
            />
          </div>
        </div>

        <QuickCreateForms onDone={refresh} />

        <div className="grid gap-5 xl:grid-cols-2">
          <DataTable
            title="Zonas"
            items={zones.data}
            columns={[
              { key: "name", label: "Nombre" },
              { key: "description", label: "Descripcion" },
            ]}
          />
          <DataTable
            title="NAPs / ODN"
            items={naps.data}
            columns={[
              { key: "name", label: "Nombre" },
              { key: "zone_id", label: "Zona" },
              { key: "capacity", label: "Capacidad" },
            ]}
          />
        </div>
      </div>
    </AppShell>
  );
}

function EnvironmentStats({
  title,
  stats,
}: {
  title: string;
  stats: DashboardEnvironmentSummary["production"];
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-panel">
      <div className="mb-3 flex items-center justify-between">
        <div className="text-sm font-semibold text-slate-950">{title}</div>
        <EnvironmentBadge environment={stats.environment} />
      </div>
      <div className="grid grid-cols-3 gap-3 text-sm">
        <div>
          <div className="text-xs text-muted">OLTs</div>
          <div className="mt-1 text-lg font-semibold text-slate-950">{stats.olts}</div>
        </div>
        <div>
          <div className="text-xs text-muted">ONUs</div>
          <div className="mt-1 text-lg font-semibold text-slate-950">{stats.onus}</div>
        </div>
        <div>
          <div className="text-xs text-muted">Online</div>
          <div className="mt-1 text-lg font-semibold text-slate-950">{stats.online}</div>
        </div>
      </div>
    </div>
  );
}

function LastSyncCard({
  title,
  execution,
}: {
  title: string;
  execution?: DashboardSummary["last_sync_onus"];
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-panel">
      <div className="text-sm font-semibold text-slate-950">{title}</div>
      {execution ? (
        <div className="mt-3 grid gap-3 text-sm sm:grid-cols-4">
          <div>
            <div className="text-xs text-muted">OLT</div>
            <div className="mt-1 text-slate-800">{execution.olt_code ?? execution.olt_id}</div>
          </div>
          <div>
            <div className="text-xs text-muted">Fecha</div>
            <div className="mt-1 text-slate-800">{new Date(execution.started_at).toLocaleString()}</div>
          </div>
          <div>
            <div className="text-xs text-muted">Duracion</div>
            <div className="mt-1 text-slate-800">{execution.duration_ms ?? 0} ms</div>
          </div>
          <div>
            <div className="text-xs text-muted">Procesadas</div>
            <div className="mt-1 text-slate-800">{execution.processed_count}</div>
          </div>
        </div>
      ) : (
        <div className="mt-3 text-sm text-muted">Sin ejecuciones registradas.</div>
      )}
    </div>
  );
}
