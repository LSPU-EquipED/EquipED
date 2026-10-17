import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { DocumentDashboard } from "../DocumentDashboard";

const latestEvaluations = vi.fn();
vi.mock("@/shared/hooks/useLatestEvaluations", () => ({
  useLatestEvaluations: (...args: unknown[]) => latestEvaluations(...args),
}));

// Mock dependencies
const mockUseSlmStorage = vi.fn();

vi.mock("@tanstack/react-router", () => ({
  useNavigate: () => vi.fn(),
  useLocation: () => ({ search: "?highlight=doc-1" }),
  Link: ({
    to,
    children,
    className,
  }: {
    to: string;
    children?: React.ReactNode;
    className?: string;
  }) => (
    <a href={to} className={className}>
      {children}
    </a>
  ),
}));

vi.mock("../../hooks/useSlmStorage", () => ({
  useSlmStorage: () => mockUseSlmStorage(),
}));

function renderWithClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe("DocumentDashboard - SLM Storage Repository", () => {
  const defaultStorageState = {
    search: "",
    setSearch: vi.fn(),
    programFilter: "ALL",
    setProgramFilter: vi.fn(),
    statusFilter: "all",
    setStatusFilter: vi.fn(),
    page: 1,
    setPage: vi.fn(),
    pageSize: 10,
    setPageSize: vi.fn(),
    total: 2,
    totalPages: 1,
    documents: [
      {
        documentId: "doc-1",
        title: "Network Systems Module",
        courseTitle: "IT 201",
        program: "BSInfoTech",
        sourceType: "slm",
        uploadedAt: "2026-08-15T10:00:00Z",
        processingStatus: "PROCESSED",
        pageCount: 25,
        hasOcrPages: true,
      },
      {
        documentId: "doc-2",
        title: "Database Admin Module",
        courseTitle: "IT 202",
        program: "BSInfoTech",
        sourceType: "slm",
        uploadedAt: "2026-08-16T11:00:00Z",
        processingStatus: "PENDING",
        pageCount: 20,
        hasOcrPages: false,
      },
    ],
    error: null,
    isLoading: false,
    inspectingDoc: null,
    setInspectingDoc: vi.fn(),
    isUploadOpen: false,
    setIsUploadOpen: vi.fn(),
    handleUploadComplete: vi.fn(),
  };

  it("renders the storage ledger and its primary action", () => {
    mockUseSlmStorage.mockReturnValue(defaultStorageState);
    const markup = renderWithClient(<DocumentDashboard />);

    expect(markup).toContain("Module Library inventory");
    expect(markup).not.toContain("Indexed content");
    expect(markup).toContain("Network Systems Module");
    expect(markup).toContain("Upload SLM");
    expect(markup).not.toContain(">Status<");
    expect(latestEvaluations).not.toHaveBeenCalled();
  });

  it("renders flash success banner with accessible contrast colors", () => {
    mockUseSlmStorage.mockReturnValue(defaultStorageState);
    const markup = renderWithClient(<DocumentDashboard />);

    expect(markup).toContain("SLM uploaded to Module library.");
    expect(markup).toContain("text-success");
    expect(markup).toContain("border-success/30");
    expect(markup).toContain("bg-success-soft");
  });

  it("renders empty state guidance when no modules exist in storage", () => {
    mockUseSlmStorage.mockReturnValue({
      ...defaultStorageState,
      total: 0,
      documents: [],
    });
    const markup = renderWithClient(<DocumentDashboard />);

    expect(markup).toContain("Your library is empty");
    expect(markup).toContain("Upload an SLM in PDF format");
  });
  it("shows a filtered empty state even when the filtered stats report zero modules", () => {
    mockUseSlmStorage.mockReturnValue({
      ...defaultStorageState,
      programFilter: "BSInfoTech",
      total: 0,
      documents: [],
    });
    const markup = renderWithClient(<DocumentDashboard />);
    expect(markup).toContain("No matching modules");
    expect(markup).toContain("Clear filters");
    expect(markup).not.toContain("Your library is empty");
  });
});
