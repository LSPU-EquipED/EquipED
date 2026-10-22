import { requestJson } from "@equiped/api-client";
import type { Course, Mappings, Objective, ObjectiveInput } from "./types";

const root = "/curriculum-map";
const json = (body: unknown, method = "PUT") => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});
export const curriculumApi = {
  objectives: () =>
    requestJson<{ items: Objective[] }>(`${root}/admin/objectives`),
  courses: () => requestJson<{ items: Course[] }>(`${root}/courses`),
  saveObjective: (input: ObjectiveInput, id?: string) =>
    requestJson<Objective>(
      `${root}/admin/objectives${id ? `/${encodeURIComponent(id)}` : ""}`,
      json(input, id ? "PUT" : "POST"),
    ),
  mappings: (id: string) =>
    requestJson<Mappings>(
      `${root}/admin/courses/${encodeURIComponent(id)}/mappings`,
    ),
  saveMappings: (input: Mappings) =>
    requestJson<Mappings>(
      `${root}/admin/courses/${encodeURIComponent(input.course_id)}/mappings`,
      json({ version: input.version, entries: input.entries }),
    ),
};
