// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { CourseMappings } from "../components/CourseMappings";

const save = vi.hoisted(() => vi.fn().mockResolvedValue({}));
vi.mock("../hooks", () => ({
  useUnsavedChanges: vi.fn(),
  useCourses: () => ({
    data: {
      items: [
        {
          course_id: "course",
          course_code: "IT101",
          course_title: "Networking",
          program: "BSIT",
        },
      ],
    },
  }),
  useMappings: (id: string) => ({
    data: id ? { course_id: id, version: 2, entries: [] } : undefined,
  }),
  useSaveMappings: () => ({ mutateAsync: save, isPending: false, error: null }),
}));
afterEach(cleanup);

it("maps only matching-program objectives and submits the captured version", async () => {
  const onDirty = vi.fn();
  render(
    <CourseMappings
      onDirtyChange={onDirty}
      objectives={[
        {
          objective_id: "it",
          code: "IT13",
          description: "Explain networks",
          program: "BSInfoTech",
          version: 1,
          mapping_count: 0,
        },
        {
          objective_id: "cs",
          code: "CS01",
          description: "Computer science",
          program: "BSCS",
          version: 1,
          mapping_count: 0,
        },
      ]}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Course" }));
  fireEvent.click(screen.getByRole("option", { name: /IT101/ }));
  expect(screen.queryByText("Computer science")).toBeNull();
  fireEvent.click(
    screen.getByRole("button", { name: "Expected level for IT13" }),
  );
  fireEvent.click(screen.getByRole("option", { name: "E — Enabling" }));
  fireEvent.submit(
    screen.getByRole("button", { name: "Save mappings" }).closest("form")!,
  );
  await waitFor(() =>
    expect(save).toHaveBeenCalledWith({
      course_id: "course",
      version: 2,
      entries: [{ objective_id: "it", level: "E" }],
    }),
  );
  expect(onDirty).toHaveBeenCalledWith(true);
});
