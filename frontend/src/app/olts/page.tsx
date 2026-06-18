"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { Eye, Plus, RefreshCw, Save } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/button";
import { EnvironmentBadge } from "@/components/ui/environment-badge";
import { Input } from "@/components/ui/input";
import { Panel } from "@/components/ui/panel";
import { api } from "@/services/api";
import { useApiData } from "@/hooks/useApiData";
import type { Olt } from "@/types";

export default function OltsPage() {
  const [showLab, setShowLab] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const olts = useApiData<Olt[]>(() => api.olts(showLab ? {} : { environment: "production" }), [], [showLab, reloadKey]);

  async function createOlt(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setMessage(null);
    const form = new FormData(event.currentTarget);
    try {
      await api.createOlt({
        olt_code: String(form.get("olt_code") ?? "").trim(),
        name: String(form.get("name") ?? "").trim(),
        ip_address: String(form.get("ip_address") ?? "").trim(),
        telnet_port: Number(form.get("telnet_port") || 23),
        username: String(form.get("username") ?? "").trim(),
        password: String(form.get("password") ?? ""),
        snmp_ro_community: String(form.get("snmp_ro_community") ?? ""),
        snmp_rw_community: String(form.get("snmp_rw_community") ?? ""),
        snmp_udp_port: Number(form.get("snmp_udp_port") || 161),
        vendor: String(form.get("vendor") ?? "ZTE"),
        hardware_version: String(form.get("hardware_version") ?? ""),
        software_version: String(form.get("software_version") ?? ""),
        firmware: String(form.get("software_version") ?? "V1.2.5P3"),
        model: "C300",
        pon_supported_types: String(form.get("pon_supported_types") ?? "GPON"),
        environment: String(form.get("environment") ?? "production"),
        connection_type: "telnet",
        status: "unknown",
      });
      event.currentTarget.reset();
      setShowForm(false);
      setReloadKey((value) => value + 1);
      setMessage("OLT guardada.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo guardar la OLT.");
    }
  }

  return (
    <AppShell>
      <div className="space-y-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h2 className="text-2xl font-semibold text-slate-950">OLTs</h2>
            <p className="mt-1 text-sm text-muted">Gestion tecnica interna de OLTs. Sin comandos de configuracion.</p>
          </div>
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setReloadKey((value) => value + 1)}><RefreshCw className="h-4 w-4" /> Refrescar</Button>
            <Button onClick={() => setShowForm((value) => !value)}><Plus className="h-4 w-4" /> Agregar OLT</Button>
          </div>
        </div>

        <label className="flex items-center gap-2 text-sm text-slate-700"><input type="checkbox" checked={showLab} onChange={(event) => setShowLab(event.target.checked)} /> Mostrar laboratorio</label>
        {message && <div className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">{message}</div>}
        {error && <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">{error}</div>}

        {showForm && (
          <Panel className="p-4">
            <form className="grid gap-3 md:grid-cols-4" onSubmit={createOlt}>
              <Input name="olt_code" placeholder="OLT Code" required />
              <Input name="name" placeholder="Nombre" required />
              <Input name="ip_address" placeholder="IP del OLT o FQDN" required />
              <Input name="telnet_port" type="number" defaultValue={23} placeholder="TCP Telnet" required />
              <Input name="username" placeholder="Usuario Telnet" required />
              <Input name="password" type="password" placeholder="Contrasena Telnet" required />
              <Input name="snmp_ro_community" type="password" placeholder="SNMP readonly community" />
              <Input name="snmp_rw_community" type="password" placeholder="SNMP readwrite community" />
              <Input name="snmp_udp_port" type="number" defaultValue={161} placeholder="UDP SNMP" />
              <Input name="vendor" defaultValue="ZTE" placeholder="Fabricante" />
              <Input name="hardware_version" placeholder="Version hardware OLT" />
              <Input name="software_version" defaultValue="V1.2.5P3" placeholder="Version software OLT" />
              <select name="pon_supported_types" className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm" defaultValue="GPON">
                <option value="GPON">GPON</option>
                <option value="EPON">EPON</option>
                <option value="GPON+EPON">GPON+EPON</option>
              </select>
              <select name="environment" className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm" defaultValue="production">
                <option value="production">Produccion</option>
                <option value="lab">Laboratorio</option>
              </select>
              <Button className="md:col-span-2"><Save className="h-4 w-4" /> Guardar OLT</Button>
            </form>
          </Panel>
        )}

        <Panel className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1200px] text-left text-sm">
              <thead className="bg-slate-50 text-slate-950">
                <tr>
                  <th className="px-4 py-3">Ver</th>
                  <th className="px-4 py-3">ID interno</th>
                  <th className="px-4 py-3">OLT Code</th>
                  <th className="px-4 py-3">Entorno</th>
                  <th className="px-4 py-3">Estado</th>
                  <th className="px-4 py-3">Nombre</th>
                  <th className="px-4 py-3">IP del OLT</th>
                  <th className="px-4 py-3">TCP</th>
                  <th className="px-4 py-3">UDP</th>
                  <th className="px-4 py-3">Vendor</th>
                  <th className="px-4 py-3">Version hardware</th>
                  <th className="px-4 py-3">Version software</th>
                  <th className="px-4 py-3">Accion</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {olts.data.map((olt) => (
                  <tr key={olt.id} className="odd:bg-white even:bg-slate-50/70">
                    <td className="px-4 py-3"><Link href={`/olts/${olt.id}`} className="inline-flex text-primary"><Eye className="h-4 w-4" /></Link></td>
                    <td className="px-4 py-3">{olt.id}</td>
                    <td className="px-4 py-3 font-medium text-primary">{olt.olt_code}</td>
                    <td className="px-4 py-3"><EnvironmentBadge environment={olt.environment} /></td>
                    <td className="px-4 py-3">{olt.status}</td>
                    <td className="px-4 py-3">{olt.name}</td>
                    <td className="px-4 py-3">{olt.ip_address}</td>
                    <td className="px-4 py-3">{olt.telnet_port}</td>
                    <td className="px-4 py-3">{olt.snmp_udp_port}</td>
                    <td className="px-4 py-3">{olt.vendor}</td>
                    <td className="px-4 py-3">{olt.hardware_version ?? "-"}</td>
                    <td className="px-4 py-3">{olt.software_version ?? olt.firmware}</td>
                    <td className="px-4 py-3"><Link href={`/olts/${olt.id}`} className="text-primary">Detalle</Link></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      </div>
    </AppShell>
  );
}
