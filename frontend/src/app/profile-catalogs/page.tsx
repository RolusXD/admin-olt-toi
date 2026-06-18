"use client";

import { FormEvent, useMemo, useState } from "react";
import { CheckCircle2, PlusCircle, RefreshCw } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/button";
import { EnvironmentBadge } from "@/components/ui/environment-badge";
import { Input } from "@/components/ui/input";
import { Panel } from "@/components/ui/panel";
import { api } from "@/services/api";
import { useApiData } from "@/hooks/useApiData";
import type { Olt, ProfileCatalog } from "@/types";

type Direction = "download" | "upload";

export default function ProfileCatalogsPage() {
  const [showLab, setShowLab] = useState(false);
  const [direction, setDirection] = useState<Direction>("download");
  const [selectedOltId, setSelectedOltId] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const olts = useApiData<Olt[]>(() => api.olts(showLab ? {} : { environment: "production" }), [], [showLab, reloadKey]);
  const catalogs = useApiData<ProfileCatalog[]>(
    () => api.profileCatalogs({ direction, ...(selectedOltId ? { olt_id: selectedOltId } : {}) }),
    [],
    [direction, selectedOltId, reloadKey],
  );
  const selectedOlt = useMemo(() => olts.data.find((olt) => String(olt.id) === selectedOltId) ?? null, [olts.data, selectedOltId]);

  async function createCatalog(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setMessage(null);
    const form = new FormData(event.currentTarget);
    const oltId = Number(form.get("olt_id") || selectedOltId);
    const speed = toNumber(form.get("speed_kbps"));
    const olt = olts.data.find((item) => item.id === oltId);
    if (!oltId || !speed) {
      setError("Seleccione una OLT e ingrese velocidad en kbps.");
      return;
    }
    const payload = {
      olt_id: oltId,
      vendor: olt?.vendor ?? "ZTE",
      model: olt?.model ?? "C300",
      firmware: olt?.firmware ?? "V1.2.5P3",
      direction,
      profile_kind: direction === "upload" ? "tcont" : "traffic",
      name: String(form.get("name") ?? "").trim(),
      service_type: String(form.get("service_type") ?? "internet"),
      speed_kbps: speed,
      is_default: form.get("is_default") === "on",
      type_value: direction === "upload" ? 5 : undefined,
      fixed_kbps: direction === "upload" ? 64 : undefined,
      assured_kbps: direction === "upload" ? 64 : undefined,
      maximum_kbps: direction === "upload" ? speed : undefined,
      sir_kbps: direction === "download" ? speed : undefined,
      pir_kbps: direction === "download" ? speed : undefined,
      source: "manual",
      is_active: form.get("is_active") === "on",
    };
    try {
      await api.createProfileCatalog(payload);
      event.currentTarget.reset();
      setReloadKey((value) => value + 1);
      setMessage("Perfil guardado correctamente.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo crear el perfil.");
    }
  }

  return (
    <AppShell>
      <div className="space-y-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h2 className="text-2xl font-semibold text-slate-950">Perfiles de velocidad ZTE</h2>
            <p className="mt-1 text-sm text-muted">Upload usa profile tcont. Descargar usa profile traffic.</p>
          </div>
          <Button variant="secondary" onClick={() => setReloadKey((value) => value + 1)}>
            <RefreshCw className="h-4 w-4" /> Refrescar
          </Button>
        </div>

        {message && <div className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">{message}</div>}
        {error && <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">{error}</div>}

        <Panel className="p-4">
          <div className="grid gap-3 md:grid-cols-[1fr_auto] md:items-end">
            <label className="text-sm font-medium text-slate-700">
              OLT
              <select className="mt-1 h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm" value={selectedOltId} onChange={(event) => setSelectedOltId(event.target.value)}>
                <option value="">Todas las OLTs visibles</option>
                {olts.data.map((olt) => <option key={olt.id} value={olt.id}>{olt.olt_code} - {olt.name}</option>)}
              </select>
            </label>
            <label className="flex h-10 items-center gap-2 text-sm text-slate-700">
              <input type="checkbox" checked={showLab} onChange={(event) => setShowLab(event.target.checked)} />
              Mostrar laboratorio
            </label>
          </div>
          {selectedOlt && <div className="mt-3"><EnvironmentBadge environment={selectedOlt.environment} /></div>}
        </Panel>

        <div className="flex gap-2">
          <Tab active={direction === "download"} onClick={() => setDirection("download")} label="Descargar" />
          <Tab active={direction === "upload"} onClick={() => setDirection("upload")} label="Upload" />
        </div>

        <Panel className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[980px] text-left text-sm">
              <thead className="bg-slate-50 text-slate-950">
                <tr>
                  <th className="px-4 py-3">OLT Code</th>
                  <th className="px-4 py-3">Nombre</th>
                  <th className="px-4 py-3">Para</th>
                  <th className="px-4 py-3">Velocidad</th>
                  <th className="px-4 py-3">Tipo</th>
                  <th className="px-4 py-3">Predeterminado</th>
                  <th className="px-4 py-3">ONUs</th>
                  <th className="px-4 py-3">Estado</th>
                  <th className="px-4 py-3">Accion</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {catalogs.data.map((profile) => (
                  <tr key={profile.id} className="odd:bg-white even:bg-slate-50/70">
                    <td className="px-4 py-3">{profile.olt_code ?? profile.olt_code_snapshot ?? profile.olt_id}</td>
                    <td className="px-4 py-3 font-medium text-primary">{profile.name}</td>
                    <td className="px-4 py-3">{profile.direction === "download" ? "Descargar" : "Upload"}</td>
                    <td className="px-4 py-3">{formatKbps(speedOf(profile))}</td>
                    <td className="px-4 py-3">{serviceLabel(profile.service_type)}</td>
                    <td className="px-4 py-3">{profile.is_default ? <CheckCircle2 className="h-4 w-4 text-emerald-600" /> : "-"}</td>
                    <td className="px-4 py-3">{profile.onu_count ?? 0}</td>
                    <td className="px-4 py-3">{profile.is_active ? "Activo" : "Inactivo"}</td>
                    <td className="px-4 py-3 text-muted">Edicion interna</td>
                  </tr>
                ))}
                {!catalogs.data.length && <tr><td className="px-4 py-6 text-center text-muted" colSpan={9}>Sin perfiles para el filtro actual.</td></tr>}
              </tbody>
            </table>
          </div>
        </Panel>

        <Panel className="p-4">
          <div className="mb-4 flex items-center gap-2 text-sm font-semibold text-slate-950">
            <PlusCircle className="h-4 w-4 text-primary" />
            Crear perfil manual
          </div>
          <form className="grid gap-3 md:grid-cols-6" onSubmit={createCatalog}>
            <select name="olt_id" className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm" defaultValue={selectedOltId} required>
              <option value="">OLT</option>
              {olts.data.map((olt) => <option key={olt.id} value={olt.id}>{olt.olt_code}</option>)}
            </select>
            <Input name="name" placeholder="Nombre del perfil" required />
            <select name="service_type" className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm" defaultValue="internet">
              <option value="internet">Internet</option>
              <option value="gestion">Gestion</option>
              <option value="voip">VoIP</option>
              <option value="iptv">IPTV</option>
              <option value="otro">Otro</option>
            </select>
            <Input name="speed_kbps" type="number" placeholder="Velocidad kbps" required />
            <label className="flex h-10 items-center gap-2 text-sm text-slate-700"><input name="is_default" type="checkbox" /> Predeterminado</label>
            <label className="flex h-10 items-center gap-2 text-sm text-slate-700"><input name="is_active" type="checkbox" defaultChecked /> Activo</label>
            <Button className="md:col-span-2"><PlusCircle className="h-4 w-4" /> Guardar perfil</Button>
          </form>
        </Panel>
      </div>
    </AppShell>
  );
}

function Tab({ active, label, onClick }: { active: boolean; label: string; onClick: () => void }) {
  return <button type="button" onClick={onClick} className={`h-10 rounded-md border px-4 text-sm font-medium ${active ? "border-slate-950 bg-slate-950 text-white" : "border-slate-200 bg-white text-slate-700"}`}>{label}</button>;
}

function toNumber(value: FormDataEntryValue | null) {
  const text = String(value ?? "").trim();
  return text ? Number(text) : undefined;
}

function speedOf(profile: ProfileCatalog) {
  return profile.speed_kbps ?? profile.maximum_kbps ?? profile.pir_kbps ?? null;
}

function formatKbps(value: number | null) {
  if (!value) return "-";
  if (value >= 1000000) return `${(value / 1000000).toFixed(2)} Gbps`;
  return `${Math.round(value / 1000)} Mbps`;
}

function serviceLabel(value: string) {
  return ({ internet: "Internet", gestion: "Gestion", voip: "VoIP", iptv: "IPTV", otro: "Otro" } as Record<string, string>)[value] ?? value;
}
