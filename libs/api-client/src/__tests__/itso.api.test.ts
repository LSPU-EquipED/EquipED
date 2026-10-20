import { afterEach, describe, expect, it, vi } from "vitest";
import { itsoApi } from "../itso.api";
import { assessmentFixture } from "../../../types/src/__tests__/itso.fixture";

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});
describe("ITSO HTTP reads and preparation", () => {
  it("reads the versioned endpoint and preserves 202 instead of a completed empty result", async () => {
    const fetcher = vi.fn(async (_url: string) =>
      json({ detail: { code: "assessment_not_ready" } }, 202),
    );
    vi.stubGlobal("fetch", fetcher);
    expect(await itsoApi.getAssessment("run/1")).toEqual({
      detail: { code: "assessment_not_ready" },
    });
    expect(fetcher.mock.calls[0][0]).toBe(
      "/api/v1/evaluations/run%2F1/assessment",
    );
  });
  it("rejects legacy unsupported 409 and exposes its bounded code without fallback", async () => {
    const fetcher = vi.fn(async () =>
      json({ detail: { code: "unsupported_version" } }, 409),
    );
    vi.stubGlobal("fetch", fetcher);
    await expect(itsoApi.getAssessment("run-1")).rejects.toMatchObject({
      status: 409,
      detail: "unsupported_version",
    });
    expect(fetcher).toHaveBeenCalledOnce();
  });
  it("rejects protected generations rather than exporting them", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        json({
          ...assessmentFixture(),
          generations: [{ content: "Protected synthetic packet" }],
        }),
      ),
    );
    await expect(itsoApi.getAssessment("run-1")).rejects.toThrow(
      "Unsupported assessment",
    );
  });
});
