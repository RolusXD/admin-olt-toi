"use client";

import { FormEvent, ReactNode, useMemo, useState } from "react";
import { Pencil, Plus, Power, RefreshCw, Save, X } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/button";
import { EnvironmentBadge } from "@/components/ui/environment-badge";
import { Input } from "@/components/ui/input";
import { Panel } from "@/components/ui/panel";
import { api } from "@/services/api";
import { useApiData } from "@/hooks/useApiData";
import type { Olt, OnuType, ProfileCatalog } from "@/types";

export default function OnuTypesPage() {
  const [reloadKey, setReloadKey] = useState(0);
  const [showLab, setShowLab] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const olts = useApiData<Olt[]>(() => api.olts(showLab ? {} : { environment: "production" }), [], [showLab, reloadKey]);
  const items = useApiData<OnuType[]>(() => api.onuTypes(showLab ? {} : { is_active: 1 }), [], [showLab, reloadKey]);
  const profiles = useApiData<ProfileCatalog[]>(() => api.profileCatalogs({ is_active: true }), [], [reloadKey]);

  const sortedItems = useMemo(() => [...items.data].sort((a, b) => (a.olt_code ?? "").localeCompare(b.olt_code ?? "") || a.name.localeCompare(b.name)), [items.data]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setMessage(null);
    const form = new FormData(event.currentTarget);
    const olt = olts.data.find((item) => item.id === Number(form.get("olt_id")));
    try {
      await api.createOnuType({
        olt_id: Number(form.get("olt_id")),
        vendor: olt?.vendor ?? "ZTE",
        model: olt?.model ?? "C300",
        firmware: olt?.firmware ?? "V1.2.5P3",
        name: String(form.get("name") ?? "").trim(),
        technology: String(form.get("pon_type") ?? "GPON"),
        pon_type: String(form.get("pon_type") ?? "GPON"),
        channel_gpon: form.get("channel_gpon") === "on",
        channel_xgpon: form.get("channel_xgpon") === "on",
        channel_xgspon: form.get("channel_xgspon") === "on",
        ethernet_ports: numberOrNull(form.get("ethernet_ports")),
        wifi_ports: numberOrNull(form.get("wifi_ports")),
        pots_ports: numberOrNull(form.get("pots_ports")),
        rf_ports: form.get("rf_ports") === "on" ? 1 : 0,
        allow_custom_profiles: form.get("allow_custom_profiles") === "on",
        default_custom_profile_id: numberOrNull(form.get("default_custom_profile_id")),
        capability_mode: String(form.get("capability_mode") ?? "bridging"),
        is_active: form.get("is_active") === "on",
        is_provisioning_allowed: form.get("is_provisioning_allowed") === "on",
        source: "manual",
      });
      event.currentTarget.reset();
      setShowForm(false);
      setReloadKey((value) => value + 1);
      setMessage("Tipo ONU guardado.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo guardar el tipo ONU.");
    }
  }

  async function saveRow(item: OnuType, form: HTMLFormElement) {
    const data = new FormData(form);
    try {
      await api.updateOnuType(item.id, payloadFromForm(data));
      setEditingId(null);
      setReloadKey((value) => value + 1);
      setMessage(`Tipo ONU ${item.name} actualizado.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo actualizar el tipo ONU.");
    }
  }

  async function toggleActive(item: OnuType) {
    await api.updateOnuType(item.id, { is_active: !item.is_active });
    setReloadKey((value) => value + 1);
  }

  return (
    <AppShell>
      <div className="space-y-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h2 className="text-2xl font-semibold text-slate-950">Tipos de ONU</h2>
            <p className="mt-1 text-sm text-muted">Catalogo tecnico real importado desde la OLT ZTE.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => setReloadKey((value) => value + 1)}>
              <RefreshCw className="h-4 w-4" /> Refrescar
            </Button>
            <Button type="button" onClick={() => setShowForm((value) => !value)}>
              {showForm ? <X className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
              {showForm ? "Cerrar" : "Agregar Tipo de ONU"}
            </Button>
          </div>
        </div>

        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input type="checkbox" checked={showLab} onChange={(event) => setShowLab(event.target.checked)} />
          Mostrar laboratorio
        </label>

        {message && <div className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">{message}</div>}
        {error && <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">{error}</div>}

        {showForm && (
          <Panel className="p-4">
            <form className="grid gap-5" onSubmit={submit}>
              <Section title="Tecnologia">
                <OltSelect olts={olts.data} />
                <Select name="pon_type" label="Tipo PON" defaultValue="GPON" options={[["GPON", "GPON"], ["EPON", "EPON"]]} />
                <Check name="channel_gpon" label="GPON" defaultChecked />
                <Check name="channel_xgpon" label="XG-PON" />
                <Check name="channel_xgspon" label="XGS-PON" />
              </Section>
              <Section title="Hardware">
                <Input name="name" placeholder="Tipo ONU real en ZTE" required />
                <PortSelect name="ethernet_ports" label="Puertos Ethernet" defaultValue={1} />
                <PortSelect name="wifi_ports" label="WiFi SSIDs" defaultValue={0} />
                <PortSelect name="pots_ports" label="Puertos VoIP" defaultValue={0} />
                <Check name="rf_ports" label="CATV" />
              </Section>
              <Section title="Perfiles">
                <Check name="allow_custom_profiles" label="Permitir perfiles personalizados" defaultChecked />
                <ProfileSelect profiles={profiles.data} />
              </Section>
              <Section title="Capacidad">
                <Radio name="capability_mode" value="bridging" label="Bridging" defaultChecked />
                <Radio name="capability_mode" value="routing" label="Routing" />
                <Radio name="capability_mode" value="bridging_routing" label="Bridging/Routing" />
              </Section>
              <Section title="Estado">
                <Check name="is_active" label="Activo" defaultChecked />
                <Check name="is_provisioning_allowed" label="Permitir aprovisionamiento" />
                <Button>
                  <Save className="h-4 w-4" /> Guardar tipo ONU
                </Button>
              </Section>
            </form>
          </Panel>
        )}

        <Panel className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1450px] text-left text-sm">
              <thead className="bg-slate-50 text-slate-950">
                <tr>
                  <th className="px-4 py-3">OLT Code</th>
                  <th className="px-4 py-3">Entorno</th>
                  <th className="px-4 py-3">Tipo PON</th>
                  <th className="px-4 py-3">Canales</th>
                  <th className="px-4 py-3">Tipo ONU</th>
                  <th className="px-4 py-3">Puertos Ethernet</th>
                  <th className="px-4 py-3">WiFi SSIDs</th>
                  <th className="px-4 py-3">Puertos VoIP</th>
                  <th className="px-4 py-3">CATV</th>
                  <th className="px-4 py-3">Permitir perfiles personalizados</th>
                  <th className="px-4 py-3">Perfil personalizado predeterminado</th>
                  <th className="px-4 py-3">Capacidad</th>
                  <th className="px-4 py-3">Estado</th>
                  <th className="px-4 py-3">Accion</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {sortedItems.map((item) => (
                  <OnuTypeRows
                    key={item.id}
                    item={item}
                    profiles={profiles.data}
                    editing={editingId === item.id}
                    onEdit={() => setEditingId(item.id)}
                    onCancel={() => setEditingId(null)}
                    onSave={saveRow}
                    onToggleActive={() => void toggleActive(item)}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      </div>
    </AppShell>
  );
}

function OnuTypeRows({ item, profiles, editing, onEdit, onCancel, onSave, onToggleActive }: { item: OnuType; profiles: ProfileCatalog[]; editing: boolean; onEdit: () => void; onCancel: () => void; onSave: (item: OnuType, form: HTMLFormElement) => Promise<void>; onToggleActive: () => void }) {
  const defaultProfile = profiles.find((profile) => profile.id === item.default_custom_profile_id);
  return (
    <>
      <tr className="odd:bg-white even:bg-slate-50/70">
        <td className="px-4 py-3">{item.olt_code ?? item.olt_code_snapshot ?? item.olt_id}</td>
        <td className="px-4 py-3"><EnvironmentBadge environment={item.olt_environment ?? "production"} /></td>
        <td className="px-4 py-3">{item.pon_type || item.technology || "GPON"}</td>
        <td className="px-4 py-3">{channelLabel(item)}</td>
        <td className="px-4 py-3 font-medium text-primary">{item.name}</td>
        <td className="px-4 py-3">{item.ethernet_ports ?? 0}</td>
        <td className="px-4 py-3">{item.wifi_ports ?? 0}</td>
        <td className="px-4 py-3">{item.pots_ports ?? 0}</td>
        <td className="px-4 py-3">{(item.rf_ports ?? 0) > 0 ? "Si" : "No"}</td>
        <td className="px-4 py-3">{item.allow_custom_profiles ? "Si" : "No"}</td>
        <td className="px-4 py-3">{defaultProfile?.name ?? "-"}</td>
        <td className="px-4 py-3">{capacityLabel(item.capability_mode)}</td>
        <td className="px-4 py-3">{item.is_active ? "Activo" : "Inactivo"}</td>
        <td className="px-4 py-3">
          <div className="flex gap-2">
            <Button type="button" variant="secondary" onClick={editing ? onCancel : onEdit}>
              {editing ? <X className="h-4 w-4" /> : <Pencil className="h-4 w-4" />}
              {editing ? "Cerrar" : "Editar"}
            </Button>
            <Button type="button" variant="secondary" onClick={onToggleActive}>
              <Power className="h-4 w-4" />
              {item.is_active ? "Desactivar" : "Activar"}
            </Button>
          </div>
        </td>
      </tr>
      {editing && (
        <tr>
          <td colSpan={14} className="bg-slate-50 px-4 py-4">
            <form className="grid gap-4" onSubmit={(event) => { event.preventDefault(); void onSave(item, event.currentTarget); }}>
              <Section title="Tecnologia">
                <Select name="pon_type" label="Tipo PON" defaultValue={item.pon_type ?? "GPON"} options={[["GPON", "GPON"], ["EPON", "EPON"]]} />
                <Check name="channel_gpon" label="GPON" defaultChecked={item.channel_gpon} />
                <Check name="channel_xgpon" label="XG-PON" defaultChecked={item.channel_xgpon} />
                <Check name="channel_xgspon" label="XGS-PON" defaultChecked={item.channel_xgspon} />
              </Section>
              <Section title="Hardware">
                <Input name="name" defaultValue={item.name} required />
                <PortSelect name="ethernet_ports" label="Puertos Ethernet" defaultValue={item.ethernet_ports ?? 0} />
                <PortSelect name="wifi_ports" label="WiFi SSIDs" defaultValue={item.wifi_ports ?? 0} />
                <PortSelect name="pots_ports" label="Puertos VoIP" defaultValue={item.pots_ports ?? 0} />
                <Check name="rf_ports" label="CATV" defaultChecked={(item.rf_ports ?? 0) > 0} />
              </Section>
              <Section title="Perfiles">
                <Check name="allow_custom_profiles" label="Permitir perfiles personalizados" defaultChecked={item.allow_custom_profiles} />
                <ProfileSelect profiles={profiles} defaultValue={item.default_custom_profile_id ?? ""} />
              </Section>
              <Section title="Capacidad">
                <Radio name="capability_mode" value="bridging" label="Bridging" defaultChecked={item.capability_mode === "bridging"} />
                <Radio name="capability_mode" value="routing" label="Routing" defaultChecked={item.capability_mode === "routing"} />
                <Radio name="capability_mode" value="bridging_routing" label="Bridging/Routing" defaultChecked={item.capability_mode === "bridging_routing"} />
              </Section>
              <Section title="Estado">
                <Check name="is_active" label="Activo" defaultChecked={item.is_active} />
                <Check name="is_provisioning_allowed" label="Permitir aprovisionamiento" defaultChecked={item.is_provisioning_allowed} />
                <Button variant="secondary"><Save className="h-4 w-4" /> Guardar</Button>
              </Section>
            </form>
          </td>
        </tr>
      )}
    </>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <fieldset className="grid gap-3 md:grid-cols-5">
      <legend className="mb-2 text-sm font-semibold text-slate-950">{title}</legend>
      {children}
    </fieldset>
  );
}

function OltSelect({ olts }: { olts: Olt[] }) {
  return (
    <select name="olt_id" className="h-9 rounded-md border border-slate-200 bg-white px-3 text-sm" required>
      <option value="">OLT</option>
      {olts.map((olt) => <option key={olt.id} value={olt.id}>{olt.olt_code}</option>)}
    </select>
  );
}

function Select({ name, label, defaultValue, options }: { name: string; label: string; defaultValue: string; options: Array<[string, string]> }) {
  return (
    <label className="text-xs font-medium text-slate-600">
      {label}
      <select name={name} defaultValue={defaultValue} className="mt-1 h-9 w-full rounded-md border border-slate-200 bg-white px-3 text-sm">
        {options.map(([value, text]) => <option key={value} value={value}>{text}</option>)}
      </select>
    </label>
  );
}

function PortSelect({ name, label, defaultValue }: { name: string; label: string; defaultValue: number }) {
  return (
    <label className="text-xs font-medium text-slate-600">
      {label}
      <select name={name} defaultValue={defaultValue} className="mt-1 h-9 w-full rounded-md border border-slate-200 bg-white px-3 text-sm">
        {[0, 1, 2, 3, 4, 5, 6, 8].map((value) => <option key={value} value={value}>{value}</option>)}
      </select>
    </label>
  );
}

function ProfileSelect({ profiles, defaultValue = "" }: { profiles: ProfileCatalog[]; defaultValue?: number | string }) {
  return (
    <select name="default_custom_profile_id" defaultValue={defaultValue} className="h-9 rounded-md border border-slate-200 bg-white px-3 text-sm">
      <option value="">Ninguno seleccionado</option>
      {profiles.map((profile) => <option key={profile.id} value={profile.id}>{profile.name}</option>)}
    </select>
  );
}

function Check({ name, label, defaultChecked = false }: { name: string; label: string; defaultChecked?: boolean }) {
  return <label className="flex h-9 items-center gap-2 text-sm text-slate-700"><input name={name} type="checkbox" defaultChecked={defaultChecked} /> {label}</label>;
}

function Radio({ name, value, label, defaultChecked = false }: { name: string; value: string; label: string; defaultChecked?: boolean }) {
  return <label className="flex h-9 items-center gap-2 text-sm text-slate-700"><input name={name} value={value} type="radio" defaultChecked={defaultChecked} /> {label}</label>;
}

function numberOrNull(value: FormDataEntryValue | null) {
  const text = String(value ?? "").trim();
  if (!text) return null;
  const parsed = Number(text);
  return Number.isFinite(parsed) ? parsed : null;
}

function payloadFromForm(data: FormData) {
  return {
    name: String(data.get("name") ?? "").trim(),
    technology: String(data.get("pon_type") ?? "GPON"),
    pon_type: String(data.get("pon_type") ?? "GPON"),
    channel_gpon: data.get("channel_gpon") === "on",
    channel_xgpon: data.get("channel_xgpon") === "on",
    channel_xgspon: data.get("channel_xgspon") === "on",
    ethernet_ports: numberOrNull(data.get("ethernet_ports")),
    wifi_ports: numberOrNull(data.get("wifi_ports")),
    pots_ports: numberOrNull(data.get("pots_ports")),
    rf_ports: data.get("rf_ports") === "on" ? 1 : 0,
    allow_custom_profiles: data.get("allow_custom_profiles") === "on",
    default_custom_profile_id: numberOrNull(data.get("default_custom_profile_id")),
    capability_mode: String(data.get("capability_mode") ?? "bridging"),
    is_active: data.get("is_active") === "on",
    is_provisioning_allowed: data.get("is_provisioning_allowed") === "on",
  };
}

function channelLabel(item: OnuType) {
  const channels = [
    item.channel_gpon ? "G" : null,
    item.channel_xgpon ? "XG" : null,
    item.channel_xgspon ? "XGS" : null,
  ].filter(Boolean);
  return channels.join(" / ") || "-";
}

function capacityLabel(value: string) {
  if (value === "bridging_routing") return "Bridging/Routing";
  if (value === "routing") return "Routing";
  return "Bridging";
}
