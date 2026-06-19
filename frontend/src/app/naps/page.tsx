"use client";

import { FormEvent, useState } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { DataTable } from "@/components/modules/DataTable";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Panel } from "@/components/ui/panel";
import { api } from "@/services/api";
import { useApiData } from "@/hooks/useApiData";
import type { Nap, NapPort, Olt, Zone } from "@/types";

export default function NapsPage() {
  const [selectedNapId, setSelectedNapId] = useState<number | null>(null);
  const olts = useApiData<Olt[]>(() => api.olts({ environment: "production" }), []);
  const zones = useApiData<Zone[]>(() => api.zones({ is_active: 1 }), []);
  const naps = useApiData<Nap[]>(() => api.naps({ is_active: 1 }), []);
  const ports = useApiData<NapPort[]>(() => api.napPorts(), []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await api.createNap({
      olt_id: Number(form.get("olt_id")),
      zone_id: Number(form.get("zone_id")),
      name: String(form.get("name")),
      code: String(form.get("code") || ""),
      nap_type: String(form.get("nap_type") || "NAP"),
      capacity: Number(form.get("capacity") || 16),
      address_reference: String(form.get("address_reference") || ""),
      source: "manual",
    });
    window.location.reload();
  }

  return (
    <AppShell>
      <div className="space-y-5">
        <div>
          <h2 className="text-2xl font-semibold text-slate-950">NAPs / Cajas</h2>
          <p className="mt-1 text-sm text-muted">Cada NAP crea puertos internos segun su capacidad. No modifica la OLT.</p>
        </div>
        <Panel className="p-4">
          <form className="grid gap-3 md:grid-cols-7" onSubmit={submit}>
            <select name="olt_id" className="h-9 rounded-md border border-slate-200 bg-white px-3 text-sm" required><option value="">OLT</option>{olts.data.map((olt) => <option key={olt.id} value={olt.id}>{olt.olt_code} - {olt.name}</option>)}</select>
            <select name="zone_id" className="h-9 rounded-md border border-slate-200 bg-white px-3 text-sm" required>
              <option value="">Zona</option>
              {zones.data.map((zone) => <option key={zone.id} value={zone.id}>{zone.name}</option>)}
            </select>
            <Input name="name" placeholder="Nombre" required />
            <Input name="code" placeholder="Codigo" />
            <Input name="nap_type" placeholder="Tipo" defaultValue="NAP" />
            <Input name="capacity" placeholder="Capacidad" type="number" defaultValue={16} />
            <Input name="address_reference" placeholder="Referencia" />
            <Button className="md:col-span-6">Guardar NAP</Button>
          </form>
        </Panel>
        <DataTable
          title="NAPs activas"
          items={naps.data}
          columns={[
            { key: "name", label: "Nombre" },
            { key: "olt_code_snapshot", label: "OLT" },
            { key: "code", label: "Codigo" },
            { key: "nap_type", label: "Tipo" },
            { key: "capacity", label: "Capacidad" },
            { key: "source", label: "Source" },
            { key: "id", label: "Puertos", render: (item) => <button className="text-primary" onClick={() => setSelectedNapId(item.id)}>Ver puertos</button> },
          ]}
        />
        <DataTable
          title={selectedNapId ? `Puertos NAP ${selectedNapId}` : "Puertos NAP"}
          items={selectedNapId ? ports.data.filter((port) => port.nap_id === selectedNapId) : ports.data}
          columns={[
            { key: "port_number", label: "Puerto" },
            { key: "label", label: "Etiqueta" },
            { key: "status", label: "Estado" },
            { key: "customer_name_snapshot", label: "Cliente" },
            { key: "onu_id", label: "ONU" },
          ]}
        />
      </div>
    </AppShell>
  );
}
