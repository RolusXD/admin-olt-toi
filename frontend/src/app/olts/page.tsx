"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { CheckCircle2, Database, Eye, Plus, RefreshCw, Server, ShieldCheck, X } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/button";
import { EnvironmentBadge } from "@/components/ui/environment-badge";
import { Input } from "@/components/ui/input";
import { Panel } from "@/components/ui/panel";
import { api } from "@/services/api";
import { useApiData } from "@/hooks/useApiData";
import type { ImportConfirmResult, ImportPreview, Olt, OltInventorySummary, ReadOnlyCheckResult } from "@/types";

type TechnicalSync = { cards: boolean; pon_ports: boolean; uplinks: boolean };

export default function OltsPage() {
  const [showLab, setShowLab] = useState(false);
  const [showIncomplete, setShowIncomplete] = useState(false);
  const [showWizard, setShowWizard] = useState(false);
  const [wizardInitialOlt, setWizardInitialOlt] = useState<Olt | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const olts = useApiData<Olt[]>(() => api.olts({ environment: showLab ? undefined : "production", include_incomplete: showIncomplete }), [], [showLab, showIncomplete, reloadKey]);

  return (
    <AppShell>
      <div className="space-y-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h2 className="text-2xl font-semibold text-slate-950">OLTs</h2>
            <p className="mt-1 text-sm text-muted">Alta, importacion inicial y gestion tecnica read-only.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => setReloadKey((value) => value + 1)}>
              <RefreshCw className="h-4 w-4" /> Refrescar
            </Button>
            <Button onClick={() => { setWizardInitialOlt(null); setShowWizard(true); }}>
              <Plus className="h-4 w-4" /> Agregar OLT e Importar
            </Button>
          </div>
        </div>

        {showWizard && (
          <OltImportWizard
            initialOlt={wizardInitialOlt}
            onClose={() => setShowWizard(false)}
            onFinished={() => setReloadKey((value) => value + 1)}
          />
        )}

        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input type="checkbox" checked={showLab} onChange={(event) => setShowLab(event.target.checked)} /> Mostrar laboratorio
        </label>
        <label className="flex items-center gap-2 text-sm text-slate-700"><input type="checkbox" checked={showIncomplete} onChange={(event) => setShowIncomplete(event.target.checked)} /> Mostrar OLTs pendientes/incompletas</label>

        <Panel className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1200px] text-left text-sm">
              <thead className="bg-slate-50 text-slate-950">
                <tr>
                  <th className="px-4 py-3">Ver</th><th className="px-4 py-3">ID interno</th><th className="px-4 py-3">OLT Code</th>
                  <th className="px-4 py-3">Entorno</th><th className="px-4 py-3">Estado</th><th className="px-4 py-3">Nombre</th>
                  <th className="px-4 py-3">IP del OLT</th><th className="px-4 py-3">TCP</th><th className="px-4 py-3">UDP</th>
                  <th className="px-4 py-3">Vendor</th><th className="px-4 py-3">Version hardware</th><th className="px-4 py-3">Version software</th><th className="px-4 py-3">Importacion</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {olts.data.map((olt) => (
                  <tr key={olt.id} className="odd:bg-white even:bg-slate-50/70">
                    <td className="px-4 py-3"><Link href={`/olts/${olt.id}`} className="inline-flex text-primary"><Eye className="h-4 w-4" /></Link></td>
                    <td className="px-4 py-3">{olt.id}</td><td className="px-4 py-3 font-medium text-primary">{olt.olt_code}</td>
                    <td className="px-4 py-3"><EnvironmentBadge environment={olt.environment} /></td><td className="px-4 py-3">{olt.status}</td>
                    <td className="px-4 py-3">{olt.name}</td><td className="px-4 py-3">{olt.ip_address}</td><td className="px-4 py-3">{olt.telnet_port}</td>
                    <td className="px-4 py-3">{olt.snmp_udp_port}</td><td className="px-4 py-3">{olt.vendor}</td>
                    <td className="px-4 py-3">{olt.hardware_version ?? "-"}</td><td className="px-4 py-3">{olt.software_version ?? olt.firmware}</td>
                    <td className="px-4 py-3"><div className="flex items-center gap-2"><ImportStatus status={olt.initial_import_status} />{olt.initial_import_status !== "confirmed" && <Button type="button" variant="secondary" onClick={() => { setWizardInitialOlt(olt); setShowWizard(true); }}>Continuar</Button>}</div></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      </div>
    </AppShell>
  );
}

function OltImportWizard({ initialOlt, onClose, onFinished }: { initialOlt: Olt | null; onClose: () => void; onFinished: () => void }) {
  const [step, setStep] = useState(initialOlt ? 2 : 1);
  const [olt, setOlt] = useState<Olt | null>(initialOlt);
  const [connection, setConnection] = useState<ReadOnlyCheckResult | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [result, setResult] = useState<ImportConfirmResult | null>(null);
  const [inventory, setInventory] = useState<OltInventorySummary | null>(null);
  const [technicalSync, setTechnicalSync] = useState<TechnicalSync | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const connectionValidated = Boolean(connection?.connection_success && connection.errors.length === 0);
  const criticalWarnings = preview?.critical_errors ?? [];

  async function closeWizard() {
    if (olt && olt.initial_import_status !== "confirmed" && result?.status !== "confirmed") {
      await api.cancelOltImport(olt.id);
      onFinished();
    }
    onClose();
  }

  async function createOlt(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy("create"); setError(null);
    try {
      const created = await api.createOlt({
        olt_code: String(form.get("olt_code") ?? "").trim(), name: String(form.get("name") ?? "").trim(),
        ip_address: String(form.get("ip_address") ?? "").trim(), telnet_port: Number(form.get("telnet_port") || 23),
        username: String(form.get("username") ?? "").trim(), password: String(form.get("password") ?? ""),
        vendor: String(form.get("vendor") || "ZTE"), model: String(form.get("model") || "C300"),
        firmware: String(form.get("firmware") || "V1.2.5P3"), connection_type: "telnet",
        environment: String(form.get("environment") || "production"), pon_supported_types: "GPON", status: "unknown",
        snmp_udp_port: 161,
      });
      setOlt(created); setStep(2); onFinished();
    } catch (exc) { setError(exc instanceof Error ? exc.message : "No se pudo crear la OLT"); }
    finally { setBusy(null); }
  }

  async function testConnection() {
    if (!olt) return;
    setBusy("connection"); setError(null); setConnection(null);
    try { setConnection(await api.readOnlyCheck(olt.id)); }
    catch (exc) { setError(exc instanceof Error ? exc.message : "Fallo la prueba read-only"); }
    finally { setBusy(null); }
  }

  async function createPreview() {
    if (!olt || !connectionValidated) { setError("Debe completar una prueba read-only exitosa antes de importar."); return; }
    setBusy("preview"); setError(null);
    try { setPreview(await api.previewImportFromTelnet(olt.id)); setStep(4); }
    catch (exc) { setError(exc instanceof Error ? exc.message : "No se pudo generar el preview"); }
    finally { setBusy(null); }
  }

  async function confirmImport() {
    if (!olt || !preview || !connectionValidated || criticalWarnings.length) return;
    setBusy("confirm"); setError(null);
    try {
      const confirmed = await api.confirmImport(preview.import_job_id);
      setResult(confirmed);
      const technical = await Promise.allSettled([api.syncCards(olt.id), api.syncPonStatus(olt.id), api.syncUplinks(olt.id)]);
      setTechnicalSync({ cards: technical[0].status === "fulfilled", pon_ports: technical[1].status === "fulfilled", uplinks: technical[2].status === "fulfilled" });
      setInventory(await api.oltInventorySummary(olt.id));
      setStep(5); onFinished();
    } catch (exc) { setError(exc instanceof Error ? exc.message : "No se pudo confirmar la importacion"); }
    finally { setBusy(null); }
  }

  return (
    <Panel className="p-4">
      <div className="mb-5 flex items-start justify-between gap-3">
        <div><h3 className="font-semibold text-slate-950">Agregar OLT e Importar</h3><p className="text-sm text-muted">Flujo controlado de cinco pasos. Solo lectura sobre la OLT.</p></div>
        <Button type="button" variant="secondary" onClick={closeWizard}><X className="h-4 w-4" /></Button>
      </div>
      <div className="mb-5 grid grid-cols-2 gap-2 md:grid-cols-5">
        {["Conexion", "Test read-only", "Preview", "Confirmar", "Resultado"].map((label, index) => (
          <div key={label} className={`border-b-2 pb-2 text-xs font-medium ${step === index + 1 ? "border-primary text-primary" : step > index + 1 ? "border-emerald-500 text-emerald-700" : "border-slate-200 text-muted"}`}>{index + 1}. {label}</div>
        ))}
      </div>
      {error && <div className="mb-4 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">{error}</div>}

      {step === 1 && <form className="grid gap-3 md:grid-cols-4" onSubmit={createOlt}>
        <Input name="olt_code" placeholder="OLT Code" required /><Input name="name" placeholder="Nombre" required />
        <Input name="ip_address" placeholder="IP o host" required /><Input name="telnet_port" type="number" defaultValue={23} required />
        <Input name="username" placeholder="Usuario Telnet" required /><Input name="password" type="password" placeholder="Contrasena Telnet" required />
        <Input name="vendor" defaultValue="ZTE" placeholder="Fabricante" /><Input name="model" defaultValue="C300" placeholder="Modelo" />
        <Input name="firmware" defaultValue="V1.2.5P3" placeholder="Firmware" />
        <select name="environment" className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm" defaultValue="production"><option value="production">Produccion</option><option value="lab">Laboratorio</option></select>
        <Button className="md:col-span-2" disabled={busy !== null}><Server className="h-4 w-4" /> Crear OLT</Button>
      </form>}

      {step === 2 && olt && <div className="space-y-4">
        <OltIdentity olt={olt} />
        <div className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-950">Ejecuta show version-running, show card y show gpon onu state. No modifica la OLT.</div>
        <div className="flex flex-wrap gap-2"><Button onClick={testConnection} disabled={busy !== null}><ShieldCheck className="h-4 w-4" /> Probar conexion read-only</Button><Button variant="secondary" onClick={() => setStep(3)} disabled={!connectionValidated}>Continuar</Button></div>
        {connection && <div className="text-sm text-slate-700">Conexion: {connection.connection_success ? "exitosa" : "fallida"} · Firmware: {connection.firmware_detected ?? "-"} · ONUs: {connection.onu_counts.total} · Errores: {connection.errors.length}</div>}
      </div>}

      {step === 3 && olt && <div className="space-y-4">
        <OltIdentity olt={olt} /><div className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-950">La importacion ejecuta solamente show running-config y crea un preview sin modificar inventario.</div>
        <Button onClick={createPreview} disabled={busy !== null || !connectionValidated}><Database className="h-4 w-4" /> Ejecutar importacion inicial</Button>
      </div>}

      {step === 4 && olt && preview && <div className="space-y-4">
        <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950">Los datos importados se asociaran a {olt.olt_code} - {olt.name}.</div>
        <CountGrid items={[["ONUs", preview.onus], ["VLANs", preview.vlans], ["Perfiles", preview.gpon_profiles], ["Tipos ONU", preview.onu_types], ["PON", preview.pon_ports], ["Uplinks", preview.uplinks ?? 0], ["Zonas", preview.zones_detected.length], ["NAPs", preview.naps_detected.length]]} />
        <div><div className="mb-2 text-sm font-medium text-slate-900">Warnings tecnicos ({preview.warnings.length})</div><div className="max-h-40 overflow-auto rounded-md border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700">{preview.warnings.length ? preview.warnings.map((warning) => <div key={warning}>{warning}</div>) : "Sin warnings"}</div></div>
        <div className="text-sm text-slate-700">Datos heredados incompletos: {preview.legacy_incomplete.length}. Se conservaran en cada ficha ONU sin bloquear la importacion.</div>
        {criticalWarnings.length > 0 && <div className="text-sm text-red-800">El preview contiene {criticalWarnings.length} errores criticos y no puede confirmarse.</div>}
        <div className="flex gap-2"><Button variant="secondary" onClick={() => setStep(3)}>Volver</Button><Button onClick={confirmImport} disabled={busy !== null || criticalWarnings.length > 0}><CheckCircle2 className="h-4 w-4" /> Confirmar importacion</Button></div>
      </div>}

      {step === 5 && olt && result && <div className="space-y-4">
        <div className="flex items-center gap-2 text-sm font-semibold text-emerald-800"><CheckCircle2 className="h-5 w-5" /> Importacion confirmada para {olt.olt_code}</div>
        <CountGrid items={[["ONUs", inventory?.onus ?? result.onus_upserted], ["VLANs", inventory?.vlans ?? result.vlans_upserted], ["Perfiles", inventory?.profiles ?? result.gpon_profiles_upserted], ["Tipos ONU", result.onu_types_upserted], ["PON", inventory?.pon_ports ?? result.pon_ports_upserted], ["Uplinks", result.uplinks_upserted ?? 0], ["Zonas", result.zones_upserted], ["NAPs", result.naps_upserted]]} />
        <div className="grid gap-2 sm:grid-cols-3"><SyncStatus label="Tarjetas" success={technicalSync?.cards} /><SyncStatus label="Estado PON" success={technicalSync?.pon_ports} /><SyncStatus label="Uplinks" success={technicalSync?.uplinks} /></div>
        <div className="flex gap-2"><Link href={`/olts/${olt.id}`}><Button>Ver OLT</Button></Link><Button variant="secondary" onClick={onClose}>Cerrar</Button></div>
      </div>}
    </Panel>
  );
}

function OltIdentity({ olt }: { olt: Olt }) { return <div className="flex flex-wrap items-center gap-3 text-sm"><span className="font-semibold text-slate-950">{olt.olt_code}</span><span>{olt.name}</span><span>{olt.ip_address}:{olt.telnet_port}</span><EnvironmentBadge environment={olt.environment} /></div>; }
function CountGrid({ items }: { items: Array<[string, number]> }) { return <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">{items.map(([label, value]) => <div key={label} className="rounded-md border border-slate-200 p-3"><div className="text-xs text-muted">{label}</div><div className="text-xl font-semibold text-slate-950">{value}</div></div>)}</div>; }
function SyncStatus({ label, success }: { label: string; success?: boolean }) { return <div className={`rounded-md border p-3 text-sm ${success ? "border-emerald-200 bg-emerald-50 text-emerald-900" : "border-amber-200 bg-amber-50 text-amber-900"}`}>{label}: {success ? "sincronizado read-only" : "requiere revision"}</div>; }
function ImportStatus({ status }: { status: string }) { const labels: Record<string, string> = { draft: "Pendiente de importacion", connection_tested: "Conexion probada", preview_created: "Preview creado", failed: "Fallida", cancelled: "Cancelada", confirmed: "Confirmada" }; const ok = status === "confirmed"; return <span className={`whitespace-nowrap rounded px-2 py-1 text-xs ${ok ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-900"}`}>{labels[status] ?? status}</span>; }
