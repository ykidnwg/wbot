import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", () => ({
  approvePersona: vi.fn(),
  createPersona: vi.fn(),
  getPersonas: vi.fn().mockResolvedValue([]),
  updatePersona: vi.fn(),
}));

import PersonasPage from "@/app/personas/page";
import { createPersona } from "@/lib/api";

describe("PersonasPage", () => {
  beforeEach(() => vi.clearAllMocks());

  it("creates an adult persona draft through the API", async () => {
    const user = userEvent.setup();
    vi.mocked(createPersona).mockResolvedValue({
      id: "persona-1",
      owner_id: "owner-1",
      name: "Nadia",
      age: 28,
      language: "Bahasa Indonesia",
      personality: "Ramah",
      target_audience: "Dewasa",
      clothing_style: "Casual",
      identity_description: "Karakter fiktif dewasa",
      caption_preferences: { style: "santai" },
      image_provider: null,
      image_model: null,
      prompt_version: "persona-v1",
      status: "draft",
      version_no: 0,
      created_at: "2026-10-30T00:00:00Z",
      updated_at: "2026-10-30T00:00:00Z",
    });

    render(<PersonasPage />);
    await user.type(screen.getByLabelText("Nama"), "Nadia");
    await user.clear(screen.getByLabelText("Umur (18+)"));
    await user.type(screen.getByLabelText("Umur (18+)"), "28");
    await user.type(screen.getByLabelText("Deskripsi identitas"), "Karakter fiktif dewasa");
    await user.type(screen.getByLabelText("Kepribadian"), "Ramah");
    await user.type(screen.getByLabelText("Target audiens"), "Dewasa");
    await user.type(screen.getByLabelText("Gaya berpakaian"), "Casual");
    await user.click(screen.getByRole("button", { name: "Simpan draft" }));

    expect(await screen.findByText("Nadia", { selector: "h3" })).toBeInTheDocument();
    expect(createPersona).toHaveBeenCalledWith(expect.objectContaining({ name: "Nadia", age: 28 }));
  });
});
