"use client";

import { useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/button";
import { EnvironmentBadge } from "@/components/ui/environment-badge";
import { Panel } from "@/components/ui/panel";
import { api } from "@/services/api";
import { useApiData } from "@/hooks/useApiData";
import type { OltCard, OltTechnicalSettings, OltUplink, PonPort, Vlan } from "@/types";

type Tab = "details" | "cards" | "pon" | "uplinks" | "vlans" | "advanced";

export default function OltDetailPage() {
  const params = useParams<{ id: string }>();
  const oltId = params.id;
  const [tab, setTab] = useState<Tab>("details");
  const [reloadKey, setReloadKey] = useState(0);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);
  const [syncError, setSyncError] = useState<string | null>(null);
  const olt = useApiData(() => api.olt(oltId), null, [oltId, reloadKey]);
  const inventory = useApiData(() => api.oltInventorySummary(oltId), null, [oltId, reloadKey]);
  const cards = useApiData<OltCard[]>(() => api.oltCards(oltId), [], [oltId, reloadKey]);
  const ponPorts = useApiData<PonPort[]>(() => api.oltPonPorts(oltId), [], [oltId, reloadKey]);
  const uplinks = useApiData<OltUplink[]>(() => api.oltUplinks(oltId), [], [oltId, reloadKey]);
  const vlans = useApiData<Vlan[]>(() => api.oltVlans(oltId), [], [oltId, reloadKey]);
  const advanced = useApiData<OltTechnicalSettings | null>(() => api.oltAdvanced(oltId), null, [oltId, reloadKey]);

  const current = olt.data;
  const title = current ? `${current.olt_code} - ${current.name}` : "OLT";
  const tabs = useMemo(
    () => [
      ["details", "Detalles del OLT"],
      ["cards", "Tarjetas OLT"],
      ["pon", "Puertos PON"],
      ["uplinks", "Uplink"],
      ["vlans", "VLANs"],
      ["advanced", "Configuracion avanzada"],
    ] as Array<[Tab, string]>,
    [],
  );

  async function runAction(action: "cards" | "pon" | "uplinks") {
    setSyncMessage(null);
    setSyncError(null);
    try {
      const result =
        action === "cards"
          ? await api.syncCards(oltId)
          : action === "pon"
            ? await api.syncPonStatus(oltId)
            : await api.syncUplinks(oltId);
      setSyncMessage("Comando read-only ejecutado y registrado.");
      setReloadKey((value) => value + 1);
    } catch (err) {
      setSyncError(err instanceof Error ? err.message : "No se pudo ejecutar la accion read-only.");
    }
  }

  return (
    <AppShell>
      <div className="space-y-5">
        <div>
          <h2 className="text-2xl font-semibold text-slate-950">{title}</h2>
          <p className="mt-1 text-sm text-muted">Gestion tecnica interna. Sin acciones de configuracion sobre la OLT.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {tabs.map(([value, label]) => (
            <button key={value} type="button" onClick={() => setTab(value)} className={`h-10 rounded-md border px-4 text-sm font-medium ${tab === value ? "border-slate-950 bg-slate-950 text-white" : "border-slate-200 bg-white text-slate-700"}`}>
              {label}
            </button>
          ))}
        </div>
        {syncMessage && <div className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">{syncMessage}</div>}
        {syncError && <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">{syncError}</div>}

        {tab === "details" && current && (
          <Panel className="p-4">
            <div className="grid gap-4 md:grid-cols-3">
              <Field label="Nombre" value={current.name} />
              <Field label="OLT Code" value={current.olt_code} />
              <div><div className="text-xs text-muted">Entorno</div><EnvironmentBadge environment={current.environment} /></div>
              <Field label="IP" value={current.ip_address} />
              <Field label="Puerto Telnet" value={current.telnet_port} />
              <Field label="Usuario Telnet" value={current.username ? "Oculto" : "-"} />
              <Field label="Contrasena" value={current.has_password ? "Oculta" : "No registrada"} />
              <Field label="SNMP" value="Oculto" />
              <Field label="Puerto UDP SNMP" value={current.snmp_udp_port} />
              <Field label="Vendor" value={current.vendor} />
              <Field label="Hardware" value={current.hardware_version ?? "-"} />
              <Field label="Firmware" value={current.software_version ?? current.firmware} />
              <Field label="Tipos PON soportados" value={current.pon_supported_types} />
              <Field label="Estado de importacion" value={current.initial_import_status} />
              <Field label="Ultima importacion" value={current.last_import_confirmed_at ?? "-"} />
              <Field label="Ultimo monitoreo" value="Ver modulo Monitoreo" />
            </div>
            {inventory.data && (
              <div className="mt-4 grid gap-3 md:grid-cols-4">
                <Metric label="ONUs" value={inventory.data.onus} />
                <Metric label="PON" value={inventory.data.pon_ports} />
                <Metric label="VLANs" value={inventory.data.vlans} />
                <Metric label="Perfiles" value={inventory.data.profiles} />
              </div>
            )}
          </Panel>
        )}

        {tab === "cards" && (
          <div className="space-y-3">
            <Button variant="secondary" onClick={() => void runAction("cards")}>Sync Tarjetas Read-Only</Button>
            <SimpleTable columns={["Ranura", "Tipo", "Tipo real", "Puertos", "SW", "Estado", "Rol", "Ultima actualizacion", "Origen"]} rows={cards.data.map((card) => [card.slot_number, card.card_type ?? "-", card.real_type ?? "-", card.port_count ?? "-", card.firmware ?? "-", card.status, card.role ?? "-", card.last_sync_at ?? card.last_seen_at ?? "-", card.sync_source ?? "-"])} />
          </div>
        )}
        {tab === "pon" && (
          <div className="space-y-3">
            <Button variant="secondary" onClick={() => void runAction("pon")}>Sync PON Read-Only</Button>
            <SimpleTable columns={["Puerto", "Tipo", "Admin", "Estado", "Online", "Offline", "Total", "Ocupacion", "Ultima sync", "Origen", "Senal promedio"]} rows={ponPorts.data.map((port) => [port.interface_name ?? "-", port.pon_type ?? "GPON", port.admin_status ?? "unknown", port.oper_status ?? "unknown", port.online_count ?? port.online_onus ?? 0, port.offline_count ?? 0, port.total_count ?? port.total_onus ?? 0, `${port.occupancy_percent ?? port.load_percent ?? 0}%`, port.last_sync_at ?? "-", port.sync_source ?? "-", port.avg_rx_power ?? "-"])} />
          </div>
        )}
        {tab === "uplinks" && (
          <div className="space-y-3">
            <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950">Esta accion solo ejecuta show interface y no modifica la OLT.</div>
            <Button variant="secondary" onClick={() => void runAction("uplinks")}>Sync Uplinks Read-Only</Button>
            <SimpleTable columns={["Puerto uplink", "Descripcion", "Tipo", "Estado administrativo", "Estado", "Line protocol", "Velocidad", "MTU", "PVID untag", "Modo", "VLANs etiquetadas / permitidas", "Ultima actualizacion"]} rows={uplinks.data.map((uplink) => [uplink.interface_name, uplink.description ?? "-", uplink.interface_type ?? "-", uplink.admin_status, uplink.oper_status, uplink.line_protocol ?? "-", formatKbps(uplink.speed_kbps), uplink.mtu ?? "-", uplink.pvid_untag ?? "-", uplink.mode ?? "-", uplink.allowed_vlans ?? "-", uplink.last_seen_at ?? "-"])} />
          </div>
        )}
        {tab === "vlans" && <SimpleTable columns={["VLAN-ID", "Descripcion", "ONUs", "Usado IPTV", "Usado Gestion/VoIP", "DHCP Snooping", "LAN a LAN", "Estado"]} rows={vlans.data.map((vlan) => [vlan.vlan_id, vlan.description ?? vlan.name ?? "-", vlan.onu_count ?? 0, boolText(vlan.used_iptv), boolText(vlan.used_management_voip), boolText(vlan.dhcp_snooping), boolText(vlan.lan_to_lan), vlan.is_active ? "Activa" : "Inactiva"])} />}
        {tab === "advanced" && advanced.data && (
          <Panel className="p-4">
            <div className="grid gap-4 md:grid-cols-3">
              {Object.entries(advanced.data).filter(([key]) => !["id", "olt_id"].includes(key)).map(([key, value]) => <Field key={key} label={key} value={String(value)} />)}
            </div>
          </Panel>
        )}
      </div>
    </AppShell>
  );
}

function Field({ label, value }: { label: string; value: string | number }) {
  return <div><div className="text-xs text-muted">{label}</div><div className="mt-1 font-medium text-slate-950">{value}</div></div>;
}

function Metric({ label, value }: { label: string; value: number }) {
  return <div className="rounded-md border border-slate-200 p-3"><div className="text-xs text-muted">{label}</div><div className="text-xl font-semibold text-slate-950">{value}</div></div>;
}

function SimpleTable({ columns, rows }: { columns: string[]; rows: Array<Array<string | number>> }) {
  return (
    <Panel className="overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[900px] text-left text-sm">
          <thead className="bg-slate-50 text-slate-950"><tr>{columns.map((column) => <th key={column} className="px-4 py-3">{column}</th>)}</tr></thead>
          <tbody className="divide-y divide-slate-100">
            {rows.map((row, index) => <tr key={index} className="odd:bg-white even:bg-slate-50/70">{row.map((cell, cellIndex) => <td key={cellIndex} className="px-4 py-3">{cell}</td>)}</tr>)}
            {!rows.length && <tr><td className="px-4 py-6 text-center text-muted" colSpan={columns.length}>Sin registros.</td></tr>}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function boolText(value: unknown) {
  return value ? "Si" : "No";
}

function formatKbps(value?: number | null) {
  if (!value) {
    return "-";
  }
  if (value >= 1000000) {
    return `${value / 1000000} Gbps`;
  }
  if (value >= 1000) {
    return `${value / 1000} Mbps`;
  }
  return `${value} Kbps`;
}
