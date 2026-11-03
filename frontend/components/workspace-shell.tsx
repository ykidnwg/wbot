"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import type { ReactNode } from "react";

const navigation = [
  { title: "Workspace", items: [
    ["/dashboard", "Overview"],
    ["/accounts", "Social accounts"],
    ["/personas", "Personas"],
    ["/content", "Content"],
    ["/media", "Media library"],
    ["/calendar", "Calendar"],
    ["/publishing", "Publishing queue"],
  ] },
  { title: "Management", items: [
    ["/campaign-links", "Campaigns"],
    ["/analytics", "Analytics"],
  ] },
  { title: "System", items: [
    ["/settings", "Settings"],
  ] },
] as const;

export function WorkspaceShell({ children }: { children: ReactNode }) {
  const pathname = usePathname() ?? "";
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  async function signOut() {
    await fetch("/api/backend/auth/logout", { method: "POST", credentials: "same-origin" });
    window.location.assign("/login");
  }

  return (
    <div className={`min-h-screen lg:grid ${collapsed ? "lg:grid-cols-[76px_1fr]" : "lg:grid-cols-[248px_1fr]"}`}>
      <aside className={`${mobileOpen ? "fixed inset-0 z-30 block w-72" : "hidden"} border-b border-[var(--border)] bg-white px-4 py-5 lg:relative lg:block lg:min-h-screen lg:border-b-0 lg:border-r lg:px-5`}>
        <div className="flex items-center justify-between">
          <Link href="/dashboard" className="block text-sm font-bold tracking-[0.16em] text-[var(--primary)]">
            {collapsed ? "WB" : "WBOT"}
          </Link>
          <button type="button" onClick={() => setCollapsed((value) => !value)} className="hidden rounded-md p-2 text-[var(--muted)] hover:bg-slate-100 lg:block" aria-label="Toggle sidebar">
            {collapsed ? "»" : "«"}
          </button>
        </div>
        {!collapsed && <p className="mt-1 text-xs text-[var(--muted)]">Social operations workspace</p>}
        <nav aria-label="Main navigation" className="mt-8 space-y-6">
          {navigation.map((group) => (
            <div key={group.title}>
              {!collapsed && <p className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">{group.title}</p>}
              <div className="space-y-1">
                {group.items.map(([href, label]) => {
                  const active = pathname === href || pathname.startsWith(`${href}/`);
                  return (
                    <Link key={href} href={href} title={collapsed ? label : undefined} onClick={() => setMobileOpen(false)} className={`block rounded-md px-3 py-2 text-sm transition-colors ${active ? "bg-blue-50 font-semibold text-blue-800" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"} ${collapsed ? "text-center" : ""}`}>
                      {collapsed ? label.slice(0, 1) : label}
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>
        {!collapsed && <div className="absolute bottom-5 left-5 right-5 hidden rounded-lg border border-[var(--border)] bg-slate-50 p-3 lg:block">
          <p className="text-xs font-semibold">Workspace owner</p>
          <p className="mt-1 truncate text-xs text-[var(--muted)]">Authenticated session</p>
        </div>}
      </aside>
      <div className="min-w-0">
        <header className="flex items-center justify-between border-b border-[var(--border)] bg-white px-5 py-3 md:px-8">
          <div className="flex items-center gap-3">
            <button type="button" onClick={() => setMobileOpen(true)} className="rounded-md p-2 text-[var(--muted)] hover:bg-slate-100 lg:hidden" aria-label="Open navigation">☰</button>
            <span className="text-sm font-medium text-slate-700">{pathname === "/dashboard" ? "Overview" : "Workspace"}</span>
          </div>
          <button onClick={signOut} className="rounded-md px-3 py-2 text-sm font-medium text-[var(--muted)] hover:bg-slate-100">
            Sign out
          </button>
        </header>
        {children}
      </div>
    </div>
  );
}
