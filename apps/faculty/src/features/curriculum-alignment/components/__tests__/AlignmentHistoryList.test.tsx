// @vitest-environment jsdom
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AlignmentHistoryList } from "../AlignmentHistoryList";
import { curriculumAlignmentApi } from "../../api/curriculumAlignment.api";
import type { AlignmentCheckListItem } from "../../types";

const item: AlignmentCheckListItem = {
  check_id: "check-1",
  document_id: "doc-1",
  document_title: "Networking module",
  course_id: "course-1",
  course_title: "IT101 — Networking",
  run_at: "2026-10-10T12:00:00Z",
  success: true,
  error_message: null,
  summary: {
    total_mapped_objectives: 2,
    match: 1,
    under_developed: 1,
    over_developed: 0,
    not_addressed: 0,
  },
};
const response = (
  items: AlignmentCheckListItem[] = [item],
  total = items.length,
  page = 1,
  pageSize = 10,
) => ({ items, total, page, page_size: pageSize });
let queryClient: QueryClient;
beforeEach(() => {
  queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
});
afterEach(() => {
  cleanup();
  queryClient.clear();
  vi.restoreAllMocks();
});
function renderHistory(onSelect = vi.fn()) {
  render(
    <QueryClientProvider client={queryClient}>
      <AlignmentHistoryList onSelect={onSelect} />
    </QueryClientProvider>,
  );
  return onSelect;
}

describe("AlignmentHistoryList", () => {
  it("shows the empty history without inviting a redundant setup step", async () => {
    vi.spyOn(curriculumAlignmentApi, "listChecks").mockResolvedValue(
      response([]),
    );
    renderHistory();
    expect(await screen.findByText("No checks yet")).toBeDefined();
    expect(
      screen.queryByRole("button", { name: "Checks per page" }),
    ).toBeNull();
  });

  it("opens a saved check and keeps failed checks distinct", async () => {
    const failed = {
      ...item,
      check_id: "check-2",
      document_title: "Failed module",
      success: false,
    };
    vi.spyOn(curriculumAlignmentApi, "listChecks").mockResolvedValue(
      response([item, failed]),
    );
    const select = renderHistory();
    await screen.findByText("Networking module");
    expect(screen.getByText("Completed")).toBeDefined();
    expect(screen.getByText("Failed")).toBeDefined();
    fireEvent.click(
      screen.getByRole("button", { name: "View check for Failed module" }),
    );
    expect(select).toHaveBeenCalledWith(failed);
    expect(screen.getAllByText("Oct 10, 2026")).toHaveLength(2);
  });

  it("requires confirmation before deleting and allows cancellation", async () => {
    vi.spyOn(curriculumAlignmentApi, "listChecks").mockResolvedValue(
      response(),
    );
    const remove = vi
      .spyOn(curriculumAlignmentApi, "deleteCheck")
      .mockResolvedValue(undefined);
    renderHistory();
    await screen.findByText("Networking module");
    fireEvent.click(
      screen.getByRole("button", {
        name: "Delete check for Networking module",
      }),
    );
    expect(remove).not.toHaveBeenCalled();
    fireEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "Cancel",
      }),
    );
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(remove).not.toHaveBeenCalled();
    fireEvent.click(
      screen.getByRole("button", {
        name: "Delete check for Networking module",
      }),
    );
    fireEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "Delete",
      }),
    );
    await waitFor(() => expect(remove).toHaveBeenCalledWith("check-1"));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("retains the confirmation when deletion fails", async () => {
    vi.spyOn(curriculumAlignmentApi, "listChecks").mockResolvedValue(
      response(),
    );
    vi.spyOn(curriculumAlignmentApi, "deleteCheck").mockRejectedValue(
      new Error("Unable to delete check"),
    );
    renderHistory();
    await screen.findByText("Networking module");
    fireEvent.click(
      screen.getByRole("button", {
        name: "Delete check for Networking module",
      }),
    );
    fireEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "Delete",
      }),
    );
    expect(await screen.findByText("Unable to delete check")).toBeDefined();
    expect(screen.getByRole("dialog")).toBeDefined();
  });

  it("resets the current page when changing the shared rows dropdown", async () => {
    const list = vi
      .spyOn(curriculumAlignmentApi, "listChecks")
      .mockImplementation(async (page, size) =>
        response(
          [{ ...item, document_title: `Page ${page} module` }],
          26,
          page,
          size,
        ),
      );
    renderHistory();
    await screen.findByText("Page 1 module");
    fireEvent.click(screen.getByRole("button", { name: "Next page" }));
    await screen.findByText("Page 2 module");
    fireEvent.click(screen.getByRole("button", { name: "Checks per page" }));
    fireEvent.click(screen.getByRole("option", { name: "25 rows" }));
    await waitFor(() => expect(list).toHaveBeenLastCalledWith(1, 25));
    await screen.findByText("Page 1 module");
  });

  it("recovers to the previous valid page after the final record is deleted", async () => {
    let deleted = false;
    const list = vi
      .spyOn(curriculumAlignmentApi, "listChecks")
      .mockImplementation(async (page, size) =>
        response(
          deleted && page === 2
            ? []
            : [{ ...item, document_title: `Page ${page} module` }],
          deleted ? 10 : 11,
          page,
          size,
        ),
      );
    vi.spyOn(curriculumAlignmentApi, "deleteCheck").mockImplementation(
      async () => {
        deleted = true;
      },
    );
    renderHistory();
    await screen.findByText("Page 1 module");
    fireEvent.click(screen.getByRole("button", { name: "Next page" }));
    await screen.findByText("Page 2 module");
    fireEvent.click(
      screen.getByRole("button", { name: "Delete check for Page 2 module" }),
    );
    fireEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "Delete",
      }),
    );
    await screen.findByText("Page 1 module");
    await waitFor(() => expect(list).toHaveBeenLastCalledWith(1, 10));
  });

  it("retries a failed history request", async () => {
    vi.spyOn(curriculumAlignmentApi, "listChecks")
      .mockRejectedValueOnce(new Error("Connection failed"))
      .mockResolvedValue(response());
    renderHistory();
    await screen.findByRole("alert");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await screen.findByText("Networking module");
  });
});
