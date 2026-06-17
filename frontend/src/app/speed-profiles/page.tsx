"use client";

import { FormEvent } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { DataTable } from "@/components/modules/DataTable";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Panel } from "@/components/ui/panel";
import { api } from "@/services/api";
import { useApiData } from "@/hooks/useApiData";
import type { Olt, SpeedProfile } from "@/types";

export default function SpeedProfilesPage() {
  const olts = useApiData<Olt[]>(() => api.olts({ environment: "production" }), []);
  const items = useApiData<SpeedProfile[]>(() => api.speedProfiles({ is_active: 1 }), []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await api.createSpeedProfile({
      olt_id: Number(form.get("olt_id")),
      name: String(form.get("name")),
      profile_code: String(form.get("profile_code")),
      upstream_profile_name: String(form.get("upstream_profile_name")),
      downstream_profile_name: String(form.get("downstream_profile_name")),
      upstream_kbps: Number(form.get("upstream_kbps") || 0) || null,
      downstream_kbps: Number(form.get("downstream_kbps") || 0) || null,
      technology: "GPON",
      source: "manual",
    });
    window.location.reload();
  }

  return (
    <AppShell>
      <div className="space-y-5">
        <div>
          <h2 className="text-2xl font-semibold text-slate-950">Perfiles de velocidad</h2>
          <p className="mt-1 text-sm text-muted">Seleccionables por el tecnico; guardan el tcont y traffic usados para el CLI.</p>
        </div>
        <Panel className="p-4">
          <form className="grid gap-3 md:grid-cols-4" onSubmit={submit}>
            <select name="olt_id" className="h-9 rounded-md border border-slate-200 bg-white px-3 text-sm" required>
              <option value="">OLT</option>
              {olts.data.map((olt) => (
                <option key={olt.id} value={olt.id}>{olt.olt_code}</option>
              ))}
            </select>
            <Input name="name" placeholder="Nombre" required />
            <Input name="profile_code" placeholder="Codigo" required />
            <Input name="upstream_profile_name" placeholder="Perfil UP" required />
            <Input name="downstream_profile_name" placeholder="Perfil DOWN" required />
            <Input name="upstream_kbps" placeholder="UP kbps" type="number" />
            <Input name="downstream_kbps" placeholder="DOWN kbps" type="number" />
            <Button>Guardar perfil</Button>
          </form>
        </Panel>
        <DataTable
          title="Perfiles activos"
          items={items.data}
          columns={[
            { key: "olt_code", label: "OLT Code" },
            { key: "name", label: "Nombre" },
            { key: "profile_code", label: "Codigo" },
            { key: "upstream_profile_name", label: "Perfil UP" },
            { key: "downstream_profile_name", label: "Perfil DOWN" },
            { key: "upstream_kbps", label: "UP kbps" },
            { key: "downstream_kbps", label: "DOWN kbps" },
            { key: "source", label: "Source" },
            { key: "is_active", label: "Estado", render: (item) => (item.is_active ? "Activo" : "Inactivo") },
          ]}
        />
      </div>
    </AppShell>
  );
}
