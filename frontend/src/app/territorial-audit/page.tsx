"use client";

import { useMemo, useState } from "react";
import { AlertTriangle, BarChart3, CheckCircle2, ExternalLink, Info, ShieldAlert, ShieldCheck, XCircle, ChevronDown, ChevronUp } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { Panel } from "@/components/ui/panel";
import { api } from "@/services/api";
import { useApiData } from "@/hooks/useApiData";
import type { TerritorialAuditCenter, TerritorialAuditOltSummary } from "@/types";

const emptyAudit: TerritorialAuditCenter = {
  generated_at: "",
  olt_summaries: [],
  zone_state_summary: { new_count: 0, exists_count: 0, review_count: 0, blocked_count: 0, merge_count: 0 },
  nap_state_summary: { new_count: 0, exists_count: 0, review_count: 0, blocked_count: 0, merge_count: 0 },
  confidence_summary: { alta_count: 0, media_count: 0, baja_count: 0, bloqueado_count: 0 },
  critical_issues: [],
  recommendations: [],
};

export default function TerritorialAuditPage() {
  const { data, error, loading } = useApiData<TerritorialAuditCenter>(api.territorialAuditCenter, emptyAudit, []);

  const [oltFilter, setOltFilter] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [severityFilter, setSeverityFilter] = useState<string>("");
  const [issueTypeFilter, setIssueTypeFilter] = useState<string>("");
  const [search, setSearch] = useState<string>("");
  const [expandedOltId, setExpandedOltId] = useState<number | null>(null);

  const totalOlts = data.olt_summaries.length;
  const countsByStatus = groupByStatus(data.olt_summaries);
  const totalIssues = data.critical_issues.length;
  const totalRecommendations = data.recommendations.length;

  const oltOptions = useMemo(
    () =>
      Array.from(
        new Map(data.olt_summaries.map((s) => [s.olt_code, { code: s.olt_code, name: s.olt_name }])).values(),
      ).sort((a, b) => a.code.localeCompare(b.code)),
    [data.olt_summaries],
  );

  const issueTypeOptions = useMemo(
    () => {
      const set = new Set<string>();
      for (const issue of data.critical_issues) {
        if (issue.issue_type) {
          set.add(issue.issue_type);
        }
      }
      return Array.from(set).sort((a, b) => a.localeCompare(b));
    },
    [data.critical_issues],
  );

  const filteredOltSummaries = useMemo(
    () =>
      data.olt_summaries.filter((s) => {
        if (oltFilter && s.olt_code !== oltFilter) return false;
        if (statusFilter && (s.status || "").toUpperCase() !== statusFilter) return false;
        return true;
      }),
    [data.olt_summaries, oltFilter, statusFilter],
  );

  const filteredIssues = useMemo(
    () => {
      const q = search.trim().toLowerCase();
      return data.critical_issues.filter((issue) => {
        if (oltFilter && (issue.olt_code || "") !== oltFilter) return false;
        if (severityFilter && (issue.severity || "").toUpperCase() !== severityFilter) return false;
        if (issueTypeFilter && issue.issue_type !== issueTypeFilter) return false;

        if (!q) return true;

        const haystack = [
          issue.olt_code,
          issue.entity_name,
          issue.issue_type,
          issue.message,
          issue.recommendation,
        ]
          .filter(Boolean)
          .join(" \n ")
          .toLowerCase();

        return haystack.includes(q);
      });
    },
    [data.critical_issues, oltFilter, severityFilter, issueTypeFilter, search],
  );

  const filteredRecommendations = useMemo(
    () => {
      const q = search.trim().toLowerCase();
      if (!q) return data.recommendations;
      return data.recommendations.filter((rec) => rec.toLowerCase().includes(q));
    },
    [data.recommendations, search],
  );

  const filteredIssuesCount = filteredIssues.length;

  return (
    <AppShell>
      <div className="space-y-5">
        <Header />

        {loading && (
          <div className="rounded-md border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
            Cargando auditoría territorial...
          </div>
        )}

        {error && !loading && (
          <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            No se pudo cargar la auditoría territorial: {error}
          </div>
        )}

        {!loading && !error && totalOlts === 0 && (
          <div className="rounded-md border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
            No hay datos de auditoría territorial aún. Asegúrate de haber ejecutado las importaciones iniciales y los previews
            territoriales.
          </div>
        )}

        {/* Resumen ejecutivo */}
        {!loading && !error && totalOlts > 0 && (
          <>
            {/* Filtros superiores */}
            <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-panel">
              <div className="mb-3 flex items-center justify-between gap-2">
                <h2 className="text-sm font-semibold text-slate-950">Filtros de auditoría</h2>
                <button
                  type="button"
                  onClick={() => {
                    setOltFilter("");
                    setStatusFilter("");
                    setSeverityFilter("");
                    setIssueTypeFilter("");
                    setSearch("");
                    setExpandedOltId(null);
                  }}
                  className="inline-flex items-center gap-1 rounded-md border border-slate-300 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50"
                >
                  Limpiar filtros
                </button>
              </div>
              <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4 xl:grid-cols-5">
                <div className="space-y-1">
                  <label className="text-xs font-medium text-slate-700">OLT</label>
                  <select
                    className="h-8 w-full rounded-md border border-slate-300 bg-white px-2 text-xs text-slate-900"
                    value={oltFilter}
                    onChange={(e) => setOltFilter(e.target.value)}
                  >
                    <option value="">Todas las OLTs</option>
                    {oltOptions.map((opt) => (
                      <option key={opt.code} value={opt.code}>
                        {opt.code} — {opt.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-medium text-slate-700">Status OLT</label>
                  <select
                    className="h-8 w-full rounded-md border border-slate-300 bg-white px-2 text-xs text-slate-900"
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value)}
                  >
                    <option value="">Todos</option>
                    <option value="HEALTHY">HEALTHY</option>
                    <option value="NEEDS_REVIEW">NEEDS_REVIEW</option>
                    <option value="DEGRADED">DEGRADED</option>
                    <option value="CRITICAL">CRITICAL</option>
                  </select>
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-medium text-slate-700">Severidad de issue</label>
                  <select
                    className="h-8 w-full rounded-md border border-slate-300 bg-white px-2 text-xs text-slate-900"
                    value={severityFilter}
                    onChange={(e) => setSeverityFilter(e.target.value)}
                  >
                    <option value="">Todas</option>
                    <option value="LOW">LOW</option>
                    <option value="MEDIUM">MEDIUM</option>
                    <option value="HIGH">HIGH</option>
                    <option value="CRITICAL">CRITICAL</option>
                  </select>
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-medium text-slate-700">Tipo de issue</label>
                  <select
                    className="h-8 w-full rounded-md border border-slate-300 bg-white px-2 text-xs text-slate-900"
                    value={issueTypeFilter}
                    onChange={(e) => setIssueTypeFilter(e.target.value)}
                  >
                    <option value="">Todos</option>
                    {issueTypeOptions.map((type) => (
                      <option key={type} value={type}>
                        {type}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="space-y-1 md:col-span-2 lg:col-span-2 xl:col-span-1">
                  <label className="text-xs font-medium text-slate-700">Búsqueda libre</label>
                  <input
                    type="text"
                    placeholder="Buscar por OLT, entidad, tipo, mensaje o recomendación"
                    className="h-8 w-full rounded-md border border-slate-300 bg-white px-2 text-xs text-slate-900 placeholder:text-slate-400"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                </div>
              </div>
            </section>

          <section className="grid gap-3 md:grid-cols-3 xl:grid-cols-7">
            <SummaryCard label="OLT auditadas" value={totalOlts} icon={BarChart3} tone="text-slate-900" />
            <SummaryCard label="OLT CRITICAL" value={countsByStatus.CRITICAL} icon={ShieldAlert} tone="text-danger" />
            <SummaryCard label="OLT DEGRADED" value={countsByStatus.DEGRADED} icon={AlertTriangle} tone="text-warning" />
            <SummaryCard label="OLT NEEDS_REVIEW" value={countsByStatus.NEEDS_REVIEW} icon={Info} tone="text-primary" />
            <SummaryCard label="OLT HEALTHY" value={countsByStatus.HEALTHY} icon={ShieldCheck} tone="text-emerald-600" />
            <SummaryCard label="Issues críticos" value={totalIssues} icon={XCircle} tone="text-danger" />
            <SummaryCard label="Recomendaciones" value={totalRecommendations} icon={CheckCircle2} tone="text-primary" />
          </section>
          </>
        )}

        {/* Tabla por OLT */}
        {!loading && !error && totalOlts > 0 && (
          <Panel>
            <div className="border-b border-slate-200 px-4 py-3">
              <h2 className="text-sm font-semibold text-slate-950">Detalle por OLT</h2>
            </div>
            {filteredOltSummaries.length === 0 ? (
              <div className="px-4 py-3 text-sm text-muted">
                No hay OLTs que coincidan con los filtros seleccionados.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[960px] text-left text-sm">
                  <thead className="bg-slate-50 text-xs uppercase text-muted">
                    <tr>
                      <th className="px-4 py-3 font-medium">OLT</th>
                      <th className="px-4 py-3 font-medium">ONUs</th>
                      <th className="px-4 py-3 font-medium">Health Score</th>
                      <th className="px-4 py-3 font-medium">Status</th>
                      <th className="px-4 py-3 font-medium">Zones existentes</th>
                      <th className="px-4 py-3 font-medium">Zones faltantes</th>
                      <th className="px-4 py-3 font-medium">NAPs existentes</th>
                      <th className="px-4 py-3 font-medium">NAPs propuestos</th>
                      <th className="px-4 py-3 font-medium">Zone cross</th>
                      <th className="px-4 py-3 font-medium">NAP cross</th>
                      <th className="px-4 py-3 font-medium">Review</th>
                      <th className="px-4 py-3 font-medium">Blocked</th>
                      <th className="px-4 py-3 font-medium text-right">Detalle</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {filteredOltSummaries.map((s) => {
                      const issuesForOlt = filteredIssues.filter(
                        (issue) => issue.olt_id === s.olt_id || (issue.olt_code && issue.olt_code === s.olt_code),
                      );
                      const criticalCount = issuesForOlt.filter(
                        (issue) => (issue.severity || "").toUpperCase() === "CRITICAL",
                      ).length;
                      const highCount = issuesForOlt.filter(
                        (issue) => (issue.severity || "").toUpperCase() === "HIGH",
                      ).length;

                      const relatedRecommendations = filteredRecommendations.filter((rec) => {
                        const qCode = s.olt_code.toLowerCase();
                        const qName = s.olt_name.toLowerCase();
                        const text = rec.toLowerCase();
                        return text.includes(qCode) || text.includes(qName);
                      });

                      const isExpanded = expandedOltId === s.olt_id;

                      return (
                        <>
                          <tr key={s.olt_id} className="hover:bg-slate-50">
                            <td className="px-4 py-3 text-slate-900">
                              <div className="font-medium">{s.olt_code}</div>
                              <div className="text-xs text-muted">{s.olt_name}</div>
                            </td>
                            <td className="px-4 py-3">{s.total_onus}</td>
                            <td className="px-4 py-3">
                              <span className="font-semibold">{s.territorial_health_score}</span>
                            </td>
                            <td className="px-4 py-3">
                              <StatusBadge status={s.status} />
                            </td>
                            <td className="px-4 py-3">{s.zones_existing_count}</td>
                            <td className="px-4 py-3">{s.zones_missing_count}</td>
                            <td className="px-4 py-3">{s.naps_existing_count}</td>
                            <td className="px-4 py-3">{s.naps_proposed_count}</td>
                            <td className="px-4 py-3">{s.onus_with_cross_olt_zone}</td>
                            <td className="px-4 py-3">{s.onus_with_cross_olt_nap}</td>
                            <td className="px-4 py-3">{s.naps_review_count}</td>
                            <td className="px-4 py-3">{s.naps_blocked_count}</td>
                            <td className="px-4 py-3 text-right">
                              <button
                                type="button"
                                onClick={() => setExpandedOltId(isExpanded ? null : s.olt_id)}
                                className="inline-flex items-center gap-1 rounded-md border border-slate-300 bg-white px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50"
                              >
                                {isExpanded ? "Ocultar" : "Ver detalle"}
                                {isExpanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                              </button>
                            </td>
                          </tr>
                          {isExpanded && (
                            <tr className="bg-slate-50/80">
                              <td colSpan={13} className="px-4 py-3">
                                <div className="grid gap-3 md:grid-cols-3">
                                  <div className="rounded-md border border-slate-200 bg-white p-3 text-xs text-slate-800">
                                    <div className="mb-2 text-[11px] font-semibold uppercase text-slate-500">
                                      Conteos principales
                                    </div>
                                    <dl className="space-y-1.5">
                                      <div className="flex items-center justify-between">
                                        <dt className="text-[11px] text-muted">Issues (filtrados)</dt>
                                        <dd className="text-sm font-semibold text-slate-950">{issuesForOlt.length}</dd>
                                      </div>
                                      <div className="flex items-center justify-between">
                                        <dt className="text-[11px] text-muted">CRITICAL</dt>
                                        <dd className="text-sm font-semibold text-red-700">{criticalCount}</dd>
                                      </div>
                                      <div className="flex items-center justify-between">
                                        <dt className="text-[11px] text-muted">HIGH</dt>
                                        <dd className="text-sm font-semibold text-orange-700">{highCount}</dd>
                                      </div>
                                      <div className="flex items-center justify-between">
                                        <dt className="text-[11px] text-muted">ONUs con Zone/NAP cruzados</dt>
                                        <dd className="text-sm font-semibold text-slate-950">
                                          {s.onus_with_cross_olt_zone + s.onus_with_cross_olt_nap}
                                        </dd>
                                      </div>
                                    </dl>
                                  </div>
                                  <div className="rounded-md border border-slate-200 bg-white p-3 text-xs text-slate-800 md:col-span-2">
                                    <div className="mb-2 text-[11px] font-semibold uppercase text-slate-500">
                                      Issues de esta OLT (según filtros)
                                    </div>
                                    {issuesForOlt.length === 0 ? (
                                      <div className="text-xs text-muted">
                                        No hay issues para esta OLT con los filtros actuales.
                                      </div>
                                    ) : (
                                      <ul className="space-y-1.5">
                                        {issuesForOlt.slice(0, 5).map((issue, idx) => (
                                          <li key={`${issue.issue_type}-${issue.olt_code}-${idx}`} className="border-b border-slate-100 pb-1 last:border-0">
                                            <div className="mb-0.5 flex items-center justify-between">
                                              <span className="text-[11px] font-semibold text-slate-900">{issue.issue_type}</span>
                                              <SeverityBadge severity={issue.severity} />
                                            </div>
                                            <div className="text-[11px] text-slate-700">{issue.message}</div>
                                            {issue.recommendation && (
                                              <div className="mt-0.5 text-[11px] text-slate-500">
                                                Recomendación: {issue.recommendation}
                                              </div>
                                            )}
                                          </li>
                                        ))}
                                        {issuesForOlt.length > 5 && (
                                          <li className="pt-1 text-[11px] text-muted">
                                            (+{issuesForOlt.length - 5} issues adicionales filtrados)
                                          </li>
                                        )}
                                      </ul>
                                    )}
                                    <div className="mt-3 border-t border-slate-100 pt-2">
                                      <div className="mb-1 text-[11px] font-semibold uppercase text-slate-500">
                                        Recomendaciones relacionadas
                                      </div>
                                      {filteredRecommendations.length === 0 ? (
                                        <div className="text-[11px] text-muted">
                                          No hay recomendaciones que coincidan con la búsqueda actual.
                                        </div>
                                      ) : relatedRecommendations.length === 0 ? (
                                        <div className="text-[11px] text-muted">
                                          No se han detectado recomendaciones específicas para esta OLT. Se aplican las
                                          recomendaciones generales.
                                        </div>
                                      ) : (
                                        <ul className="space-y-1">
                                          {relatedRecommendations.slice(0, 3).map((rec, idx) => (
                                            <li key={idx} className="text-[11px] text-slate-700">
                                              • {rec}
                                            </li>
                                          ))}
                                          {relatedRecommendations.length > 3 && (
                                            <li className="text-[11px] text-muted">
                                              (+{relatedRecommendations.length - 3} recomendaciones adicionales)
                                            </li>
                                          )}
                                        </ul>
                                      )}
                                    </div>
                                  </div>
                                </div>
                              </td>
                            </tr>
                          )}
                        </>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
        )}

        {/* Resumen de estados y confianza */}
        {!loading && !error && (
          <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            <Panel>
              <div className="border-b border-slate-200 px-4 py-3">
                <h2 className="text-sm font-semibold text-slate-950">Estados Zones</h2>
              </div>
              <StateList summary={data.zone_state_summary} />
            </Panel>
            <Panel>
              <div className="border-b border-slate-200 px-4 py-3">
                <h2 className="text-sm font-semibold text-slate-950">Estados NAP/ODN/ODB</h2>
              </div>
              <StateList summary={data.nap_state_summary} />
            </Panel>
            <Panel>
              <div className="border-b border-slate-200 px-4 py-3">
                <h2 className="text-sm font-semibold text-slate-950">Confianza agregada</h2>
              </div>
              <div className="space-y-2 px-4 py-3 text-sm">
                <ConfidenceRow label="ALTA" value={data.confidence_summary.alta_count} tone="text-emerald-700" />
                <ConfidenceRow label="MEDIA" value={data.confidence_summary.media_count} tone="text-primary" />
                <ConfidenceRow label="BAJA" value={data.confidence_summary.baja_count} tone="text-amber-600" />
                <ConfidenceRow label="BLOQUEADO" value={data.confidence_summary.bloqueado_count} tone="text-danger" />
              </div>
            </Panel>
          </section>
        )}

        {/* Issues críticos */}
        {!loading && !error && (
          <Panel>
            <div className="border-b border-slate-200 px-4 py-3">
              <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                <h2 className="text-sm font-semibold text-slate-950">Issues críticos</h2>
                {totalIssues > 0 && (
                  <p className="text-xs text-muted">
                    Mostrando {filteredIssuesCount} de {totalIssues} issues
                  </p>
                )}
              </div>
            </div>
            {data.critical_issues.length === 0 ? (
              <div className="px-4 py-3 text-sm text-muted">No se han detectado issues territoriales en esta auditoría.</div>
            ) : filteredIssuesCount === 0 ? (
              <div className="px-4 py-3 text-sm text-muted">
                No hay issues críticos que coincidan con los filtros actuales.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[960px] text-left text-sm">
                  <thead className="bg-slate-50 text-xs uppercase text-muted">
                    <tr>
                      <th className="px-4 py-3 font-medium">Severidad</th>
                      <th className="px-4 py-3 font-medium">Tipo</th>
                      <th className="px-4 py-3 font-medium">OLT</th>
                      <th className="px-4 py-3 font-medium">Entidad</th>
                      <th className="px-4 py-3 font-medium">ONUs afectadas</th>
                      <th className="px-4 py-3 font-medium">Mensaje</th>
                      <th className="px-4 py-3 font-medium">Recomendación</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {filteredIssues.map((issue, index) => (
                      <tr key={`${issue.issue_type}-${issue.olt_code}-${index}`} className="hover:bg-slate-50">
                        <td className="px-4 py-3">
                          <SeverityBadge severity={issue.severity} />
                        </td>
                        <td className="px-4 py-3 text-xs font-mono text-slate-700">{issue.issue_type}</td>
                        <td className="px-4 py-3 text-xs text-slate-700">{issue.olt_code ?? "-"}</td>
                        <td className="px-4 py-3 text-xs text-slate-700">
                          {issue.entity_type}
                          {issue.entity_name ? `: ${issue.entity_name}` : ""}
                        </td>
                        <td className="px-4 py-3">{issue.affected_onu_count ?? "-"}</td>
                        <td className="px-4 py-3 text-xs text-slate-700">{issue.message}</td>
                        <td className="px-4 py-3 text-xs text-slate-700">{issue.recommendation ?? "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
        )}

        {/* Recomendaciones */}
        {!loading && !error && (
          <Panel>
            <div className="border-b border-slate-200 px-4 py-3">
              <h2 className="text-sm font-semibold text-slate-950">Recomendaciones</h2>
            </div>
            {data.recommendations.length === 0 ? (
              <div className="px-4 py-3 text-sm text-muted">No hay recomendaciones adicionales generadas.</div>
            ) : filteredRecommendations.length === 0 ? (
              <div className="px-4 py-3 text-sm text-muted">
                No hay recomendaciones que coincidan con la búsqueda actual.
              </div>
            ) : (
              <ul className="space-y-2 px-4 py-3 text-sm text-slate-800">
                {filteredRecommendations.map((rec, idx) => (
                  <li key={idx} className="flex gap-2">
                    <span className="mt-0.5 h-1.5 w-1.5 rounded-full bg-slate-400" />
                    <span>{rec}</span>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        )}

        {/* Accesos rápidos */}
        <Panel>
          <div className="border-b border-slate-200 px-4 py-3">
            <h2 className="text-sm font-semibold text-slate-950">Accesos rápidos (solo lectura)</h2>
          </div>
          <div className="flex flex-wrap gap-3 px-4 py-3 text-sm">
            <QuickLink
              href="/api/v1/admin/territorial/zones/preview"
              label="API Zones preview"
            />
            <QuickLink
              href="/api/v1/admin/territorial/naps/preview"
              label="API NAPs preview"
            />
            <QuickLink
              href="/api/v1/admin/territorial/audit-center"
              label="API Audit Center"
            />
          </div>
        </Panel>
      </div>
    </AppShell>
  );
}

function Header() {
  return (
    <section className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h1 className="text-xl font-semibold text-slate-950">Auditoría Territorial FTTH</h1>
        <p className="text-sm text-muted">Vista read-only de reconstrucción territorial por OLT.</p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <span className="inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-800">
          <ShieldCheck className="h-3 w-3" /> SOLO LECTURA / SIN APPLY
        </span>
      </div>
    </section>
  );
}

function SummaryCard({
  label,
  value,
  icon: Icon,
  tone,
}: {
  label: string;
  value: number;
  icon: React.ComponentType<{ className?: string }>;
  tone: string;
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-panel">
      <div className="flex items-center justify-between">
        <span className="text-sm text-muted">{label}</span>
        <Icon className={`h-4 w-4 ${tone}`} />
      </div>
      <div className="mt-3 text-2xl font-semibold text-slate-950">{value}</div>
    </div>
  );
}

function StatusBadge({ status }: { status: TerritorialAuditOltSummary["status"] }) {
  const normalized = (status || "").toUpperCase();
  let color = "bg-slate-100 text-slate-800 border-slate-200";
  if (normalized === "HEALTHY") color = "bg-emerald-50 text-emerald-800 border-emerald-200";
  else if (normalized === "NEEDS_REVIEW") color = "bg-amber-50 text-amber-800 border-amber-200";
  else if (normalized === "DEGRADED") color = "bg-orange-50 text-orange-800 border-orange-200";
  else if (normalized === "CRITICAL") color = "bg-red-50 text-red-800 border-red-200";

  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${color}`}>
      {normalized || "UNKNOWN"}
    </span>
  );
}

function StateList({ summary }: { summary: TerritorialAuditCenter["zone_state_summary"] }) {
  return (
    <dl className="grid grid-cols-2 gap-3 px-4 py-3 text-sm">
      <StateRow label="NEW" value={summary.new_count} />
      <StateRow label="EXISTS" value={summary.exists_count} />
      <StateRow label="REVIEW" value={summary.review_count} />
      <StateRow label="BLOCKED" value={summary.blocked_count} />
      <StateRow label="MERGE" value={summary.merge_count} />
    </dl>
  );
}

function StateRow({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="mt-1 text-base font-semibold text-slate-950">{value}</dd>
    </div>
  );
}

function ConfidenceRow({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-xs text-muted">{label}</span>
      <span className={`text-base font-semibold ${tone}`}>{value}</span>
    </div>
  );
}

function SeverityBadge({ severity }: { severity: string }) {
  const s = (severity || "").toUpperCase();
  let color = "bg-slate-100 text-slate-800 border-slate-200";
  if (s === "LOW") color = "bg-sky-50 text-sky-800 border-sky-200";
  else if (s === "MEDIUM") color = "bg-amber-50 text-amber-800 border-amber-200";
  else if (s === "HIGH") color = "bg-orange-50 text-orange-800 border-orange-200";
  else if (s === "CRITICAL") color = "bg-red-50 text-red-800 border-red-200";

  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${color}`}>
      {s || "INFO"}
    </span>
  );
}

function QuickLink({ href, label }: { href: string; label: string }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="inline-flex items-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-800 shadow-sm hover:bg-slate-50"
    >
      <ExternalLink className="h-3 w-3" />
      <span>{label}</span>
    </a>
  );
}

function groupByStatus(olts: TerritorialAuditOltSummary[]) {
  const acc: Record<string, number> = { HEALTHY: 0, NEEDS_REVIEW: 0, DEGRADED: 0, CRITICAL: 0 };
  for (const s of olts) {
    const key = (s.status || "").toUpperCase();
    if (acc[key] === undefined) continue;
    acc[key] += 1;
  }
  return acc as { HEALTHY: number; NEEDS_REVIEW: number; DEGRADED: number; CRITICAL: number };
}
