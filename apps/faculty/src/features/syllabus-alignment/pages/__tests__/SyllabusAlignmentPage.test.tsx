// @vitest-environment jsdom
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ComponentPropsWithoutRef, ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SyllabusAlignmentPage } from "../SyllabusAlignmentPage";
import { alignmentApi } from "../../api/syllabusAlignment.api";
import type {
  AlignmentRun,
  AlignmentSlmItem,
  AlignmentSlmListResponse,
} from "../../types";

vi.mock("@tanstack/react-router", () => ({
  Link: ({
    to,
    params,
    children,
    ...props
  }: {
    to?: string;
    params?: Record<string, string>;
    children?: ReactNode;
  } & ComponentPropsWithoutRef<"a">) => {
    let href = to || props.href || "#";
    if (params && to) {
      Object.entries(params).forEach(([key, val]) => {
        href = href.replace(`$${key}`, val);
      });
    }
    return (
      <a href={href} {...props}>
        {children}
      </a>
    );
  },
}));

const moduleItem: AlignmentSlmItem = {
  document_id: "slm-1",
  title: "Networking 101",
  program: "BSCS",
  course_code: "CS101",
  processing_status: "PROCESSED",
  uploaded_at: "2026-08-01T00:00:00Z",
  evaluation_available: true,
};

function result(overrides: Partial<AlignmentRun> = {}): AlignmentRun {
  return {
    alignment_id: "align-1",
    slm_document_id: "slm-1",
    syllabus_document_id: "syl-1",
    requested_by: "user-1",
    status: "COMPLETED",
    alignment_level: "MEETS",
    advisory_only: true,
    created_at: "2026-08-01T00:00:00Z",
    updated_at: "2026-08-01T00:01:00Z",
    ...overrides,
  };
}

function response(
  items: AlignmentSlmItem[] = [moduleItem],
  total = items.length,
  page = 1,
): AlignmentSlmListResponse {
  return { items, total, page, page_size: 10 };
}

describe("SyllabusAlignmentPage", () => {
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

  function renderPage() {
    return render(
      <QueryClientProvider client={queryClient}>
        <SyllabusAlignmentPage />
      </QueryClientProvider>,
    );
  }

  it("opens setup for unchecked modules without inventing missing metadata", async () => {
    vi.spyOn(alignmentApi, "listSlms").mockResolvedValue(response());
    renderPage();
    const link = await screen.findByRole("link", {
      name: "Set up check for Networking 101",
    });
    expect(link.getAttribute("href")).toBe("/syllabus-alignment/slm-1");
    expect(screen.getByText("Not checked")).toBeDefined();
    expect(screen.getByText("CS101 · BSCS")).toBeDefined();
    expect(screen.queryByText("No lesson title")).toBeNull();
  });

  it.each([
    [result(), "Meets syllabus", "View result"],
    [
      result({ alignment_level: "PARTIALLY_MEETS" }),
      "Partially meets",
      "View result",
    ],
    [
      result({ alignment_level: "DOES_NOT_MEET" }),
      "Does not meet",
      "View result",
    ],
    [
      result({ status: "FAILED", alignment_level: "UNAVAILABLE" }),
      "Check failed",
      "Retry check",
    ],
    [
      result({ status: "QUEUED", alignment_level: null }),
      "Queued",
      "View progress",
    ],
    [
      result({ status: "RUNNING", alignment_level: null }),
      "Checking syllabus",
      "View progress",
    ],
    [
      result({ alignment_level: "UNAVAILABLE" }),
      "Result unavailable",
      "View result",
    ],
  ])(
    "preserves the state and workspace action for %s",
    async (run, label, action) => {
      vi.spyOn(alignmentApi, "listSlms").mockResolvedValue(
        response([{ ...moduleItem, current_result: run }]),
      );
      renderPage();
      const modules = await screen.findByRole("list", {
        name: "Modules for syllabus checks",
      });
      expect(within(modules).getByText(label)).toBeDefined();
      expect(
        within(modules)
          .getByRole("link", { name: `${action} for Networking 101` })
          .getAttribute("href"),
      ).toBe("/syllabus-alignment/slm-1");
    },
  );

  it("keeps filters available when there are no matches and can clear them", async () => {
    const list = vi
      .spyOn(alignmentApi, "listSlms")
      .mockImplementation(async (_page, _size, options) =>
        options?.status_filter === "MEETS" ? response([]) : response(),
      );
    renderPage();
    await screen.findByText("Networking 101");
    fireEvent.click(screen.getByRole("button", { name: "Check status" }));
    fireEvent.click(screen.getByRole("option", { name: "Meets syllabus" }));
    await screen.findByText("No matching modules");
    expect(
      screen.getByRole("searchbox", { name: "Search syllabus alignments" }),
    ).toBeDefined();
    expect(screen.queryByText("No modules available")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
    await screen.findByText("Networking 101");
    await waitFor(() =>
      expect(list).toHaveBeenLastCalledWith(1, 10, {
        search: undefined,
        status_filter: undefined,
      }),
    );
  });

  it("resets pagination when search or status changes", async () => {
    const list = vi
      .spyOn(alignmentApi, "listSlms")
      .mockImplementation(async (page, _size, options) =>
        options?.search || options?.status_filter
          ? response()
          : response(
              [{ ...moduleItem, title: `Page ${page} module` }],
              11,
              page,
            ),
      );
    renderPage();
    await screen.findByText("Page 1 module");
    await waitFor(() =>
      expect(
        screen
          .getByRole("button", { name: "Next page" })
          .hasAttribute("disabled"),
      ).toBe(false),
    );
    fireEvent.click(screen.getByRole("button", { name: "Next page" }));
    await screen.findByText("Page 2 module");
    fireEvent.change(screen.getByRole("searchbox"), {
      target: { value: "Networking" },
    });
    await waitFor(() =>
      expect(list).toHaveBeenLastCalledWith(1, 10, {
        search: "Networking",
        status_filter: undefined,
      }),
    );
    await screen.findByText("Networking 101");
    fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
    await screen.findByText("Page 1 module");
    await waitFor(() =>
      expect(
        screen
          .getByRole("button", { name: "Next page" })
          .hasAttribute("disabled"),
      ).toBe(false),
    );
    fireEvent.click(screen.getByRole("button", { name: "Next page" }));
    await screen.findByText("Page 2 module");
    fireEvent.click(screen.getByRole("button", { name: "Check status" }));
    fireEvent.click(screen.getByRole("option", { name: "Partially meets" }));
    await waitFor(() =>
      expect(list).toHaveBeenLastCalledWith(1, 10, {
        search: undefined,
        status_filter: "PARTIALLY_MEETS",
      }),
    );
  });

  it("keeps unprocessed modules unavailable for new checks", async () => {
    vi.spyOn(alignmentApi, "listSlms").mockResolvedValue(
      response([
        {
          ...moduleItem,
          evaluation_available: false,
          processing_status: "PROCESSING",
        },
      ]),
    );
    renderPage();
    await screen.findByText("SLM not ready");
    expect(
      screen.queryByRole("link", { name: "Set up check for Networking 101" }),
    ).toBeNull();
  });

  it("offers Module library when there are no stored modules", async () => {
    vi.spyOn(alignmentApi, "listSlms").mockResolvedValue(response([]));
    renderPage();
    await screen.findByText("No modules available");
    expect(
      screen
        .getByRole("link", { name: "Open Module library" })
        .getAttribute("href"),
    ).toBe("/documents");
  });

  it("can retry a failed list request", async () => {
    const list = vi
      .spyOn(alignmentApi, "listSlms")
      .mockRejectedValueOnce(new Error("Connection failed"))
      .mockResolvedValue(response());
    renderPage();
    await screen.findByRole("alert");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await screen.findByText("Networking 101");
    expect(list).toHaveBeenCalledTimes(2);
  });
});
