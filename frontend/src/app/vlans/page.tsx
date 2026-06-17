"use client";

import { FormEvent } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { DataTable } from "@/components/modules/DataTable";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Panel } from "@/components/ui/panel";
import { api } from "@/services/api";
import { useApiData } from "@/hooks/useApiData";
import type { Olt, Vlan } from "@/types";

export default function VlansPage() {
  const olts = useApiData<Olt[]>(() => api.olts({ environment: "production" }), []);
  const items = useApiData<Vlan[]>(() => api.vlans({ is_active: 1 }), []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await api.createVlan({
      olt_id: Number(form.get("olt_id")),
      vlan_id: Number(form.get("vlan_id")),
      name: String(form.get("name") || ""),
      description: String(form.get("description") || ""),
      service_type: String(form.get("service_type") || "internet"),
      source: "manual",
    });
    window.location.reload();
  }

  return (
    <AppShell>
      <div className="space-y-5">
        <div>
          <h2 className="text-2xl font-semibold text-slate-950">VLANs</h2>
          <p className="mt-1 text-sm text-muted">Catalogo interno de VLANs importadas o manuales. No crea VLANs en la OLT.</p>
        </div>
        <Panel className="p-4">
          <form className="grid gap-3 md:grid-cols-5" onSubmit={submit}>
            <select name="olt_id" className="h-9 rounded-md border border-slate-200 bg-white px-3 text-sm" required>
              <option value="">OLT</option>
              {olts.data.map((olt) => <option key={olt.id} value={olt.id}>{olt.olt_code}</option>)}
            </select>
            <Input name="vlan_id" placeholder="VLAN ID" type="number" required />
            <Input name="name" placeholder="Nombre" />
            <Input name="description" placeholder="Descripcion" />
            <select name="service_type" className="h-9 rounded-md border border-slate-200 bg-white px-3 text-sm">
              {["internet", "iptv", "voip", "management", "other"].map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
            <Button className="md:col-span-5">Guardar VLAN</Button>
          </form>
        </Panel>
        <DataTable
          title="VLANs activas"
          items={items.data}
          columns={[
            { key: "olt_code", label: "OLT Code" },
            { key: "vlan_id", label: "VLAN" },
            { key: "name", label: "Nombre" },
            { key: "description", label: "Descripcion" },
            { key: "service_type", label: "Servicio" },
            { key: "source", label: "Source" },
            { key: "is_active", label: "Estado", render: (item) => (item.is_active ? "Activo" : "Inactivo") },
          ]}
        />
      </div>
    </AppShell>
  );
}
