import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import DashboardPage from "@/app/dashboard/page";

describe("DashboardPage", () => {
  it("labels unconfigured services instead of inventing values", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            connected_accounts: 0,
            active_personas: 0,
            generated_images: 0,
            pending_approval: 0,
            scheduled_posts: 0,
            published_posts: 0,
            failed_posts: 0,
            estimated_ai_cost: null,
            services: { database: "ok", worker: "not_configured", queue: "not_configured", providers: "not_configured" },
          }),
          { status: 200 },
        ),
      ),
    );

    render(<DashboardPage />);

    expect(await screen.findAllByText("Belum dikonfigurasi")).toHaveLength(3);
    expect(screen.getByText("Estimasi biaya AI")).toBeInTheDocument();
    expect(screen.getByText("Belum tersedia")).toBeInTheDocument();
  });
});
