"use client";

import Link from "next/link";
import type { ReactNode } from "react";

const navigation = [
  ["/dashboard", "Ringkasan"],
  ["/accounts", "Akun sosial"],
  ["/personas", "Persona"],
  ["/personas/onboarding", "Onboarding persona"],
  ["/content", "Konten"],
  ["/calendar", "Kalender"],
  ["/publishing", "Antrean publikasi"],
  ["/campaign-links", "Campaign & link"],
  ["/analytics", "Analitik"],
  ["/settings", "Pengaturan"],
] as const;

export function WorkspaceShell({ children }: { children: ReactNode }) {
  async function signOut() {
    await fetch("/api/backend/auth/logout", { method: "POST", credentials: "same-origin" });
    window.location.assign("/login");
  }

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[250px_1fr]">
      <aside className="border-b border-[var(--border)] bg-white px-4 py-5 lg:min-h-screen lg:border-b-0 lg:border-r lg:px-5">
        <Link href="/dashboard" className="block text-base font-bold tracking-tight text-blue-800">
          AI SOCIAL AUTOMATION
        </Link>
        <p className="mt-1 text-xs text-[var(--muted)]">Workspace operasional</p>
        <nav aria-label="Navigasi utama" className="mt-6 grid grid-cols-2 gap-1 sm:grid-cols-3 lg:grid-cols-1">
          {navigation.map(([href, label]) => {
            return (
              <Link
                key={href}
                href={href}
                className="rounded-md px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
              >
                {label}
              </Link>
            );
          })}
        </nav>
      </aside>
      <div className="min-w-0">
        <header className="flex items-center justify-between border-b border-[var(--border)] bg-white px-5 py-3 md:px-8">
          <span className="text-sm text-[var(--muted)]">Kontrol terpusat · integrasi eksternal belum dikonfigurasi</span>
          <button onClick={signOut} className="rounded-md px-3 py-2 text-sm font-medium hover:bg-slate-100">
            Keluar
          </button>
        </header>
        {children}
      </div>
    </div>
  );
}
