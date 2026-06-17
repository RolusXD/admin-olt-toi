"use client";

import { FormEvent, useMemo, useState } from "react";
import { Boxes, PlusCircle, RefreshCw } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/button";
import { EnvironmentBadge } from "@/components/ui/environment-badge";
import { Input } from "@/components/ui/input";
import { Panel } from "@/components/ui/panel";
import { api } from "@/services/api";
import { useApiData } from "@/hooks/useApiData";
import type { Olt, ProfileCatalog } from "@/types";

type Direction = "upload" | "download";

export default function ProfileCatalogsPage() {
  const [showLab, setShowLab] = useState(false);
  const [direction, setDirection] = useState<Direction>("upload");
  const [selectedOltId, setSelectedOltId] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const olts = useApiData<Olt[]>(() => api.olts(showLab ? {} : { environment: "production" }), [], [showLab, reloadKey]);
  const catalogs = useApiData<ProfileCatalog[]>(
    () =>
      api.profileCatalogs({
        direction,
        is_active: true,
        ...(selectedOltId ? { olt_id: selectedOltId } : {}),
      }),
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
    if (!oltId) {
      setError("Seleccione una OLT antes de crear el catalogo.");
      return;
    }
    const olt = olts.data.find((item) => item.id === oltId);
    const payload = {
      olt_id: oltId,
      vendor: olt?.vendor ?? "ZTE",
      model: olt?.model ?? "C300",
      firmware: olt?.firmware ?? "V1.2.5P3",
      direction,
      profile_kind: direction === "upload" ? "tcont" : "traffic",
      name: String(form.get("name") ?? "").trim(),
      type_value: toNumber(form.get("type_value")),
      fixed_kbps: toNumber(form.get("fixed_kbps")),
      assured_kbps: toNumber(form.get("assured_kbps")),
      maximum_kbps: toNumber(form.get("maximum_kbps")),
      sir_kbps: toNumber(form.get("sir_kbps")),
      pir_kbps: toNumber(form.get("pir_kbps")),
      notes: String(form.get("notes") ?? "").trim() || undefined,
      source: "manual",
      is_active: true,
    };
    try {
      await api.createProfileCatalog(payload);
      event.currentTarget.reset();
      setReloadKey((value) => value + 1);
      setMessage("Catalogo creado correctamente.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo crear el catalogo.");
    }
  }

  return (
    <AppShell>
      <div className="space-y-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h2 className="text-2xl font-semibold text-slate-950">Catalogos de perfiles GPON</h2>
            <p className="mt-1 text-sm text-muted">Perfiles ZTE C300 separados por subida tcont y bajada traffic.</p>
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
              <select
                className="mt-1 h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm"
                value={selectedOltId}
                onChange={(event) => setSelectedOltId(event.target.value)}
              >
                <option value="">Todas las OLTs visibles</option>
                {olts.data.map((olt) => (
                  <option key={olt.id} value={olt.id}>
                    {olt.olt_code} - {olt.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex h-10 items-center gap-2 text-sm text-slate-700">
              <input type="checkbox" checked={showLab} onChange={(event) => setShowLab(event.target.checked)} />
              Mostrar laboratorio
            </label>
          </div>
          {selectedOlt && (
            <div className="mt-3 flex flex-wrap items-center gap-2 text-sm text-slate-700">
              <EnvironmentBadge environment={selectedOlt.environment} />
              <span>{selectedOlt.vendor} {selectedOlt.model} {selectedOlt.firmware}</span>
            </div>
          )}
        </Panel>

        <div className="flex gap-2">
          <Tab active={direction === "upload"} onClick={() => setDirection("upload")} label="Upload / tcont" />
          <Tab active={direction === "download"} onClick={() => setDirection("download")} label="Download / traffic" />
        </div>

        <Panel className="overflow-hidden">
          <div className="border-b border-slate-200 px-4 py-3">
            <div className="flex items-center gap-2 text-sm font-semibold text-slate-950">
              <Boxes className="h-4 w-4 text-primary" />
              {direction === "upload" ? "Perfiles de subida" : "Perfiles de bajada"}
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-3">OLT</th>
                  <th className="px-4 py-3">Nombre</th>
                  <th className="px-4 py-3">Tipo</th>
                  <th className="px-4 py-3">Parametros</th>
                  <th className="px-4 py-3">Origen</th>
                  <th className="px-4 py-3">Entorno</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {catalogs.data.map((profile) => (
                  <tr key={profile.id}>
                    <td className="px-4 py-3">{profile.olt_code ?? profile.olt_code_snapshot ?? profile.olt_id}</td>
                    <td className="px-4 py-3 font-medium text-slate-950">{profile.name}</td>
                    <td className="px-4 py-3">{profile.profile_kind}</td>
                    <td className="px-4 py-3 text-slate-600">{profile.direction === "upload" ? uploadParams(profile) : downloadParams(profile)}</td>
                    <td className="px-4 py-3">{profile.source}</td>
                    <td className="px-4 py-3">
                      <EnvironmentBadge environment={profile.olt_environment ?? "production"} />
                    </td>
                  </tr>
                ))}
                {!catalogs.data.length && (
                  <tr>
                    <td className="px-4 py-6 text-center text-muted" colSpan={6}>
                      Sin perfiles para el filtro actual.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Panel>

        <Panel className="p-4">
          <div className="mb-4 flex items-center gap-2 text-sm font-semibold text-slate-950">
            <PlusCircle className="h-4 w-4 text-primary" />
            Crear catalogo manual
          </div>
          <form className="grid gap-3 md:grid-cols-4" onSubmit={createCatalog}>
            <select
              key={selectedOltId}
              name="olt_id"
              className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm"
              defaultValue={selectedOltId}
              required
            >
              <option value="">Seleccione OLT</option>
              {olts.data.map((olt) => (
                <option key={olt.id} value={olt.id}>
                  {olt.olt_code}
                </option>
              ))}
            </select>
            <Input name="name" placeholder="Nombre perfil" required />
            {direction === "upload" ? (
              <>
                <Input name="type_value" type="number" placeholder="type" />
                <Input name="maximum_kbps" type="number" placeholder="maximum kbps" />
                <Input name="fixed_kbps" type="number" placeholder="fixed kbps" />
                <Input name="assured_kbps" type="number" placeholder="assured kbps" />
              </>
            ) : (
              <>
                <Input name="sir_kbps" type="number" placeholder="sir kbps" />
                <Input name="pir_kbps" type="number" placeholder="pir kbps" />
              </>
            )}
            <Input className="md:col-span-2" name="notes" placeholder="Notas" />
            <Button className="md:col-span-1">
              <PlusCircle className="h-4 w-4" /> Guardar
            </Button>
          </form>
        </Panel>
      </div>
    </AppShell>
  );
}

function Tab({ active, label, onClick }: { active: boolean; label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`h-10 rounded-md border px-4 text-sm font-medium ${
        active ? "border-slate-950 bg-slate-950 text-white" : "border-slate-200 bg-white text-slate-700"
      }`}
    >
      {label}
    </button>
  );
}

function toNumber(value: FormDataEntryValue | null) {
  const text = String(value ?? "").trim();
  return text ? Number(text) : undefined;
}

function uploadParams(profile: ProfileCatalog) {
  return `type ${profile.type_value ?? "-"} / fixed ${profile.fixed_kbps ?? "-"} / assured ${profile.assured_kbps ?? "-"} / max ${profile.maximum_kbps ?? "-"}`;
}

function downloadParams(profile: ProfileCatalog) {
  return `sir ${profile.sir_kbps ?? "-"} / pir ${profile.pir_kbps ?? "-"}`;
}
