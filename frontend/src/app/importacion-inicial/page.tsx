"use client";

import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from "react";
import { CheckCircle2, FileText, Loader2, ShieldCheck, Upload } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";
import { EnvironmentBadge } from "@/components/ui/environment-badge";
import { api } from "@/services/api";
import { useApiData } from "@/hooks/useApiData";
import type { ImportConfirmResult, ImportJob, ImportPreview, Olt, OltInventorySummary } from "@/types";

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
  const [previewStage, setPreviewStage] = useState<PreviewStage>("idle");
  const [importJob, setImportJob] = useState<ImportJob | null>(null);
  const [jobRefreshing, setJobRefreshing] = useState(false);

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
    setImportJob(null);
  }

  async function runTextPreview(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setConfirmResult(null);
    setImportJob(null);
    setLoading("text");
    setPreviewStage("analysing");
    try {
      const result = await api.previewImportFromText(oltId, rawConfig);
      setPreview(result);
      void refreshImportJob(result.import_job_id);
      setPreviewStage("ready");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "No se pudo crear el preview");
      setPreviewStage("error");
    } finally {
      setLoading(null);
    }
  }

  async function runFilePreview() {
    if (!file) return;
    setError(null);
    setConfirmResult(null);
    setImportJob(null);
    setLoading("file");
    setPreviewStage("analysing");
    try {
      const result = await api.previewImportFromFile(oltId, file);
      setPreview(result);
      void refreshImportJob(result.import_job_id);
      setPreviewStage("ready");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "No se pudo leer el archivo");
      setPreviewStage("error");
    } finally {
      setLoading(null);
    }
  }

  async function runTelnetPreview() {
    setError(null);
    setConfirmResult(null);
    setImportJob(null);
    setLoading("telnet");
    setPreviewStage("preparing");
    try {
      setPreviewStage("connecting");
      const result = await api.previewImportFromTelnet(oltId);
      setPreview(result);
      void refreshImportJob(result.import_job_id);
      setPreviewStage("ready");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "No se pudo leer la OLT");
      setPreviewStage("error");
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
      await refreshImportJob(preview.import_job_id);
      setInventorySummary(await api.oltInventorySummary(oltId));
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "No se pudo confirmar la importacion");
    } finally {
      setLoading(null);
    }
  }

   async function refreshImportJob(jobId: number) {
    setJobRefreshing(true);
    try {
      setImportJob(await api.importJob(jobId));
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "No se pudo actualizar el estado del import job");
    } finally {
      setJobRefreshing(false);
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
                  setPreviewStage("idle");
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
                    setPreviewStage("idle");
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
              Esta operación no modifica la OLT. Solo ejecuta show running-config en modo read-only y genera un preview.
            </div>
            <Button type="button" onClick={runTelnetPreview} disabled={!oltId || loading !== null}>
              <ShieldCheck className="h-4 w-4" /> Importar desde OLT real
            </Button>
            <PreviewProgress stage={previewStage} loading={loading === "telnet"} />
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

            <div className="mt-6">
              <ImportJobState
                job={importJob}
                preview={preview}
                refreshing={jobRefreshing}
                onRefresh={() => refreshImportJob(preview.import_job_id)}
              />
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

type PreviewStage = "idle" | "preparing" | "connecting" | "analysing" | "ready" | "error";

function PreviewProgress({ stage, loading }: { stage: PreviewStage; loading: boolean }) {
  const steps: Array<{ key: PreviewStage; label: string }> = [
    { key: "preparing", label: "Preparando importacion..." },
    { key: "connecting", label: "Conectando y leyendo configuracion de la OLT..." },
    { key: "analysing", label: "Analizando configuracion y generando preview..." },
    { key: "ready", label: "Preview generado correctamente." },
  ];

  if (stage === "idle") {
    return (
      <div className="rounded-md border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
        Presiona "Importar desde OLT real" para iniciar la importacion inicial.
      </div>
    );
  }

  const activeIndex = stage === "error" ? -1 : steps.findIndex((step) => step.key === stage);

  return (
    <div className="space-y-2 rounded-md border border-slate-200 bg-white p-3 text-sm">
      {stage === "error" && (
        <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-red-800">
          Error durante la generación del preview.
        </div>
      )}
      <ul className="space-y-2">
        {steps.map((step, index) => {
          const isActive = index === activeIndex;
          const isCompleted = activeIndex > index;
          return (
            <li
              key={step.key}
              className={`flex items-start gap-2 rounded-md border px-3 py-2 text-xs sm:text-sm ${
                isActive
                  ? "border-emerald-300 bg-emerald-50 text-emerald-900"
                  : isCompleted
                    ? "border-slate-200 bg-slate-50 text-slate-700"
                    : "border-slate-100 bg-white text-slate-500"
              }`}
            >
              {isActive ? <Loader2 className="mt-0.5 h-3.5 w-3.5 animate-spin" /> : <span className="mt-0.5 h-3.5 w-3.5 rounded-full border border-current" />}
              <span>{step.label}</span>
            </li>
          );
        })}
      </ul>
      {loading && stage !== "ready" && stage !== "error" && (
        <p className="text-xs text-slate-500">Esta etapa no modifica la OLT; puedes cerrar esta ventana y reintentar si algo falla.</p>
      )}
    </div>
  );
}

type ImportJobStateProps = {
  job: ImportJob | null;
  preview: ImportPreview;
  refreshing: boolean;
  onRefresh: () => void;
};

function ImportJobState({ job, preview, refreshing, onRefresh }: ImportJobStateProps) {
  const summary = job?.parsed_summary ?? null;
  const warnings = (job?.snapshot_warnings && job.snapshot_warnings.length > 0
    ? job.snapshot_warnings
    : summary?.warnings) ?? [];
  const criticalErrors = summary?.critical_errors ?? [];

  const items: Array<[string, number]> = [
    ["ONUs", summary?.onus ?? preview.onus],
    ["VLANs", summary?.vlans ?? preview.vlans],
    ["Perfiles", summary?.gpon_profiles ?? preview.gpon_profiles],
    ["PONs", summary?.pon_ports ?? preview.pon_ports],
    ["Uplinks", summary?.uplinks ?? preview.uplinks ?? 0],
    ["NAPs", (summary?.naps_detected ?? preview.naps_detected).length],
    ["Zonas", (summary?.zones_detected ?? preview.zones_detected).length],
    ["Warnings", warnings.length],
    ["Errores", criticalErrors.length],
  ];

  return (
    <div className="space-y-4 rounded-md border border-slate-200 bg-slate-50 p-3 text-sm text-slate-900">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="text-xs font-semibold uppercase text-muted">Estado del import job</div>
          <div className="text-sm text-slate-900">
            Job: <span className="font-medium">{job?.status ?? "desconocido"}</span>
            {" · "}
            Snapshot: <span className="font-medium">{job?.snapshot_status ?? "desconocido"}</span>
          </div>
        </div>
        <Button type="button" className="h-8 px-2 text-xs" variant="secondary" onClick={onRefresh} disabled={refreshing}>
          {refreshing ? "Actualizando..." : "Actualizar estado"}
        </Button>
      </div>

      <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
        {items.map(([label, value]) => (
          <div key={label} className="rounded-md border border-slate-200 bg-white p-3">
            <div className="text-xs text-muted">{label}</div>
            <div className="text-lg font-semibold text-slate-950">{value}</div>
          </div>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <PreviewList title="Warnings reales" values={warnings} />
        <PreviewList title="Errores" values={criticalErrors.map((value) => String(value))} />
      </div>
    </div>
  );
}
