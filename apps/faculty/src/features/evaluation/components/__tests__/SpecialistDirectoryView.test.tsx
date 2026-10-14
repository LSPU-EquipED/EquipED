// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TARGET_AGENT_META } from "@equiped/types";
import { SpecialistDirectoryView } from "../SpecialistDirectoryView";

vi.mock("@tanstack/react-router", () => ({ useNavigate: () => vi.fn() }));
afterEach(cleanup);

describe("SpecialistDirectoryView module browser", () => {
  it.each(["READY", "COMPLETED"])(
    "keeps a single selector for a %s module",
    (status) => {
      render(
        <SpecialistDirectoryView
          validAgent="sme"
          meta={TARGET_AGENT_META.sme}
          items={[
            {
              document_id: "completed-module",
              title: "Previously evaluated SLM",
              course_code: "CS101",
              program: "BSCS",
              uploaded_at: "2026-10-15T00:00:00Z",
              my_status: status,
              my_score: 3,
              my_adjectival: "Satisfactory",
              peer_completed_count: 1,
              peer_completed_desks: ["sme"],
            },
          ]}
        />,
      );
      expect(
        screen.queryByRole("button", { name: "Browse modules" }),
      ).toBeNull();
      expect(
        screen.getAllByRole("button", { name: "Select module" }),
      ).toHaveLength(1);
      fireEvent.click(screen.getByRole("button", { name: "Select module" }));
      expect(
        screen.getByRole("dialog", { name: "Select module" }),
      ).toBeDefined();
      expect(
        screen.getByRole("button", {
          name: new RegExp(
            `Previously evaluated SLM.*${status === "COMPLETED" ? "View results" : "Evaluate"}`,
          ),
        }),
      ).toBeDefined();
    },
  );
});
