"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, Boxes, ClipboardList, FileCheck2, FileInput, History, Network, ShieldCheck } from "lucide-react";
import clsx from "clsx";

const nav = [
  { label: "Dashboard", icon: Activity, href: "/" },
  { label: "Importacion inicial", icon: FileInput, href: "/importacion-inicial" },
  { label: "Prueba OLT Read-Only", icon: ShieldCheck, href: "/prueba-read-only" },
  { label: "OLTs", icon: Network, href: "/olts" },
  { label: "ONUs", icon: Network, href: "/onus" },
  { label: "ONUs Pendientes", icon: ClipboardList, href: "/onus-pendientes" },
  { label: "Tipos ONU", icon: Boxes, href: "/onu-types" },
  { label: "Perfiles", icon: Boxes, href: "/speed-profiles" },
  { label: "Catalogos GPON", icon: Boxes, href: "/profile-catalogs" },
  { label: "VLANs", icon: Boxes, href: "/vlans" },
  { label: "Zonas", icon: Boxes, href: "/zonas" },
  { label: "NAPs", icon: Boxes, href: "/naps" },
  { label: "Plantillas", icon: Boxes, href: "/provisioning-templates" },
  { label: "Aprovisionamiento", icon: FileCheck2, href: "/aprovisionamiento" },
  { label: "Monitoreo", icon: History, href: "/monitoreo" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <main className="min-h-screen">
      <aside className="fixed inset-y-0 left-0 hidden w-64 border-r border-slate-200 bg-white px-4 py-5 lg:block">
        <div className="mb-8">
          <div className="text-lg font-semibold text-slate-950">TOI OLT Manager</div>
          <div className="text-xs text-muted">OSS GPON FTTH</div>
        </div>
        <nav className="space-y-1">
          {nav.map((item) => (
            <Link
              key={item.label}
              href={item.href}
              className={clsx(
                "flex h-10 items-center gap-3 rounded-md px-3 text-sm text-slate-700 hover:bg-slate-100",
                pathname === item.href && "bg-slate-100 font-medium text-slate-950",
              )}
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </Link>
          ))}
        </nav>
      </aside>
      <section className="lg:pl-64">
        <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/95 px-5 py-4 backdrop-blur">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-semibold text-slate-950">Operacion GPON</h1>
              <p className="text-sm text-muted">ZTE C300 V1.2.5P3 via Telnet y SNMP</p>
            </div>
            <div className="rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-700">TOI Internet</div>
          </div>
        </header>
        <div className="p-5">{children}</div>
      </section>
    </main>
  );
}
