"use client";

import { FormEvent, useState } from "react";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Panel } from "@/components/ui/panel";
import { api } from "@/services/api";

export function QuickCreateForms({ onDone }: { onDone: () => void }) {
  const [busy, setBusy] = useState(false);

  async function submitOlt(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    const form = new FormData(event.currentTarget);
    await api.createOlt(Object.fromEntries(form));
    event.currentTarget.reset();
    setBusy(false);
    onDone();
  }

  async function submitZone(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    const form = new FormData(event.currentTarget);
    await api.createZone(Object.fromEntries(form));
    event.currentTarget.reset();
    setBusy(false);
    onDone();
  }

  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <Panel className="p-4">
        <h2 className="mb-3 text-sm font-semibold text-slate-950">Nueva OLT</h2>
        <form className="grid gap-3 sm:grid-cols-2" onSubmit={submitOlt}>
          <Input name="olt_code" placeholder="Codigo OLT" required />
          <Input name="name" placeholder="Nombre" required />
          <Input name="display_name" placeholder="Display name" />
          <Input name="ip_address" placeholder="IP" required />
          <Input name="telnet_port" placeholder="Puerto Telnet" defaultValue="23" required />
          <Input name="username" placeholder="Usuario" required />
          <Input name="password" placeholder="Contrasena" type="password" required />
          <Input name="firmware" placeholder="Firmware" defaultValue="V1.2.5P3" />
          <select name="environment" className="h-9 rounded-md border border-slate-200 bg-white px-3 text-sm" defaultValue="production">
            <option value="production">Produccion</option>
            <option value="lab">Laboratorio</option>
          </select>
          <Button disabled={busy} className="sm:col-span-2">
            <Plus className="h-4 w-4" /> Crear OLT
          </Button>
        </form>
      </Panel>
      <Panel className="p-4">
        <h2 className="mb-3 text-sm font-semibold text-slate-950">Nueva zona</h2>
        <form className="grid gap-3" onSubmit={submitZone}>
          <Input name="name" placeholder="Nombre de zona" required />
          <Input name="description" placeholder="Descripcion" />
          <Button disabled={busy}>
            <Plus className="h-4 w-4" /> Crear zona
          </Button>
        </form>
      </Panel>
    </div>
  );
}
