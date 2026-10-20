// @vitest-environment jsdom
import { assessmentFixture } from "../../../../../../../libs/types/src/__tests__/itso.fixture";
import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useEvaluationResults } from "../useEvaluationResults";

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
function wrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return {
    client,
    wrapper: ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    ),
  };
}
describe("current results hook version integration", () => {
  it("keeps a 202 pending projection out of legacy data and later reads typed five-row v2", async () => {
    let calls = 0;
    const fetcher = vi.fn(async (url: string) =>
      url.endsWith("/results")
        ? json({ detail: { code: "unsupported_version" } }, 409)
        : ++calls === 1
          ? json({ detail: { code: "assessment_not_ready" } }, 202)
          : json(assessmentFixture()),
    );
    vi.stubGlobal("fetch", fetcher);
    const provider = wrapper();
    const hook = renderHook(
      () => useEvaluationResults("evaluation-1", "COMPLETED", "itso"),
      { wrapper: provider.wrapper },
    );
    await waitFor(() =>
      expect(hook.result.current.isAssessmentPending).toBe(true),
    );
    expect(hook.result.current.data).toBeUndefined();
    expect(hook.result.current.assessment).toBeUndefined();
    await act(async () => {
      await hook.result.current.refetch();
    });
    await waitFor(() =>
      expect(hook.result.current.assessment?.criteria).toHaveLength(5),
    );
    expect(hook.result.current.assessment?.subtotal).toBeNull();
    expect(hook.result.current.data).toBeUndefined();
    expect(fetcher.mock.calls.map(([url]) => url)).toEqual([
      "/api/v1/evaluations/evaluation-1/results",
      "/api/v1/evaluations/evaluation-1/assessment",
      "/api/v1/evaluations/evaluation-1/results",
      "/api/v1/evaluations/evaluation-1/assessment",
    ]);
    provider.client.clear();
  });
  it("reads scored ITSO results directly without requesting the historical endpoint", async () => {
    const results = {
      evaluation_id: "scored-run",
      domain_scores: {
        itso: {
          subtotal: 3,
          criteria: [{ criterion_id: "ITSO-01", score: 3 }],
        },
      },
    };
    const fetcher = vi.fn(async (_url: string) => json(results));
    vi.stubGlobal("fetch", fetcher);
    const provider = wrapper();
    const hook = renderHook(
      () => useEvaluationResults("scored-run", "COMPLETED", "itso"),
      { wrapper: provider.wrapper },
    );
    await waitFor(() => expect(hook.result.current.data).toEqual(results));
    expect(hook.result.current.assessment).toBeUndefined();
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(fetcher.mock.calls[0][0]).toBe(
      "/api/v1/evaluations/scored-run/results",
    );
    provider.client.clear();
  });
  it.each([
    [403, "forbidden"],
    [404, "not_found"],
    [500, "assessment_integrity_failed"],
    [409, "assessment_integrity_failed"],
  ])(
    "preserves a %s error without trying a different reader",
    async (status, code) => {
      const fetcher = vi.fn(async () => json({ detail: { code } }, status));
      vi.stubGlobal("fetch", fetcher);
      const provider = wrapper();
      const hook = renderHook(
        () => useEvaluationResults("evaluation-1", "COMPLETED", "itso"),
        { wrapper: provider.wrapper },
      );
      await waitFor(() => expect(hook.result.current.isError).toBe(true));
      expect(hook.result.current.data).toBeUndefined();
      expect(hook.result.current.assessment).toBeUndefined();
      expect(fetcher).toHaveBeenCalledTimes(1);
      provider.client.clear();
    },
  );
  it("leaves SME requests on the existing results route", async () => {
    const fetcher = vi.fn(async (_url: string) =>
      json({ evaluation_id: "sme-run", domain_scores: {} }),
    );
    vi.stubGlobal("fetch", fetcher);
    const provider = wrapper();
    const hook = renderHook(
      () => useEvaluationResults("sme-run", "COMPLETED", "sme"),
      { wrapper: provider.wrapper },
    );
    await waitFor(() =>
      expect(hook.result.current.data?.evaluation_id).toBe("sme-run"),
    );
    expect(fetcher.mock.calls[0][0]).toBe(
      "/api/v1/evaluations/sme-run/results",
    );
    provider.client.clear();
  });
});
