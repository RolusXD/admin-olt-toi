"use client";

import { FormEvent } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { DataTable } from "@/components/modules/DataTable";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Panel } from "@/components/ui/panel";
import { api } from "@/services/api";
import { useApiData } from "@/hooks/useApiData";
import type { Olt, OnuType } from "@/types";

export default function OnuTypesPage() {
  const olts = useApiData<Olt[]>(() => api.olts({ environment: "production" }), []);
  const items = useApiData<OnuType[]>(() => api.onuTypes({ is_active: 1 }), []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await api.createOnuType({
      olt_id: Number(form.get("olt_id")),
      name: String(form.get("name")),
      vendor_detected: String(form.get("vendor_detected") || ""),
      technology: String(form.get("technology") || "GPON"),
      ethernet_ports: Number(form.get("ethernet_ports") || 0) || null,
      wifi_ports: Number(form.get("wifi_ports") || 0) || null,
      pots_ports: Number(form.get("pots_ports") || 0) || null,
      source: "manual",
    });
    window.location.reload();
  }

  return (
    <AppShell>
      <div className="space-y-5">
        <Header title="Tipos de ONU" subtitle="Catalogo interno para seleccionar equipos compatibles en aprovisionamiento." />
        <Panel className="p-4">
          <form className="grid gap-3 md:grid-cols-6" onSubmit={submit}>
            <OltSelect olts={olts.data} />
            <Input name="name" placeholder="Nombre" required />
            <Input name="vendor_detected" placeholder="Vendor" />
            <Input name="technology" placeholder="Tecnologia" defaultValue="GPON" />
            <Input name="ethernet_ports" placeholder="ETH" type="number" />
            <Input name="wifi_ports" placeholder="WiFi" type="number" />
            <Input name="pots_ports" placeholder="POTS" type="number" />
            <Button className="md:col-span-6">Guardar tipo ONU</Button>
          </form>
        </Panel>
        <DataTable
          title="Tipos activos"
          items={items.data}
          columns={[
            { key: "olt_code", label: "OLT Code" },
            { key: "name", label: "Nombre" },
            { key: "vendor_detected", label: "Vendor" },
            { key: "technology", label: "Tecnologia" },
            { key: "ethernet_ports", label: "ETH" },
            { key: "wifi_ports", label: "WiFi" },
            { key: "pots_ports", label: "POTS" },
            { key: "source", label: "Source" },
            { key: "is_active", label: "Estado", render: (item) => (item.is_active ? "Activo" : "Inactivo") },
          ]}
        />
      </div>
    </AppShell>
  );
}

function Header({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div>
      <h2 className="text-2xl font-semibold text-slate-950">{title}</h2>
      <p className="mt-1 text-sm text-muted">{subtitle}</p>
    </div>
  );
}

function OltSelect({ olts }: { olts: Olt[] }) {
  return (
    <select name="olt_id" className="h-9 rounded-md border border-slate-200 bg-white px-3 text-sm" required>
      <option value="">OLT</option>
      {olts.map((olt) => (
        <option key={olt.id} value={olt.id}>
          {olt.olt_code}
        </option>
      ))}
    </select>
  );
}
