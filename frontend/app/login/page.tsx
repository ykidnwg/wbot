import { LoginForm } from "@/components/login-form";
import { SparkIcon } from "@/components/icons";

export default function LoginPage() {
  return (
    <main className="grid min-h-screen lg:grid-cols-[1.1fr_0.9fr]">
      <section className="relative hidden flex-col justify-between overflow-hidden bg-[var(--forest)] p-10 text-[#f4f0e7] lg:flex">
        <div className="absolute -right-24 -top-24 h-80 w-80 rounded-full border border-white/10" />
        <div className="absolute -bottom-32 -left-16 h-96 w-96 rounded-full bg-[var(--accent)]/20 blur-3xl" />
        <div className="relative">
          <div className="flex items-center gap-3">
            <span className="grid h-10 w-10 place-items-center rounded-full bg-[var(--accent)] text-sm font-black">W</span>
            <span className="text-sm font-bold tracking-[0.16em]">WBOT</span>
          </div>
          <h1 className="display mt-20 max-w-lg text-5xl font-semibold leading-[1.04]">
            A social content workspace built on evidence.
          </h1>
          <p className="mt-5 max-w-md text-sm leading-6 text-[#b8c8c1]">
            Plan fictional personas, version every caption, schedule approved work, and only call a post published when the platform confirms it.
          </p>
        </div>
        <ul className="relative grid gap-3 text-sm text-[#c8d7d1]">
          {["Owner-scoped data", "Immutable approval history", "Explicit provider and credential states"].map((item) => (
            <li key={item} className="flex items-center gap-2">
              <SparkIcon className="h-4 w-4 text-[var(--accent)]" />
              {item}
            </li>
          ))}
        </ul>
      </section>

      <section className="flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-sm">
          <p className="eyebrow">Private workspace</p>
          <h2 className="display mt-2 text-4xl font-semibold">Sign in</h2>
          <p className="mt-3 text-sm leading-6 text-[var(--muted)]">
            Use the administrator account configured privately in the server environment.
          </p>
          <LoginForm />
        </div>
      </section>
    </main>
  );
}
