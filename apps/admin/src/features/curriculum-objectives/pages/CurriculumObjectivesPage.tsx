import { useState } from "react";
import { Plus, PencilSimple } from "@phosphor-icons/react";
import { BUTTON_STYLES, Dropdown, PageContainer, cn } from "@equiped/ui";
import { CANONICAL_PROGRAMS } from "@equiped/types";
import { getErrorMessage } from "@equiped/api-client";
import { useObjectives } from "../hooks";
import { ObjectiveForm } from "../components/ObjectiveForm";
import { CourseMappings } from "../components/CourseMappings";
import type { Objective } from "../types";

export function CurriculumObjectivesPage() {
  const objectives = useObjectives();
  const [tab, setTab] = useState<"objectives" | "mappings">("objectives");
  const [mappingDirty, setMappingDirty] = useState(false);
  const [search, setSearch] = useState("");
  const [program, setProgram] = useState("");
  const [editing, setEditing] = useState<Objective | "new" | null>(null);
  const [editorRevision, setEditorRevision] = useState(0);
  const items = objectives.data?.items ?? [];
  const filtered = items.filter(
    (item) =>
      (!program || item.program === program) &&
      `${item.code} ${item.description}`
        .toLowerCase()
        .includes(search.trim().toLowerCase()),
  );
  return (
    <PageContainer as="section" className="space-y-5">
      <header className="flex flex-wrap items-start justify-between gap-4 border-b border-border pb-5">
        <div>
          <h1 className="text-xl font-semibold text-text">
            Curriculum Objectives
          </h1>
          <p className="mt-1 max-w-3xl text-sm text-text-muted">
            Maintain program objectives and the expected learning depth for each
            course. Saved changes apply to future alignment checks.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setEditing("new")}
          disabled={mappingDirty}
          className={cn(
            BUTTON_STYLES.base,
            BUTTON_STYLES.variants.primary,
            BUTTON_STYLES.sizes.md,
          )}
        >
          <Plus className="size-4" aria-hidden="true" />
          Add objective
        </button>
      </header>
      <nav
        aria-label="Curriculum sections"
        className="flex gap-5 border-b border-border"
      >
        {(["objectives", "mappings"] as const).map((value) => (
          <button
            key={value}
            type="button"
            aria-current={tab === value ? "page" : undefined}
            onClick={() => {
              if (
                tab !== value &&
                (!mappingDirty ||
                  window.confirm("Discard unsaved mapping changes?"))
              ) {
                setMappingDirty(false);
                setTab(value);
              }
            }}
            className={cn(
              "border-b-2 px-1 py-3 text-sm font-semibold focus-visible:outline-2 focus-visible:outline-ring",
              tab === value
                ? "border-primary text-primary"
                : "border-transparent text-text-muted",
            )}
          >
            {value === "objectives" ? "Objective catalog" : "Course mappings"}
          </button>
        ))}
      </nav>
      <p className="text-sm text-text-muted">
        Programs: BSCS and BSInfoTech. Curriculum alignment uses objectives mapped
        to courses in the same program.
      </p>
      {objectives.isLoading ? <p role="status">Loading objectives…</p> : null}
      {objectives.error ? (
        <div role="alert" className="text-sm text-destructive">
          {getErrorMessage(objectives.error)}{" "}
          <button
            type="button"
            className="underline"
            onClick={() => void objectives.refetch()}
          >
            Retry
          </button>
        </div>
      ) : null}
      {objectives.data && tab === "objectives" ? (
        <>
          <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_14rem]">
            <label className="text-sm font-semibold text-text">
              Search objectives
              <input
                type="search"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search code or description"
                className="mt-1 w-full rounded-sm border border-input bg-surface px-3 py-2 text-sm focus-visible:outline-2 focus-visible:outline-ring"
              />
            </label>
            <Dropdown
              label="Program filter"
              value={program}
              onChange={setProgram}
              options={[
                { value: "", label: "All programs" },
                ...CANONICAL_PROGRAMS.map((value) => ({ value, label: value })),
              ]}
            />
          </div>
          <div className="overflow-x-auto rounded-sm border border-border bg-surface">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border bg-surface-subtle text-text">
                <tr>
                  {[
                    "Code",
                    "Description",
                    "Program",
                    "Course mappings",
                    "Actions",
                  ].map((title) => (
                    <th
                      key={title}
                      scope="col"
                      className="px-4 py-3 font-semibold"
                    >
                      {title}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {filtered.map((item) => (
                  <tr key={item.objective_id} className="align-top">
                    <td className="px-4 py-4 font-mono font-semibold text-text">
                      {item.code}
                    </td>
                    <td className="min-w-64 max-w-2xl whitespace-pre-wrap break-words px-4 py-4 text-text-muted">
                      {item.description}
                    </td>
                    <td className="px-4 py-4 text-text">{item.program}</td>
                    <td className="px-4 py-4 text-text-muted">
                      {item.mapping_count
                        ? `${item.mapping_count} courses`
                        : "Not mapped"}
                    </td>
                    <td className="px-4 py-3">
                      <button
                        type="button"
                        aria-label={`Edit ${item.code}`}
                        onClick={() => setEditing(item)}
                        className={cn(
                          BUTTON_STYLES.base,
                          BUTTON_STYLES.variants.secondary,
                          BUTTON_STYLES.sizes.sm,
                        )}
                      >
                        <PencilSimple className="size-4" aria-hidden="true" />
                        Edit
                      </button>
                    </td>
                  </tr>
                ))}
                {!filtered.length ? (
                  <tr>
                    <td
                      colSpan={5}
                      className="px-4 py-10 text-center text-text-muted"
                    >
                      {items.length
                        ? "No objectives match your filters."
                        : "No objectives yet. Add an objective to get started."}
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-text-muted">
            {filtered.length} of {items.length} objectives
          </p>
        </>
      ) : null}
      {objectives.data && tab === "mappings" ? (
        <CourseMappings objectives={items} onDirtyChange={setMappingDirty} />
      ) : null}
      {editing ? (
        <ObjectiveForm
          key={
            editing === "new"
              ? "new"
              : `${editing.objective_id}:${editing.version}:${editorRevision}`
          }
          objective={editing === "new" ? undefined : editing}
          onClose={() => setEditing(null)}
          onReload={async () => {
            if (editing === "new") return;
            const latest = await objectives.refetch();
            const current = latest.data?.items.find(
              (item) => item.objective_id === editing.objective_id,
            );
            if (current) {
              setEditing(current);
              setEditorRevision((value) => value + 1);
            }
          }}
        />
      ) : null}
    </PageContainer>
  );
}
