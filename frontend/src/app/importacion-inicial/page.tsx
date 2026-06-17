"use client";

import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from "react";
import { CheckCircle2, FileText, ShieldCheck, Upload } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";
import { EnvironmentBadge } from "@/components/ui/environment-badge";
import { api } from "@/services/api";
import { useApiData } from "@/hooks/useApiData";
import type { ImportConfirmResult, ImportPreview, Olt, OltInventorySummary } from "@/types";

const emptyPreviewText = "";

export default function InitialImportPage() {
  const olts = useApiData<Olt[]>(() => api.olts({ environment: "production" }), []);
  const [showLab, setShowLab] = useState(false);
  const [selectedOltId, setSelectedOltId] = useState("");
  const [rawConfig, setRawConfig] = useState(emptyPreviewText);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [confirmResult, setConfirmResult] = useState<ImportConfirmResult | null>(null);
  const [inventorySummary, setInventorySummary] = useState<OltInventorySummary | null>(null);
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const oltId = useMemo(() => Number(selectedOltId || olts.data[0]?.id || 0), [selectedOltId, olts.data]);
  const selectedOlt = olts.data.find((olt) => olt.id === oltId) ?? null;

  useEffect(() => {
    if (!oltId) return;
    let active = true;
    api
      .oltInventorySummary(oltId)
      .then((summary) => {
        if (active) setInventorySummary(summary);
      })
      .catch(() => {
        if (active) setInventorySummary(null);
      });
    return () => {
      active = false;
    };
  }, [oltId]);

  function selectFile(event: ChangeEvent<HTMLInputElement>) {
    setFile(event.target.files?.[0] ?? null);
    setPreview(null);
    setConfirmResult(null);
  }

  async function runTextPreview(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setConfirmResult(null);
    setLoading("text");
    try {
      setPreview(await api.previewImportFromText(oltId, rawConfig));
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "No se pudo crear el preview");
    } finally {
      setLoading(null);
    }
  }

  async function runFilePreview() {
    if (!file) return;
    setError(null);
    setConfirmResult(null);
    setLoading("file");
    try {
      setPreview(await api.previewImportFromFile(oltId, file));
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "No se pudo leer el archivo");
    } finally {
      setLoading(null);
    }
  }

  async function runTelnetPreview() {
    setError(null);
    setConfirmResult(null);
    setLoading("telnet");
    try {
      setPreview(await api.previewImportFromTelnet(oltId));
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "No se pudo leer la OLT");
    } finally {
      setLoading(null);
    }
  }

  async function confirmImport() {
    if (!preview) return;
    setError(null);
    setLoading("confirm");
    try {
      setConfirmResult(await api.confirmImport(preview.import_job_id));
      setInventorySummary(await api.oltInventorySummary(oltId));
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "No se pudo confirmar la importacion");
    } finally {
      setLoading(null);
    }
  }

  return (
    <AppShell>
      <div className="space-y-5">
        <div>
          <h1 className="text-xl font-semibold text-slate-950">Importacion inicial</h1>
          <p className="text-sm text-muted">Preview seguro y confirmacion controlada para configuraciones ZTE C300.</p>
        </div>

        {error && <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">{error}</div>}

        <Panel className="p-4">
          <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
            <label className="space-y-2 text-sm">
              <span className="font-medium text-slate-800">OLT</span>
              <select
                className="h-9 w-full rounded-md border border-slate-200 bg-white px-3 text-sm"
                value={selectedOltId || olts.data[0]?.id || ""}
                onChange={(event) => {
                  setSelectedOltId(event.target.value);
                  setPreview(null);
                  setConfirmResult(null);
                }}
              >
                {olts.data.map((olt) => (
                  <option key={olt.id} value={olt.id}>
                    {olt.olt_code} - {olt.display_name || olt.name} - {olt.environment}
                  </option>
                ))}
              </select>
              <label className="mt-2 inline-flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={showLab}
                  onChange={async (event) => {
                    setShowLab(event.target.checked);
                    olts.setData(await api.olts(event.target.checked ? {} : { environment: "production" }));
                    setSelectedOltId("");
                    setPreview(null);
                    setConfirmResult(null);
                  }}
                />
                Mostrar laboratorio
              </label>
            </label>
            <div className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-950">
              Esta operación no modifica la OLT. Solo lee la configuración actual para crear la base inicial del sistema.
            </div>
          </div>
          <div className="mt-4">
            <InventorySummary summary={inventorySummary} />
          </div>
          <div className="mt-3">{selectedOlt && <EnvironmentBadge environment={selectedOlt.environment} />}</div>
        </Panel>

        <Panel className="p-4">
          <div className="space-y-4">
            <div className="flex items-center gap-2 text-sm font-semibold text-slate-950">
              <ShieldCheck className="h-4 w-4" /> Produccion: Importar desde OLT real
            </div>
            <div className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-950">
              Esta operación no modifica la OLT. Solo ejecuta show running-config en modo read-only.
            </div>
            <Button type="button" onClick={runTelnetPreview} disabled={!oltId || loading !== null}>
              <ShieldCheck className="h-4 w-4" /> Importar desde OLT real
            </Button>
          </div>
        </Panel>

        <div className="grid gap-5 xl:grid-cols-2">
          <Panel className="p-4">
            <form className="space-y-3" onSubmit={runTextPreview}>
              <div className="flex items-center gap-2 text-sm font-semibold text-slate-950">
                <FileText className="h-4 w-4" /> Laboratorio: Pegar configuracion
              </div>
              <textarea
                className="min-h-[320px] w-full resize-y rounded-md border border-slate-200 bg-white p-3 font-mono text-xs outline-none focus:border-primary focus:ring-2 focus:ring-primary/15"
                value={rawConfig}
                onChange={(event) => setRawConfig(event.target.value)}
                placeholder="show running-config"
              />
              <Button type="submit" disabled={!oltId || !rawConfig.trim() || loading !== null}>
                Ejecutar preview
              </Button>
            </form>
          </Panel>

          <Panel className="p-4">
            <div className="space-y-4">
              <div className="flex items-center gap-2 text-sm font-semibold text-slate-950">
                <Upload className="h-4 w-4" /> Laboratorio: Subir archivo TXT
              </div>
              <input
                className="block w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm"
                type="file"
                accept=".txt,text/plain"
                onChange={selectFile}
              />
              <div className="flex flex-wrap gap-3">
                <Button type="button" onClick={runFilePreview} disabled={!oltId || !file || loading !== null}>
                  Ejecutar preview desde archivo
                </Button>
              </div>
              <div className="rounded-md border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
                Archivo seleccionado: {file?.name ?? "ninguno"}
              </div>
            </div>
          </Panel>
        </div>

        {preview && (
          <Panel className="p-4">
            <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h2 className="text-sm font-semibold text-slate-950">Resumen del preview</h2>
                <p className="text-sm text-muted">Import job #{preview.import_job_id}</p>
              </div>
              <Button type="button" onClick={confirmImport} disabled={loading !== null || confirmResult !== null}>
                Confirmar importacion
              </Button>
            </div>
            <div className="mb-4 rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950">
              Los datos importados se asociarán a la OLT seleccionada: {selectedOlt?.olt_code ?? ""} - {selectedOlt?.name ?? ""} ({selectedOlt?.environment ?? ""}).
            </div>
            <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
              {[
                ["VLANs", preview.vlans],
                ["Perfiles GPON", preview.gpon_profiles],
                ["Tipos ONU", preview.onu_types],
                ["Puertos PON", preview.pon_ports],
                ["ONUs", preview.onus],
                ["Warnings", preview.warnings.length],
              ].map(([label, value]) => (
                <div key={label} className="rounded-md border border-slate-200 bg-slate-50 p-3">
                  <div className="text-xs text-muted">{label}</div>
                  <div className="text-xl font-semibold text-slate-950">{value}</div>
                </div>
              ))}
            </div>
            <div className="mt-4 grid gap-4 lg:grid-cols-3">
              <PreviewList title="Zonas detectadas" values={preview.zones_detected} />
              <PreviewList title="NAPs detectadas" values={preview.naps_detected} />
              <PreviewList title="Warnings" values={preview.warnings} />
            </div>
          </Panel>
        )}

        {confirmResult && (
          <Panel className="p-4">
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-950">
              <CheckCircle2 className="h-4 w-4 text-primary" /> Importacion confirmada
            </div>
            <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
              {[
                ["VLANs", confirmResult.vlans_upserted],
                ["Perfiles", confirmResult.gpon_profiles_upserted],
                ["Tipos ONU", confirmResult.onu_types_upserted],
                ["PON", confirmResult.pon_ports_upserted],
                ["ONUs", confirmResult.onus_upserted],
                ["NAPs", confirmResult.naps_upserted],
              ].map(([label, value]) => (
                <div key={label} className="rounded-md border border-slate-200 bg-white p-3">
                  <div className="text-xs text-muted">{label}</div>
                  <div className="text-xl font-semibold text-slate-950">{value}</div>
                </div>
              ))}
            </div>
          </Panel>
        )}
      </div>
    </AppShell>
  );
}

function InventorySummary({ summary }: { summary: OltInventorySummary | null }) {
  const items = [
    ["ONUs", summary?.onus ?? 0],
    ["PON ports", summary?.pon_ports ?? 0],
    ["VLANs", summary?.vlans ?? 0],
    ["Perfiles", summary?.profiles ?? 0],
  ];
  return (
    <div className="rounded-md border border-slate-200 bg-white p-3">
      <div className="mb-3 flex flex-col gap-1 text-sm text-slate-950">
        <span className="font-semibold">Inventario asociado a la OLT seleccionada</span>
        <span className="text-muted">
          {summary ? `${summary.olt_code} - ${summary.olt_name} · ${summary.environment} · ${importStatusLabel(summary.initial_import_status)}` : "Sin OLT seleccionada"}
        </span>
      </div>
      <div className="grid gap-3 md:grid-cols-5">
        {items.map(([label, value]) => (
          <div key={label} className="rounded-md bg-slate-50 p-3">
            <div className="text-xs text-muted">{label}</div>
            <div className="text-lg font-semibold text-slate-950">{value}</div>
          </div>
        ))}
        <div className="rounded-md bg-slate-50 p-3">
          <div className="text-xs text-muted">Ultima importacion confirmada</div>
          <div className="text-sm font-medium text-slate-950">
            {summary?.last_confirmed_import ? new Date(summary.last_confirmed_import).toLocaleString() : "Sin confirmar"}
          </div>
        </div>
      </div>
    </div>
  );
}

function importStatusLabel(status: string) {
  const labels: Record<string, string> = {
    pending: "Pendiente de importacion inicial",
    preview_created: "Preview creado",
    confirmed: "Importacion confirmada",
    failed: "Fallida",
  };
  return labels[status] ?? status;
}

function PreviewList({ title, values }: { title: string; values: string[] }) {
  return (
    <div className="rounded-md border border-slate-200 p-3">
      <div className="mb-2 text-xs font-medium uppercase text-muted">{title}</div>
      <div className="flex max-h-36 flex-wrap gap-2 overflow-auto">
        {values.length ? (
          values.map((value) => (
            <span key={value} className="rounded-md bg-slate-100 px-2 py-1 text-xs text-slate-700">
              {value}
            </span>
          ))
        ) : (
          <span className="text-sm text-muted">Sin datos</span>
        )}
      </div>
    </div>
  );
}
