"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import type { ReactNode } from "react";

import {
  CalendarIcon,
  ChartIcon,
  DocumentIcon,
  HomeIcon,
  ImageIcon,
  LinkIcon,
  MenuIcon,
  PanelIcon,
  SendIcon,
  SettingsIcon,
  UsersIcon,
} from "@/components/icons";

const navigation = [
  {
    title: "Workspace",
    items: [
      ["/dashboard", "Overview", HomeIcon],
      ["/accounts", "Social accounts", UsersIcon],
      ["/personas", "Personas", UsersIcon],
      ["/content", "Content studio", DocumentIcon],
      ["/media", "Media library", ImageIcon],
      ["/calendar", "Calendar", CalendarIcon],
      ["/publishing", "Publishing queue", SendIcon],
    ],
  },
  {
    title: "Growth",
    items: [
      ["/campaign-links", "Campaigns", LinkIcon],
      ["/analytics", "Analytics", ChartIcon],
    ],
  },
  {
    title: "System",
    items: [["/settings", "Settings", SettingsIcon]],
  },
] as const;

function sectionTitle(pathname: string): string {
  for (const group of navigation) {
    for (const [href, label] of group.items) {
      if (pathname === href || pathname.startsWith(`${href}/`)) return label;
    }
  }
  return "Workspace";
}

export function WorkspaceShell({ children }: { children: ReactNode }) {
  const pathname = usePathname() ?? "";
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  async function signOut() {
    await fetch("/api/backend/auth/logout", { method: "POST", credentials: "same-origin" });
    window.location.assign("/login");
  }

  return (
    <div
      className={`min-h-screen lg:grid ${
        collapsed ? "lg:grid-cols-[82px_1fr]" : "lg:grid-cols-[256px_1fr]"
      }`}
    >
      {mobileOpen ? (
        <button
          type="button"
          aria-label="Close navigation"
          onClick={() => setMobileOpen(false)}
          className="fixed inset-0 z-20 bg-[#1b1a16]/40 backdrop-blur-[2px] lg:hidden"
        />
      ) : null}

      <aside
        className={`${
          mobileOpen ? "fixed inset-y-0 left-0 z-30 flex w-72" : "hidden"
        } flex-col bg-[var(--forest)] px-4 py-5 text-[#f4f0e7] lg:sticky lg:top-0 lg:flex lg:h-screen lg:border-r lg:border-[#172e28] lg:px-4`}
      >
        <div className="flex items-center justify-between px-1">
          <Link href="/dashboard" className="flex items-center gap-3">
            <span className="grid h-10 w-10 place-items-center rounded-full bg-[var(--accent)] text-sm font-black tracking-tight text-white">
              W
            </span>
            {!collapsed ? (
              <span>
                <span className="block text-sm font-bold tracking-[0.16em]">WBOT</span>
                <span className="block text-[0.62rem] text-[#b8c8c1]">social operations</span>
              </span>
            ) : null}
          </Link>
          <button
            type="button"
            onClick={() => setCollapsed((value) => !value)}
            className="hidden rounded-full p-2 text-[#a9bdb5] hover:bg-white/10 hover:text-white lg:block"
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            <PanelIcon />
          </button>
        </div>

        <nav aria-label="Main navigation" className="mt-9 flex-1 space-y-7 overflow-y-auto">
          {navigation.map((group) => (
            <div key={group.title}>
              {!collapsed ? (
                <p className="mb-2 px-3 text-[0.6rem] font-bold uppercase tracking-[0.18em] text-[#8fa79e]">
                  {group.title}
                </p>
              ) : null}
              <div className="space-y-1">
                {group.items.map(([href, label, Icon]) => {
                  const active = pathname === href || pathname.startsWith(`${href}/`);
                  return (
                    <Link
                      key={href}
                      href={href}
                      title={collapsed ? label : undefined}
                      aria-current={active ? "page" : undefined}
                      onClick={() => setMobileOpen(false)}
                      className={`flex items-center gap-3 rounded-[var(--radius-sm)] px-3 py-2.5 text-[0.82rem] transition-colors ${
                        active
                          ? "bg-[#f4f0e7] font-semibold text-[var(--forest)]"
                          : "text-[#c2d2cb] hover:bg-white/8 hover:text-white"
                      } ${collapsed ? "justify-center" : ""}`}
                    >
                      <Icon className="h-4 w-4 shrink-0" />
                      {!collapsed ? <span className="truncate">{label}</span> : null}
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>

        {!collapsed ? (
          <div className="mt-6 rounded-[var(--radius-md)] border border-white/10 bg-white/5 p-3">
            <p className="text-[0.66rem] font-bold uppercase tracking-[0.14em] text-[#8fa79e]">Workspace</p>
            <p className="mt-1 text-sm font-medium">Owner session</p>
            <p className="mt-0.5 text-[0.68rem] text-[#9eb3aa]">Private, owner-scoped data</p>
          </div>
        ) : null}
      </aside>

      <div className="min-w-0">
        <header className="sticky top-0 z-10 flex items-center justify-between border-b border-[var(--line)] bg-[var(--paper)]/90 px-5 py-3 backdrop-blur md:px-10">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setMobileOpen(true)}
              className="rounded-full p-2 text-[var(--ink-soft)] hover:bg-[var(--paper-deep)] lg:hidden"
              aria-label="Open navigation"
            >
              <MenuIcon />
            </button>
            <div>
              <p className="text-[0.6rem] font-bold uppercase tracking-[0.16em] text-[var(--muted)]">Workspace</p>
              <p className="text-sm font-semibold">{sectionTitle(pathname)}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Link href="/content" className="btn btn-secondary hidden sm:inline-flex">
              New content
            </Link>
            <button onClick={() => void signOut()} className="btn btn-ghost">
              Sign out
            </button>
          </div>
        </header>
        {children}
      </div>
    </div>
  );
}
