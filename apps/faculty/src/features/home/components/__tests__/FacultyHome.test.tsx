import { afterEach, describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { FacultyHome } from "../FacultyHome";
import type { useFacultyHome } from "../../hooks/useFacultyHome";

const mockUseFacultyHome = vi.fn();

vi.mock("../../hooks/useFacultyHome", () => ({
  useFacultyHome: () => mockUseFacultyHome(),
}));

vi.mock("@tanstack/react-router", () => ({
  Link: ({
    to,
    params,
    children,
    className,
  }: {
    to: string;
    params?: Record<string, string>;
    children?: React.ReactNode;
    className?: string;
  }) => {
    let href = to;
    if (params) {
      Object.entries(params).forEach(([key, val]) => {
        href = href.replace(`$${key}`, val);
      });
    }
    return (
      <a href={href} className={className}>
        {children}
      </a>
    );
  },
}));

describe("FacultyHome", () => {
  afterEach(() => vi.useRealTimers());
  const defaultHomeState = {
    isLoading: false,
    isError: false,
    error: null,
    stats: { total: 1, ready: 1, processing: 0, failed: 0 },
    homeData: {
      activeEvaluation: null,
    },
    evaluations: [
      {
        evaluation_id: "eval-1",
        document_id: "doc-1",
        document_title: "Operating Systems Module",
        syllabus_id: "syl-1",
        curriculum_id: "curr-1",
        status: "COMPLETED",
        submitted_at: "2026-08-20T12:00:00Z",
      },
    ],
    refetch: vi.fn(),
  } satisfies ReturnType<typeof useFacultyHome>;

  it("renders evaluation activity and the module overview", () => {
    mockUseFacultyHome.mockReturnValue(defaultHomeState);
    const markup = renderToStaticMarkup(<FacultyHome />);

    expect(markup).toContain("Recent activity");
    expect(markup).toContain("Module overview");
  });

  it("keeps the library summary focused on the total when uploads need no attention", () => {
    mockUseFacultyHome.mockReturnValue(defaultHomeState);
    const markup = renderToStaticMarkup(<FacultyHome />);

    expect(markup).toContain("Total modules");
    expect(markup).not.toContain("Processed");
    expect(markup).not.toContain("Module processing updates");
  });

  it("keeps active upload processing and failures visible without the old metric strip", () => {
    mockUseFacultyHome.mockReturnValue({
      ...defaultHomeState,
      stats: { total: 4, ready: 1, processing: 2, failed: 1 },
    });
    const markup = renderToStaticMarkup(<FacultyHome />);
    const text = markup.replace(/<[^>]*>/g, "");
    expect(text).toContain("2 processing");
    expect(text).toContain("1 failed upload");
    expect(markup).toContain("Module processing updates");
    expect(markup).toContain('href="/documents"');
  });

  it("renders recent evaluation links instead of a searchable table", () => {
    mockUseFacultyHome.mockReturnValue(defaultHomeState);
    const markup = renderToStaticMarkup(<FacultyHome />);

    expect(markup).toContain("Recent activity");
    expect(markup).toContain("Operating Systems Module");
    expect(markup).toContain("Completed");
    expect(markup).toContain("View history");
    expect(markup).not.toContain("<table");
    expect(markup).not.toContain("Search evaluations");
    expect(markup).not.toContain("Requires review");
    expect(markup).toContain('href="/evaluations/eval-1"');
  });

  it("renders empty state guidance when no evaluations exist yet", () => {
    mockUseFacultyHome.mockReturnValue({
      ...defaultHomeState,
      evaluations: [],
    });
    const markup = renderToStaticMarkup(<FacultyHome />);

    expect(markup).toContain("No evaluations yet.");
  });

  it.each([
    [8, "Good morning, Jeremy."],
    [14, "Good afternoon, Jeremy."],
    [20, "Good evening, Jeremy."],
  ])(
    "greets the signed-in user at local hour %s without a dashboard upload shortcut",
    (hour, greeting) => {
      vi.useFakeTimers();
      vi.setSystemTime(new Date(2026, 9, 1, hour));
      mockUseFacultyHome.mockReturnValue(defaultHomeState);
      const markup = renderToStaticMarkup(
        <FacultyHome displayName="Jeremy Garin" />,
      );
      expect(markup).toContain(greeting);
      expect(markup).toMatch(/datetime="2026-10-01"/i);
      expect(markup).not.toContain("Upload module");
      expect(markup).not.toContain('href="/documents?upload=true"');
    },
  );

  it("uses a greeting without a name when profile details are unavailable", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 9, 1, 8));
    mockUseFacultyHome.mockReturnValue(defaultHomeState);
    const markup = renderToStaticMarkup(<FacultyHome displayName="  " />);
    expect(markup).toContain("Good morning.");
    expect(markup).not.toContain("undefined");
  });

  it("renders active evaluation banner when evaluation is in progress", () => {
    mockUseFacultyHome.mockReturnValue({
      ...defaultHomeState,
      homeData: {
        ...defaultHomeState.homeData,
        activeEvaluation: {
          evaluation_id: "eval-in-progress-1234",
          target_agent: "sme",
          document_id: "doc-1",
          document_title: "Operating Systems Module",
          syllabus_id: "syl-1",
          curriculum_id: "curr-1",
          status: "EVALUATING",
          submitted_at: "2026-08-20T12:00:00Z",
        },
      },
    });
    const markup = renderToStaticMarkup(<FacultyHome />);

    expect(markup).toContain("Specialist review");
    expect(markup).toContain("View progress");
    expect(markup).toContain('href="/specialists/sme/doc-1"');
    expect(markup).toContain("Operating Systems Module");
  });

  it("links all-agent active evaluations to the combined scorecard", () => {
    mockUseFacultyHome.mockReturnValue({
      ...defaultHomeState,
      homeData: {
        ...defaultHomeState.homeData,
        activeEvaluation: {
          evaluation_id: "eval-all-1234",
          document_id: "doc-1",
          document_title: "Operating Systems Module",
          syllabus_id: "syl-1",
          curriculum_id: "curr-1",
          status: "EVALUATING",
          target_agent: "all",
          submitted_at: "2026-08-20T12:00:00Z",
        },
      },
    });

    const markup = renderToStaticMarkup(<FacultyHome />);

    expect(markup).toContain("View progress");
    expect(markup).toContain("/evaluations/eval-all-1234");
    expect(markup).not.toContain("/specialists/sme/doc-1");
  });

  it.each([undefined, null, []])(
    "shows all shortcuts for unrestricted assignments (%s)",
    (evaluatorPermissions) => {
      mockUseFacultyHome.mockReturnValue(defaultHomeState);
      const markup = renderToStaticMarkup(
        <FacultyHome evaluatorPermissions={evaluatorPermissions} />,
      );
      for (const agent of ["sme", "coordinator", "gad", "itso"]) {
        expect(markup).toContain(`href="/specialists/${agent}"`);
      }
      expect(markup).toContain('href="/syllabus-alignment"');
      expect(markup).toContain('href="/curriculum-alignment"');
    },
  );

  it("limits specialist shortcuts to the assigned workspaces while retaining alignment checks", () => {
    mockUseFacultyHome.mockReturnValue(defaultHomeState);
    const markup = renderToStaticMarkup(
      <FacultyHome evaluatorPermissions={["coordinator", "gad"]} />,
    );
    expect(markup).toContain('href="/specialists/coordinator"');
    expect(markup).toContain('href="/specialists/gad"');
    expect(markup).not.toContain('href="/specialists/sme"');
    expect(markup).not.toContain('href="/specialists/itso"');
    expect(markup).toContain('href="/syllabus-alignment"');
    expect(markup).toContain('href="/curriculum-alignment"');
  });

  it("shows every specialist to admins regardless of assignments", () => {
    mockUseFacultyHome.mockReturnValue(defaultHomeState);
    const markup = renderToStaticMarkup(
      <FacultyHome userRole="admin" evaluatorPermissions={["sme"]} />,
    );
    for (const agent of ["sme", "coordinator", "gad", "itso"]) {
      expect(markup).toContain(`href="/specialists/${agent}"`);
    }
  });

  it("renders all four explicitly assigned workspaces with their own links", () => {
    mockUseFacultyHome.mockReturnValue(defaultHomeState);
    const markup = renderToStaticMarkup(
      <FacultyHome
        evaluatorPermissions={["sme", "coordinator", "gad", "itso"]}
      />,
    );
    for (const agent of ["sme", "coordinator", "gad", "itso"]) {
      expect(markup).toContain(`href="/specialists/${agent}"`);
    }
    expect(markup).toContain("Gender and Development");
    expect(markup).not.toContain("layout sample");
  });

  it("keeps the greeting and navigation available on errors while offering retry", () => {
    mockUseFacultyHome.mockReturnValue({
      ...defaultHomeState,
      isError: true,
      error: new Error("Connection failed"),
    });
    const markup = renderToStaticMarkup(
      <FacultyHome evaluatorPermissions={["sme"]} />,
    );
    expect(markup).toContain('role="alert"');
    expect(markup).toContain("Retry");
    expect(markup).toContain("<h1");
    expect(markup).toContain('href="/specialists/sme"');
    expect(markup).toContain('href="/syllabus-alignment"');
    expect(markup).not.toContain("Module overview");
    expect(markup).not.toContain("Recent activity");
  });

  it("shows loading placeholders without presenting pending data as actual counts or records", () => {
    mockUseFacultyHome.mockReturnValue({
      ...defaultHomeState,
      isLoading: true,
      stats: { total: 783, ready: 781, processing: 2, failed: 0 },
    });
    const markup = renderToStaticMarkup(<FacultyHome />);
    expect(markup).toContain("Loading recent activity");
    expect(markup).not.toContain(">783<");
    expect(markup).not.toContain(">781<");
    expect(markup).not.toContain("Operating Systems Module");
    expect(markup).not.toContain("Module processing updates");
  });
});
