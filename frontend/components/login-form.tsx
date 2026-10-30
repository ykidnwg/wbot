"use client";

import { FormEvent, useState } from "react";

import { login } from "@/lib/api";

export function LoginForm() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await login(email, password);
      window.location.assign("/dashboard");
    } catch (requestError: unknown) {
      setError(
        requestError instanceof Error && requestError.message === "invalid-credentials"
          ? "Email atau kata sandi tidak valid."
          : "Login tidak tersedia. Periksa koneksi backend dan konfigurasi administrator.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form className="mt-8 grid gap-5" onSubmit={handleSubmit} noValidate>
      <label className="grid gap-2 text-sm font-medium" htmlFor="email">
        Email
        <input
          id="email"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
          className="rounded-md border border-[var(--border)] bg-white px-3 py-2.5 text-base"
        />
      </label>
      <label className="grid gap-2 text-sm font-medium" htmlFor="password">
        Kata sandi
        <input
          id="password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
          className="rounded-md border border-[var(--border)] bg-white px-3 py-2.5 text-base"
        />
      </label>
      {error ? <p role="alert" className="text-sm text-[var(--danger)]">{error}</p> : null}
      <button
        type="submit"
        disabled={isSubmitting}
        className="rounded-md bg-[var(--primary)] px-4 py-2.5 font-medium text-white hover:bg-[var(--primary-hover)] disabled:cursor-not-allowed disabled:opacity-60"
      >
        {isSubmitting ? "Memverifikasi…" : "Masuk"}
      </button>
    </form>
  );
}
