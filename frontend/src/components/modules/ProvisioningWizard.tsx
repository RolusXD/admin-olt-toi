"use client";

import { FormEvent, useState } from "react";
import { Wand2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Panel } from "@/components/ui/panel";
import { api } from "@/services/api";

export function ProvisioningWizard() {
  const [commands, setCommands] = useState<string[]>([]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const payload = {
      olt_id: Number(form.get("olt_id")),
      unauthorized_onu: String(form.get("unauthorized_onu")),
      customer_name: String(form.get("customer_name")),
      zone_id: Number(form.get("zone_id")),
      nap_id: Number(form.get("nap_id")),
      nap_port: Number(form.get("nap_port")),
      vlan: Number(form.get("vlan")),
      speed_profile: String(form.get("speed_profile")),
    };
    const plan = await api.provisioningPlan(payload);
    setCommands(plan.commands);
  }

  return (
    <Panel className="p-4">
      <div className="mb-3 flex items-center gap-2">
        <Wand2 className="h-4 w-4 text-primary" />
        <h2 className="text-sm font-semibold text-slate-950">Asistente de aprovisionamiento</h2>
      </div>
      <form className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" onSubmit={submit}>
        <Input name="olt_id" placeholder="OLT ID" defaultValue="1" />
        <Input name="unauthorized_onu" placeholder="ONU no autorizada" defaultValue="gpon-onu_1/2/1:pending" />
        <Input name="customer_name" placeholder="Cliente" />
        <Input name="zone_id" placeholder="Zona ID" defaultValue="1" />
        <Input name="nap_id" placeholder="NAP ID" defaultValue="1" />
        <Input name="nap_port" placeholder="Puerto NAP" defaultValue="1" />
        <Input name="vlan" placeholder="VLAN" defaultValue="100" />
        <Input name="speed_profile" placeholder="Perfil" defaultValue="50M" />
        <Button className="sm:col-span-2 xl:col-span-4">
          <Wand2 className="h-4 w-4" /> Generar comandos
        </Button>
      </form>
      {commands.length > 0 && (
        <pre className="mt-4 overflow-x-auto rounded-md bg-slate-950 p-3 text-xs text-slate-50">
          {commands.join("\n")}
        </pre>
      )}
    </Panel>
  );
}
