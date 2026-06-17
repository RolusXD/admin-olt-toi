"use client";

import { FormEvent } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { DataTable } from "@/components/modules/DataTable";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Panel } from "@/components/ui/panel";
import { api } from "@/services/api";
import { useApiData } from "@/hooks/useApiData";
import type { Zone } from "@/types";

export default function ZonesPage() {
  const items = useApiData<Zone[]>(() => api.zones({ is_active: 1 }), []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await api.createZone({
      name: String(form.get("name")),
      code: String(form.get("code") || ""),
      description: String(form.get("description") || ""),
      source: "manual",
    });
    window.location.reload();
  }

  return (
    <AppShell>
      <div className="space-y-5">
        <div>
          <h2 className="text-2xl font-semibold text-slate-950">Zonas</h2>
          <p className="mt-1 text-sm text-muted">Zonas operativas detectadas o creadas manualmente.</p>
        </div>
        <Panel className="p-4">
          <form className="grid gap-3 md:grid-cols-4" onSubmit={submit}>
            <Input name="name" placeholder="Nombre" required />
            <Input name="code" placeholder="Codigo" />
            <Input name="description" placeholder="Descripcion" />
            <Button>Guardar zona</Button>
          </form>
        </Panel>
        <DataTable
          title="Zonas activas"
          items={items.data}
          columns={[
            { key: "name", label: "Nombre" },
            { key: "code", label: "Codigo" },
            { key: "description", label: "Descripcion" },
            { key: "source", label: "Source" },
            { key: "is_active", label: "Estado", render: (item) => (item.is_active ? "Activo" : "Inactivo") },
          ]}
        />
      </div>
    </AppShell>
  );
}
