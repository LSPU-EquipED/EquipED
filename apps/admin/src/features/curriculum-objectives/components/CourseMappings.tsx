import { useCallback, useEffect, useState } from "react";
import { Dropdown, BUTTON_STYLES, cn } from "@equiped/ui";
import { normalizeProgram } from "@equiped/types";
import { getErrorMessage } from "@equiped/api-client";
import {
  useCourses,
  useMappings,
  useSaveMappings,
  useUnsavedChanges,
} from "../hooks";
import type { Mappings, Objective, Level } from "../types";

function MappingForm({
  initial,
  objectives,
  onDirtyChange,
  onReload,
}: {
  initial: Mappings;
  objectives: Objective[];
  onDirtyChange: (dirty: boolean) => void;
  onReload: () => void;
}) {
  const [levels, setLevels] = useState<Record<string, Level | "">>(() =>
    Object.fromEntries(
      initial.entries.map((entry) => [entry.objective_id, entry.level]),
    ),
  );
  const save = useSaveMappings();
  const entries = Object.entries(levels)
    .filter(([, level]) => level)
    .map(([objective_id, level]) => ({ objective_id, level: level as Level }));
  const signature = (items: Mappings["entries"]) =>
    JSON.stringify(
      [...items].sort((a, b) => a.objective_id.localeCompare(b.objective_id)),
    );
  const dirty = signature(entries) !== signature(initial.entries);
  useEffect(() => {
    onDirtyChange(dirty);
  }, [dirty, onDirtyChange]);
  useUnsavedChanges(dirty);
  return (
    <form
      className="space-y-4"
      onSubmit={async (event) => {
        event.preventDefault();
        try {
          await save.mutateAsync({ ...initial, entries });
        } catch {
          /* Mutation error remains visible. */
        }
      }}
    >
      <p className="text-sm text-text-muted">
        I — Introductory · E — Enabling · D — Demonstrative. Not mapped excludes
        an objective from this course’s future checks.
      </p>
      <div className="divide-y divide-border border-y border-border">
        {objectives.map((objective) => (
          <div
            key={objective.objective_id}
            className="grid gap-3 py-3 sm:grid-cols-[minmax(0,1fr)_11rem] sm:items-center"
          >
            <div>
              <span className="font-mono text-sm font-semibold">
                {objective.code}
              </span>
              <p className="mt-1 whitespace-pre-wrap break-words text-sm text-text-muted">
                {objective.description}
              </p>
            </div>
            <Dropdown
              aria-label={`Expected level for ${objective.code}`}
              value={levels[objective.objective_id] ?? ""}
              options={[
                { value: "", label: "Not mapped" },
                { value: "I", label: "I — Introductory" },
                { value: "E", label: "E — Enabling" },
                { value: "D", label: "D — Demonstrative" },
              ]}
              onChange={(value) =>
                setLevels((current) => ({
                  ...current,
                  [objective.objective_id]: value as Level | "",
                }))
              }
              disabled={save.isPending}
            />
          </div>
        ))}
      </div>
      {!objectives.length ? (
        <p className="text-sm text-text-muted">
          Add objectives for this program before mapping them to a course.
        </p>
      ) : null}
      {save.error ? (
        <p role="alert" className="text-sm text-destructive">
          {getErrorMessage(save.error)}
        </p>
      ) : null}
      {save.error ? (
        <button
          type="button"
          className="text-sm font-semibold text-primary underline"
          onClick={onReload}
        >
          Reload latest mappings
        </button>
      ) : null}
      <div className="flex items-center justify-end gap-3">
        {dirty ? (
          <span className="text-sm text-text-muted">Unsaved changes</span>
        ) : null}
        <button
          type="submit"
          disabled={!dirty || save.isPending}
          className={cn(
            BUTTON_STYLES.base,
            BUTTON_STYLES.variants.primary,
            BUTTON_STYLES.sizes.md,
          )}
        >
          {save.isPending ? "Saving…" : "Save mappings"}
        </button>
      </div>
    </form>
  );
}

export function CourseMappings({
  objectives,
  onDirtyChange,
}: {
  objectives: Objective[];
  onDirtyChange: (dirty: boolean) => void;
}) {
  const courses = useCourses();
  const [courseId, setCourseId] = useState("");
  const [dirty, setDirty] = useState(false);
  const reportDirty = useCallback(
    (value: boolean) => {
      setDirty(value);
      onDirtyChange(value);
    },
    [onDirtyChange],
  );
  const mappings = useMappings(courseId);
  const course = courses.data?.items.find(
    (item) => item.course_id === courseId,
  );
  return (
    <section className="space-y-5">
      <Dropdown
        label="Course"
        value={courseId}
        placeholder="Select a course"
        options={(courses.data?.items ?? []).map((item) => ({
          value: item.course_id,
          label: `${item.course_code} — ${item.course_title}`,
          description: normalizeProgram(item.program),
        }))}
        onChange={(value) => {
          if (
            !dirty ||
            window.confirm("Discard unsaved mapping changes and switch course?")
          ) {
            reportDirty(false);
            setCourseId(value);
          }
        }}
      />
      {courses.isLoading || mappings.isFetching ? (
        <p role="status" className="text-sm text-text-muted">
          Loading course mappings…
        </p>
      ) : null}
      {courses.error || mappings.error ? (
        <div role="alert" className="text-sm text-destructive">
          {getErrorMessage(courses.error || mappings.error)}{" "}
          <button
            type="button"
            className="underline"
            onClick={() => {
              void courses.refetch();
              void mappings.refetch();
            }}
          >
            Retry
          </button>
        </div>
      ) : null}
      {course && mappings.data && !mappings.isFetching ? (
        <MappingForm
          key={`${courseId}:${mappings.data.version}`}
          initial={mappings.data}
          objectives={objectives.filter(
            (item) => item.program === normalizeProgram(course.program),
          )}
          onDirtyChange={reportDirty}
          onReload={() => {
            if (
              !dirty ||
              window.confirm(
                "Discard your changes and load the latest mappings?",
              )
            ) {
              reportDirty(false);
              void mappings.refetch();
            }
          }}
        />
      ) : null}
    </section>
  );
}
