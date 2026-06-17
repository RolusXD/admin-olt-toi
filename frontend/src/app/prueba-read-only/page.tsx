"use client";

import { FormEvent, ReactNode, useMemo, useState } from "react";
import { Activity, Bolt, Edit3, RefreshCw, ShieldCheck } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Panel } from "@/components/ui/panel";
import { EnvironmentBadge } from "@/components/ui/environment-badge";
import { api } from "@/services/api";
import { useApiData } from "@/hooks/useApiData";
import type { DriverCommandLog, Olt, OltPowerSyncResult, OltSyncResult, ReadOnlyCheckResult } from "@/types";

type OltForm = {
  olt_code: string;
  name: string;
  display_name: string;
  ip_address: string;
  telnet_port: string;
  username: string;
  password: string;
  vendor: string;
  model: string;
  firmware: string;
  connection_type: string;
  status: string;
  environment: string;
};

const defaultOltForm: OltForm = {
  olt_code: "",
  name: "",
  display_name: "",
  ip_address: "",
  telnet_port: "23",
  username: "",
  password: "",
  vendor: "ZTE",
  model: "C300",
  firmware: "V1.2.5P3",
  connection_type: "telnet",
  status: "unknown",
  environment: "production",
};

export default function ReadOnlyTestPage() {
  const olts = useApiData<Olt[]>(() => api.olts({ environment: "production" }), []);
  const [showLab, setShowLab] = useState(false);
  const [selectedOltId, setSelectedOltId] = useState("");
  const [editingOltId, setEditingOltId] = useState<number | null>(null);
  const [form, setForm] = useState<OltForm>(defaultOltForm);
  const [savedOlt, setSavedOlt] = useState<Olt | null>(null);
  const [checkResult, setCheckResult] = useState<ReadOnlyCheckResult | null>(null);
  const [syncResult, setSyncResult] = useState<OltSyncResult | null>(null);
  const [powerResult, setPowerResult] = useState<OltPowerSyncResult | null>(null);
  const [logs, setLogs] = useState<DriverCommandLog[]>([]);
  const [limit, setLimit] = useState("5");
  const [interfacesText, setInterfacesText] = useState("");
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const oltId = useMemo(() => Number(selectedOltId || olts.data[0]?.id || 0), [selectedOltId, olts.data]);
  const selectedOlt = olts.data.find((olt) => olt.id === oltId) ?? null;
  const isCreatingOlt = editingOltId === null;
  const requiredCreateFieldsMissing = !form.olt_code.trim() || (isCreatingOlt && !form.password.trim());

  async function refreshOlts() {
    setError(null);
    setLoading("refresh-olts");
    try {
      olts.setData(await api.olts(showLab ? {} : { environment: "production" }));
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "No se pudo refrescar la lista de OLTs");
    } finally {
      setLoading(null);
    }
  }

  async function refreshLogs(currentOltId = oltId) {
    if (!currentOltId) return;
    setLogs(await api.commandLogs(currentOltId, 80));
  }

  function updateForm(field: keyof OltForm, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  function clearForm() {
    setEditingOltId(null);
    setSavedOlt(null);
    setForm(defaultOltForm);
  }

  function loadSelectedOltForEdit() {
    if (!selectedOlt) {
      setError("Selecciona una OLT registrada para editar.");
      return;
    }
    setError(null);
    setEditingOltId(selectedOlt.id);
    setSavedOlt(selectedOlt);
    setForm({
      olt_code: selectedOlt.olt_code,
      name: selectedOlt.name,
      display_name: selectedOlt.display_name ?? "",
      ip_address: selectedOlt.ip_address,
      telnet_port: String(selectedOlt.telnet_port ?? 23),
      username: selectedOlt.username,
      password: "",
      vendor: selectedOlt.vendor || "ZTE",
      model: selectedOlt.model || "C300",
      firmware: selectedOlt.firmware || "V1.2.5P3",
      connection_type: selectedOlt.connection_type || "telnet",
      status: selectedOlt.status || "unknown",
      environment: selectedOlt.environment || "production",
    });
  }

  async function saveOlt(event: FormEvent) {
    event.preventDefault();
    setError(null);
    const telnetPort = Number(form.telnet_port);
    if (!form.olt_code.trim()) {
      setError("Codigo OLT es obligatorio.");
      return;
    }
    if (!/^[A-Za-z0-9_-]+$/.test(form.olt_code.trim())) {
      setError("Codigo OLT solo permite letras, numeros, guion y guion bajo.");
      return;
    }
    if (!form.ip_address.trim()) {
      setError("IP/host es obligatorio.");
      return;
    }
    if (!form.username.trim()) {
      setError("Usuario es obligatorio.");
      return;
    }
    if (!Number.isInteger(telnetPort) || telnetPort < 1) {
      setError("Puerto Telnet es obligatorio y debe ser valido.");
      return;
    }
    if (!editingOltId && !form.password.trim()) {
      setError("La contraseña es obligatoria al crear una OLT.");
      return;
    }
    setLoading("save-olt");
    try {
      const payload: Record<string, unknown> = {
        olt_code: form.olt_code.trim().toUpperCase(),
        name: form.name.trim() || form.ip_address.trim(),
        display_name: form.display_name.trim() || null,
        ip_address: form.ip_address.trim(),
        telnet_port: telnetPort,
        username: form.username.trim(),
        vendor: form.vendor.trim() || "ZTE",
        model: form.model.trim() || "C300",
        firmware: form.firmware.trim() || "V1.2.5P3",
        connection_type: form.connection_type.trim() || "telnet",
        status: form.status.trim() || "unknown",
        environment: form.environment,
      };
      if (form.password.trim()) {
        payload.password = form.password;
      }
      const olt = editingOltId ? await api.updateOlt(editingOltId, payload) : await api.createOlt(payload);
      setSavedOlt(olt);
      setEditingOltId(olt.id);
      setForm((current) => ({ ...current, password: "" }));
      olts.setData(await api.olts(showLab ? {} : { environment: "production" }));
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "No se pudo guardar la OLT");
    } finally {
      setLoading(null);
    }
  }

  function useSavedOltForTest() {
    const id = savedOlt?.id ?? editingOltId;
    if (!id) {
      setError("Guarda o carga una OLT antes de usarla para prueba.");
      return;
    }
    setError(null);
    setSelectedOltId(String(id));
    setLogs([]);
    setCheckResult(null);
    setSyncResult(null);
    setPowerResult(null);
  }

  async function runReadOnlyCheck() {
    setError(null);
    if (!selectedOlt?.has_password) {
      setError("Esta OLT no tiene contraseña guardada. Edite la OLT y registre una contraseña antes de probar conexión.");
      return;
    }
    setLoading("check");
    try {
      const result = await api.readOnlyCheck(oltId);
      setCheckResult(result);
      await refreshLogs(oltId);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "No se pudo ejecutar read-only-check");
    } finally {
      setLoading(null);
    }
  }

  async function runSyncOnus() {
    setError(null);
    setLoading("sync-onus");
    try {
      const result = await api.syncOnusReadOnly(oltId);
      setSyncResult(result);
      await refreshLogs(oltId);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "No se pudo sincronizar ONUs");
    } finally {
      setLoading(null);
    }
  }

  async function runSyncPower(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setLoading("sync-power");
    const interfaces = interfacesText
      .split(/\r?\n/)
      .map((item) => item.trim())
      .filter(Boolean);
    try {
      const result = await api.syncPower(oltId, {
        limit: interfaces.length ? undefined : limit,
        interfaces,
      });
      setPowerResult(result);
      await refreshLogs(oltId);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "No se pudo sincronizar potencia");
    } finally {
      setLoading(null);
    }
  }

  return (
    <AppShell>
      <div className="space-y-5">
        <div>
          <h1 className="text-xl font-semibold text-slate-950">Prueba OLT Read-Only</h1>
          <p className="text-sm text-muted">Validacion Telnet controlada con comandos show permitidos.</p>
        </div>

        {error && <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">{error}</div>}

        <Panel className="p-4">
          <div className="grid gap-4 xl:grid-cols-[360px_1fr]">
            <div className="space-y-3">
              <div className="flex items-center justify-between gap-3">
                <div className="text-sm font-semibold text-slate-950">OLT registrada</div>
                <div className="flex flex-wrap gap-2">
                  <label className="inline-flex items-center gap-2 text-sm text-slate-700">
                    <input
                      type="checkbox"
                      checked={showLab}
                      onChange={async (event) => {
                        setShowLab(event.target.checked);
                        olts.setData(await api.olts(event.target.checked ? {} : { environment: "production" }));
                      }}
                    />
                    Mostrar laboratorio
                  </label>
                  <Button type="button" variant="secondary" onClick={refreshOlts} disabled={loading !== null}>
                    <RefreshCw className="h-4 w-4" /> Refrescar lista
                  </Button>
                </div>
              </div>
              <select
                className="h-9 w-full rounded-md border border-slate-200 bg-white px-3 text-sm"
                value={selectedOltId || olts.data[0]?.id || ""}
                onChange={(event) => {
                  setSelectedOltId(event.target.value);
                  setLogs([]);
                }}
              >
                {!olts.data.length && <option value="">Sin OLTs registradas</option>}
                {olts.data.map((olt) => (
                  <option key={olt.id} value={olt.id}>
                    {olt.olt_code} - {olt.display_name || olt.name} - {olt.environment}
                  </option>
                ))}
              </select>
              <div className="flex flex-wrap gap-2">
                <Button type="button" variant="secondary" onClick={loadSelectedOltForEdit} disabled={!selectedOlt || loading !== null}>
                  <Edit3 className="h-4 w-4" /> Editar seleccionada
                </Button>
                <Button type="button" variant="secondary" onClick={() => refreshLogs()} disabled={!oltId || loading !== null}>
                  Actualizar logs
                </Button>
              </div>
            </div>
            <div className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-950">
              Solo se permiten comandos show de lectura. No se ejecutan configure terminal, write, reboot, reload, reset,
              delete, erase ni aprovisionamiento. Guardar una OLT no ejecuta pruebas automaticamente.
            </div>
          </div>
        </Panel>

        <Panel className="p-4">
          <form className="space-y-4" onSubmit={saveOlt}>
            <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h2 className="text-sm font-semibold text-slate-950">Registrar / editar OLT de prueba</h2>
                <p className="text-sm text-muted">
                  {editingOltId ? "Dejar vacío para mantener la contraseña actual." : "La contraseña es obligatoria al crear."}
                </p>
              </div>
              <div className="text-sm">
                {editingOltId && (
                <span className="mr-3 text-slate-700">
                  Contraseña guardada: {(savedOlt ?? selectedOlt)?.has_password ? "Sí" : "No"}
                </span>
                )}
                {savedOlt && <span className="text-emerald-700">OLT guardada: {savedOlt.name}</span>}
              </div>
            </div>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              <FormField label="Nombre">
                <Input value={form.name} onChange={(event) => updateForm("name", event.target.value)} placeholder="FTTH-PCM-ZTE1" />
              </FormField>
              <FormField label="Codigo OLT *">
                <Input value={form.olt_code} onChange={(event) => updateForm("olt_code", event.target.value)} placeholder="OLT-PCM-ZTE-01" required />
              </FormField>
              <FormField label="Display name">
                <Input value={form.display_name} onChange={(event) => updateForm("display_name", event.target.value)} placeholder="PCM ZTE 01" />
              </FormField>
              <FormField label="IP / Host">
                <Input value={form.ip_address} onChange={(event) => updateForm("ip_address", event.target.value)} required />
              </FormField>
              <FormField label="Puerto Telnet">
                <Input value={form.telnet_port} onChange={(event) => updateForm("telnet_port", event.target.value)} type="number" min={1} required />
              </FormField>
              <FormField label="Usuario">
                <Input value={form.username} onChange={(event) => updateForm("username", event.target.value)} required />
              </FormField>
              <FormField label={editingOltId ? "Contraseña" : "Contraseña *"}>
                <Input
                  value={form.password}
                  onChange={(event) => updateForm("password", event.target.value)}
                  type="password"
                  autoComplete="new-password"
                  required={!editingOltId}
                />
              </FormField>
              <FormField label="Fabricante">
                <Input value={form.vendor} onChange={(event) => updateForm("vendor", event.target.value)} />
              </FormField>
              <FormField label="Modelo">
                <Input value={form.model} onChange={(event) => updateForm("model", event.target.value)} />
              </FormField>
              <FormField label="Firmware">
                <Input value={form.firmware} onChange={(event) => updateForm("firmware", event.target.value)} />
              </FormField>
              <FormField label="Tipo de conexion">
                <select
                  className="h-9 w-full rounded-md border border-slate-200 bg-white px-3 text-sm"
                  value={form.connection_type}
                  onChange={(event) => updateForm("connection_type", event.target.value)}
                >
                  <option value="telnet">telnet</option>
                </select>
              </FormField>
              <FormField label="Entorno">
                <select
                  className="h-9 w-full rounded-md border border-slate-200 bg-white px-3 text-sm"
                  value={form.environment}
                  onChange={(event) => updateForm("environment", event.target.value)}
                >
                  <option value="production">Produccion</option>
                  <option value="lab">Laboratorio</option>
                </select>
              </FormField>
            </div>
            <div>{selectedOlt && <EnvironmentBadge environment={selectedOlt.environment} />}</div>
            <div className="flex flex-wrap gap-2">
              <Button type="submit" disabled={loading !== null || requiredCreateFieldsMissing}>
                Guardar OLT
              </Button>
              <Button type="button" variant="secondary" onClick={clearForm} disabled={loading !== null}>
                Limpiar formulario
              </Button>
              <Button type="button" variant="secondary" onClick={useSavedOltForTest} disabled={loading !== null}>
                Usar esta OLT para prueba
              </Button>
            </div>
          </form>
        </Panel>

        <div className="grid gap-5 xl:grid-cols-3">
          <Panel className="p-4">
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-950">
              <ShieldCheck className="h-4 w-4" /> Read-only check
            </div>
            <Button type="button" onClick={runReadOnlyCheck} disabled={!oltId || loading !== null}>
              Ejecutar read-only-check
            </Button>
          </Panel>

          <Panel className="p-4">
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-950">
              <Activity className="h-4 w-4" /> Sync ONUs Read-Only
            </div>
            <div className="mb-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
              Este proceso solo ejecuta show gpon onu state y no modifica la OLT.
            </div>
            <Button type="button" onClick={runSyncOnus} disabled={!oltId || loading !== null}>
              Sync ONUs Read-Only
            </Button>
          </Panel>

          <Panel className="p-4">
            <form className="space-y-3" onSubmit={runSyncPower}>
              <div className="flex items-center gap-2 text-sm font-semibold text-slate-950">
                <Bolt className="h-4 w-4" /> Sync Power limitado
              </div>
              <label className="block text-sm">
                <span className="mb-1 block text-slate-700">Limit</span>
                <Input value={limit} onChange={(event) => setLimit(event.target.value)} type="number" min={1} />
              </label>
              <label className="block text-sm">
                <span className="mb-1 block text-slate-700">Interfaces ONU manuales</span>
                <textarea
                  className="min-h-24 w-full rounded-md border border-slate-200 bg-white p-3 font-mono text-xs outline-none focus:border-primary focus:ring-2 focus:ring-primary/15"
                  value={interfacesText}
                  onChange={(event) => setInterfacesText(event.target.value)}
                  placeholder={"gpon-onu_1/2/3:2\ngpon-onu_1/2/3:4"}
                />
              </label>
              <Button type="submit" disabled={!oltId || loading !== null}>
                Ejecutar sync power
              </Button>
            </form>
          </Panel>
        </div>

        {checkResult && <CheckResultPanel result={checkResult} />}

        {(syncResult || powerResult) && (
          <Panel className="p-4">
            <h2 className="mb-3 text-sm font-semibold text-slate-950">Resultado de sincronizacion</h2>
            <pre className="max-h-72 overflow-auto rounded-md bg-slate-950 p-3 text-xs text-white">
              {JSON.stringify(syncResult ?? powerResult, null, 2)}
            </pre>
          </Panel>
        )}

        <Panel className="overflow-hidden">
          <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
            <h2 className="text-sm font-semibold text-slate-950">Comandos ejecutados</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px] text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase text-muted">
                <tr>
                  <th className="px-4 py-3">Fecha</th>
                  <th className="px-4 py-3">Comando</th>
                  <th className="px-4 py-3">Exito</th>
                  <th className="px-4 py-3">Read-only</th>
                  <th className="px-4 py-3">Duracion</th>
                  <th className="px-4 py-3">Error</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {logs.map((log) => (
                  <tr key={log.id}>
                    <td className="px-4 py-3 text-slate-700">{formatDate(log.created_at)}</td>
                    <td className="px-4 py-3 font-mono text-xs text-slate-800">{log.command}</td>
                    <td className="px-4 py-3 text-slate-700">{log.success ? "si" : "no"}</td>
                    <td className="px-4 py-3 text-slate-700">{log.read_only ? "si" : "no"}</td>
                    <td className="px-4 py-3 text-slate-700">{log.duration_ms ?? ""} ms</td>
                    <td className="px-4 py-3 text-slate-700">{log.error_message ?? ""}</td>
                  </tr>
                ))}
                {!logs.length && (
                  <tr>
                    <td className="px-4 py-6 text-sm text-muted" colSpan={6}>
                      Sin comandos registrados para esta OLT.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Panel>
      </div>
    </AppShell>
  );
}

function FormField({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block text-slate-700">{label}</span>
      {children}
    </label>
  );
}

function CheckResultPanel({ result }: { result: ReadOnlyCheckResult }) {
  return (
    <Panel className="p-4">
      <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-sm font-semibold text-slate-950">Resultado general</h2>
          <p className="text-sm text-muted">Duracion total: {result.duration_ms} ms</p>
        </div>
        <span className={`rounded-md px-3 py-2 text-sm ${result.connection_success ? "bg-emerald-100 text-emerald-800" : "bg-red-100 text-red-800"}`}>
          {result.connection_success ? "Conexion exitosa" : "Conexion fallida"}
        </span>
      </div>
      <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
        <Metric label="Total ONUs" value={result.onu_counts.total} />
        <Metric label="Working" value={result.onu_counts.working} />
        <Metric label="Offline" value={result.onu_counts.offline} />
        <Metric label="LOS" value={result.onu_counts.los} />
        <Metric label="DyingGasp" value={result.onu_counts.dying_gasp} />
        <Metric label="Prompt" value={result.prompt_detected ?? ""} />
      </div>
      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <div>
          <div className="mb-2 text-xs font-medium uppercase text-muted">Firmware</div>
          <div className="rounded-md border border-slate-200 bg-slate-50 p-3 text-sm text-slate-800">
            {result.firmware_detected ?? "No detectado"}
          </div>
        </div>
        <div>
          <div className="mb-2 text-xs font-medium uppercase text-muted">Errores</div>
          <div className="whitespace-pre-line rounded-md border border-slate-200 bg-slate-50 p-3 text-sm text-slate-800">
            {result.errors.length ? result.errors.map((error) => `${error.command ?? "comando"}: ${error.error}`).join("\n") : "Sin errores"}
          </div>
        </div>
      </div>
      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[520px] text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase text-muted">
            <tr>
              <th className="px-3 py-2">Slot</th>
              <th className="px-3 py-2">Tipo</th>
              <th className="px-3 py-2">Estado</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {result.cards.map((card, index) => (
              <tr key={index}>
                <td className="px-3 py-2 text-slate-700">{String(card.slot ?? "")}</td>
                <td className="px-3 py-2 text-slate-700">{String(card.card_type ?? "")}</td>
                <td className="px-3 py-2 text-slate-700">{String(card.status ?? "")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
      <div className="text-xs text-muted">{label}</div>
      <div className="mt-1 text-lg font-semibold text-slate-950">{value}</div>
    </div>
  );
}

function formatDate(value: string) {
  return new Date(value).toLocaleString();
}
