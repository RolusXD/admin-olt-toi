"use client";

import { FormEvent } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { DataTable } from "@/components/modules/DataTable";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Panel } from "@/components/ui/panel";
import { api } from "@/services/api";
import { useApiData } from "@/hooks/useApiData";
import type { ProvisioningTemplate } from "@/types";

export default function ProvisioningTemplatesPage() {
  const items = useApiData<ProvisioningTemplate[]>(() => api.provisioningTemplates(), []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await api.createProvisioningTemplate({
      vendor: String(form.get("vendor") || "ZTE"),
      model: String(form.get("model") || "C300"),
      firmware: String(form.get("firmware") || "V1.2.5P3"),
      template_name: String(form.get("template_name")),
      template_body: String(form.get("template_body")),
      is_default: Boolean(form.get("is_default")),
      is_active: true,
      description: String(form.get("description") || ""),
    });
    window.location.reload();
  }

  return (
    <AppShell>
      <div className="space-y-5">
        <div>
          <h2 className="text-2xl font-semibold text-slate-950">Plantillas de aprovisionamiento</h2>
          <p className="mt-1 text-sm text-muted">Plantillas internas para generar CLI. No ejecutan configuracion.</p>
        </div>
        <Panel className="p-4">
          <form className="grid gap-3 md:grid-cols-3" onSubmit={submit}>
            <Input name="vendor" placeholder="Vendor" defaultValue="ZTE" />
            <Input name="model" placeholder="Modelo" defaultValue="C300" />
            <Input name="firmware" placeholder="Firmware" defaultValue="V1.2.5P3" />
            <Input name="template_name" placeholder="Nombre plantilla" required />
            <Input name="description" placeholder="Descripcion" />
            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input name="is_default" type="checkbox" /> Default
            </label>
            <textarea
              name="template_body"
              className="min-h-40 rounded-md border border-slate-200 p-3 text-sm md:col-span-3"
              placeholder="CLI con variables: {pon_port_interface}, {onu_index}, {serial_number}"
              required
            />
            <Button className="md:col-span-3">Guardar plantilla</Button>
          </form>
        </Panel>
        <DataTable
          title="Plantillas"
          items={items.data}
          columns={[
            { key: "vendor", label: "Vendor" },
            { key: "model", label: "Modelo" },
            { key: "firmware", label: "Firmware" },
            { key: "template_name", label: "Nombre" },
            { key: "is_default", label: "Default", render: (item) => (item.is_default ? "Si" : "No") },
            { key: "is_active", label: "Estado", render: (item) => (item.is_active ? "Activo" : "Inactivo") },
            { key: "description", label: "Descripcion" },
          ]}
        />
      </div>
    </AppShell>
  );
}
