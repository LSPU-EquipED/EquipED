import { beforeEach, expect, it, vi } from "vitest";
import { requestJson } from "@equiped/api-client";
import { curriculumApi } from "../api";
vi.mock("@equiped/api-client", () => ({ requestJson: vi.fn() }));
beforeEach(() => vi.clearAllMocks());

it("creates and updates objectives with explicit canonical fields and versions", async () => {
  const input = {
    code: "IT13",
    description: "Explain networks",
    program: "BSInfoTech" as const,
  };
  await curriculumApi.saveObjective(input);
  expect(requestJson).toHaveBeenLastCalledWith(
    "/curriculum-map/admin/objectives",
    expect.objectContaining({ method: "POST", body: JSON.stringify(input) }),
  );
  await curriculumApi.saveObjective({ ...input, version: 3 }, "id");
  expect(requestJson).toHaveBeenLastCalledWith(
    "/curriculum-map/admin/objectives/id",
    expect.objectContaining({
      method: "PUT",
      body: JSON.stringify({ ...input, version: 3 }),
    }),
  );
});

it("sends mapping replacement and its version without overwriting course fields", async () => {
  await curriculumApi.saveMappings({
    course_id: "course",
    version: 2,
    entries: [],
  });
  expect(requestJson).toHaveBeenCalledWith(
    "/curriculum-map/admin/courses/course/mappings",
    expect.objectContaining({
      method: "PUT",
      body: JSON.stringify({ version: 2, entries: [] }),
    }),
  );
});
