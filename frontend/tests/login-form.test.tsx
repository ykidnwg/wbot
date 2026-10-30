import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LoginForm } from "@/components/login-form";

describe("LoginForm", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("submits credentials to the proxied backend", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    render(<LoginForm />);
    await user.type(screen.getByLabelText("Email"), "owner@example.com");
    await user.type(screen.getByLabelText("Kata sandi"), "safe-password");
    await user.click(screen.getByRole("button", { name: "Masuk" }));

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/backend/auth/login",
      expect.objectContaining({ method: "POST", credentials: "same-origin" }),
    );
  });

  it("shows an actionable authentication failure", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 401 })));

    render(<LoginForm />);
    await user.type(screen.getByLabelText("Email"), "owner@example.com");
    await user.type(screen.getByLabelText("Kata sandi"), "incorrect");
    await user.click(screen.getByRole("button", { name: "Masuk" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Email atau kata sandi tidak valid");
  });
});
