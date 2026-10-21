// @vitest-environment jsdom
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SelectModuleModal } from "../SelectModuleModal";
import type { DeskQueueItem } from "../../../types";

const mockNavigate = vi.fn();
vi.mock("@tanstack/react-router", () => ({
  useNavigate: () => mockNavigate,
}));

describe("SelectModuleModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("browses all specialist states and opens results, failures, progress, and new evaluations", () => {
    const items = ["COMPLETED", "FAILED", "EVALUATING", "READY"].map(
      (status, index) => ({
        document_id: `doc-${index}`,
        title: `${status} module`,
        course_code: "CS101",
        program: "BSCS",
        uploaded_at: "2026-10-15T00:00:00Z",
        my_status: status,
        my_score: null,
        my_adjectival: null,
        peer_completed_count: 0,
        peer_completed_desks: [],
      }),
    );

    render(<SelectModuleModal agentId="gad" items={items} onClose={vi.fn()} />);
    expect(
      screen.getByRole("heading", { name: "Select module" }),
    ).toBeDefined();
    for (const [index, action] of [
      "View results",
      "Inspect evaluation",
      "View progress",
      "Evaluate",
    ].entries()) {
      const row = screen.getByRole("button", {
        name: new RegExp(`${items[index].title}.*${action}`),
      });
      fireEvent.click(row);
      expect(mockNavigate).toHaveBeenLastCalledWith({
        to: "/specialists/$agentId/$documentId",
        params: { agentId: "gad", documentId: items[index].document_id },
      });
    }
    fireEvent.change(
      screen.getByRole("searchbox", { name: "Search modules" }),
      {
        target: { value: "COMPLETED" },
      },
    );
    expect(screen.getByText("COMPLETED module")).toBeDefined();
    expect(screen.queryByText("FAILED module")).toBeNull();
  });

  it("includes FAILED status modules so they are selectable and retryable", async () => {
    const mockItems: DeskQueueItem[] = [
      {
        document_id: "doc-failed-001",
        title: "Algorithms Module (Failed Eval)",
        course_code: "CS102",
        program: "BSCS",
        uploaded_at: "2026-08-20T10:00:00Z",
        my_status: "FAILED",
        my_score: null,
        my_adjectival: null,
        peer_completed_count: 0,
        peer_completed_desks: [],
      },
      {
        document_id: "doc-completed-002",
        title: "Completed Module",
        course_code: "CS103",
        program: "BSCS",
        uploaded_at: "2026-08-20T10:00:00Z",
        my_status: "COMPLETED",
        my_score: 3.5,
        my_adjectival: "Satisfactory",
        peer_completed_count: 1,
        peer_completed_desks: ["sme"],
      },
    ];

    render(
      <SelectModuleModal agentId="sme" items={mockItems} onClose={vi.fn()} />,
    );

    // Failed module should be displayed in the modal
    expect(screen.getByText("Algorithms Module (Failed Eval)")).toBeDefined();
    // Completed SLMs remain available through the same selector.
    expect(screen.getByText("Completed Module")).toBeDefined();

    // Clicking the failed module selects it and routes to its desk workspace
    const failedBtn = screen.getByRole("button", {
      name: /Algorithms Module \(Failed Eval\)/i,
    });
    fireEvent.click(failedBtn);

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith({
        to: "/specialists/$agentId/$documentId",
        params: { agentId: "sme", documentId: "doc-failed-001" },
      });
    });
  });
  it("filters with the shared program dropdown and restores the complete list", () => {
    const items: DeskQueueItem[] = ["BSCS", "BSInfoTech"].map(
      (program, index) => ({
        document_id: `filtered-${index}`,
        title: `${program} SLM`,
        course_code: null,
        program,
        uploaded_at: "2026-10-15",
        my_status: "COMPLETED",
        my_score: 3,
        my_adjectival: "Satisfactory",
        peer_completed_count: 0,
        peer_completed_desks: [],
      }),
    );
    render(
      <SelectModuleModal
        agentId="coordinator"
        items={items}
        onClose={vi.fn()}
      />,
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Filter modules by program" }),
    );
    fireEvent.click(screen.getByRole("option", { name: "BSInfoTech" }));
    expect(screen.queryByText("BSCS SLM")).toBeNull();
    expect(screen.getByText("BSInfoTech SLM")).toBeDefined();
    fireEvent.change(
      screen.getByRole("searchbox", { name: "Search modules" }),
      { target: { value: "missing" } },
    );
    expect(screen.getByText("No matching modules")).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(screen.getByText("BSCS SLM")).toBeDefined();
    expect(screen.getByText("BSInfoTech SLM")).toBeDefined();
  });

  it("filters specialist states, groups active stages, and combines filters with search", () => {
    const items: DeskQueueItem[] = [
      "COMPLETED",
      "FAILED",
      "READY",
      "SUBMITTED",
      "PREPROCESSING",
      "EVALUATING",
      "SYNTHESIZING",
    ].map((status, index) => ({
      document_id: `status-${index}`,
      title: `${status} SLM`,
      course_code: "CS101",
      program: "BSCS",
      uploaded_at: "2026-10-15",
      my_status: status.toLowerCase(),
      my_score: null,
      my_adjectival: null,
      peer_completed_count: 0,
      peer_completed_desks: [],
    }));
    items.push({
      ...items[0],
      document_id: "other-program",
      title: "Other program SLM",
      program: "BSInfoTech",
    });
    render(<SelectModuleModal agentId="sme" items={items} onClose={vi.fn()} />);
    const chooseStatus = (name: string) => {
      fireEvent.click(
        screen.getByRole("button", { name: "Filter modules by status" }),
      );
      fireEvent.click(screen.getByRole("option", { name }));
    };
    for (const [label, expected] of [
      ["Completed", ["COMPLETED SLM", "Other program SLM"]],
      ["Failed", ["FAILED SLM"]],
      ["Not evaluated", ["READY SLM"]],
      [
        "Evaluating",
        [
          "SUBMITTED SLM",
          "PREPROCESSING SLM",
          "EVALUATING SLM",
          "SYNTHESIZING SLM",
        ],
      ],
    ] as const) {
      chooseStatus(label);
      expect(
        screen
          .getAllByRole("heading", { level: 3 })
          .map((el) => el.textContent),
      ).toEqual(expected);
    }
    chooseStatus("Completed");
    fireEvent.click(
      screen.getByRole("button", { name: "Filter modules by program" }),
    );
    fireEvent.click(screen.getByRole("option", { name: "BSInfoTech" }));
    expect(
      screen.getAllByRole("heading", { level: 3 }).map((el) => el.textContent),
    ).toEqual(["Other program SLM"]);
    fireEvent.change(
      screen.getByRole("searchbox", { name: "Search modules" }),
      { target: { value: "missing" } },
    );
    expect(screen.getByText("No matching modules")).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(screen.getAllByRole("heading", { level: 3 })).toHaveLength(8);
    expect(
      screen.getByRole("button", { name: "Filter modules by status" })
        .textContent,
    ).toBe("All statuses");
    expect(
      screen.getByRole("button", { name: "Filter modules by program" })
        .textContent,
    ).toBe("All programs");
  });

  it("contains keyboard focus, closes with Escape, and restores the trigger on unmount", () => {
    const trigger = document.createElement("button");
    document.body.appendChild(trigger);
    trigger.focus();
    const onClose = vi.fn();
    const { unmount } = render(
      <SelectModuleModal agentId="sme" items={[]} onClose={onClose} />,
    );
    const search = screen.getByRole("searchbox", { name: "Search modules" });
    expect(document.activeElement).toBe(search);
    expect(document.body.style.overflow).toBe("hidden");
    const cancel = screen.getByRole("button", { name: "Cancel" });
    cancel.focus();
    fireEvent.keyDown(cancel, { key: "Tab" });
    expect(document.activeElement).toBe(
      screen.getByRole("button", { name: "Close module selection" }),
    );
    fireEvent.keyDown(search, { key: "Escape" });
    expect(onClose).toHaveBeenCalledOnce();
    unmount();
    expect(document.activeElement).toBe(trigger);
    expect(document.body.style.overflow).not.toBe("hidden");
    trigger.remove();
  });
});
