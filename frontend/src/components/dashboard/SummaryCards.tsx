import { CircleOff, ClipboardList, FileCheck2, Radio, SignalLow, ZapOff } from "lucide-react";
import type { DashboardSummary } from "@/types";

const cards = [
  { key: "online", label: "ONUs online", icon: Radio, tone: "text-primary" },
  { key: "offline", label: "ONUs offline", icon: CircleOff, tone: "text-slate-600" },
  { key: "los", label: "LOS", icon: ZapOff, tone: "text-danger" },
  { key: "dying_gasp", label: "DyingGasp", icon: ZapOff, tone: "text-warning" },
  { key: "rx_warning", label: "RX warning", icon: SignalLow, tone: "text-warning" },
  { key: "rx_critical", label: "RX critical", icon: SignalLow, tone: "text-danger" },
  { key: "unauthorized_pending", label: "Pendientes", icon: ClipboardList, tone: "text-primary" },
  { key: "unauthorized_ignored", label: "Ignoradas", icon: ClipboardList, tone: "text-slate-600" },
  { key: "unauthorized_ready_for_provisioning", label: "Listas aprovisionar", icon: ClipboardList, tone: "text-warning" },
  { key: "provisioning_draft", label: "Planes draft", icon: FileCheck2, tone: "text-slate-600" },
  { key: "provisioning_validated", label: "Planes validados", icon: FileCheck2, tone: "text-primary" },
  { key: "provisioning_approved", label: "Planes aprobados", icon: FileCheck2, tone: "text-warning" },
  { key: "provisioning_cancelled", label: "Planes cancelados", icon: FileCheck2, tone: "text-danger" },
] as const;

export function SummaryCards({ summary }: { summary: DashboardSummary }) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4 2xl:grid-cols-7">
      {cards.map((card) => (
        <div key={card.key} className="rounded-lg border border-slate-200 bg-white p-4 shadow-panel">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted">{card.label}</span>
            <card.icon className={`h-4 w-4 ${card.tone}`} />
          </div>
          <div className="mt-3 text-3xl font-semibold text-slate-950">{summary[card.key]}</div>
        </div>
      ))}
    </div>
  );
}
