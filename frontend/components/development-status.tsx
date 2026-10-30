import Link from "next/link";

import { WorkspaceShell } from "@/components/workspace-shell";

type DevelopmentStatusProps = {
  title: string;
  status: "Belum dikonfigurasi" | "Dalam pengembangan" | "Belum tersedia";
  description: string;
};

export function DevelopmentStatus({ title, status, description }: DevelopmentStatusProps) {
  return (
    <WorkspaceShell>
      <main className="mx-auto max-w-4xl p-5 md:p-10">
        <p className="text-sm font-semibold tracking-wide text-blue-700">WORKSPACE</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight">{title}</h1>
        <section className="mt-7 rounded-lg border border-[var(--border)] bg-white p-6">
          <span className="inline-flex rounded-full bg-amber-50 px-3 py-1 text-sm font-medium text-amber-800">{status}</span>
          <p className="mt-4 max-w-2xl leading-7 text-[var(--muted)]">{description}</p>
          <Link href="/settings" className="mt-5 inline-flex rounded-md border border-[var(--border)] px-4 py-2 text-sm font-medium hover:bg-slate-50">
            Buka pengaturan operasional
          </Link>
        </section>
      </main>
    </WorkspaceShell>
  );
}
