import { LoginForm } from "@/components/login-form";

export default function LoginPage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-md items-center px-6 py-12">
      <section className="w-full rounded-xl border border-[var(--border)] bg-[var(--surface)] p-8 shadow-sm">
        <p className="mb-3 text-sm font-semibold tracking-wide text-blue-700">AI SOCIAL AUTOMATION</p>
        <h1 className="text-3xl font-semibold tracking-tight">Masuk ke workspace</h1>
        <p className="mt-3 text-sm leading-6 text-[var(--muted)]">
          Gunakan akun administrator yang dikonfigurasi secara privat di environment.
        </p>
        <LoginForm />
      </section>
    </main>
  );
}
