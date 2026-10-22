import { useEffect, useRef, useState } from "react";
import { Dropdown, BUTTON_STYLES, cn } from "@equiped/ui";
import { CANONICAL_PROGRAMS, type CanonicalProgram } from "@equiped/types";
import { getErrorMessage } from "@equiped/api-client";
import { useSaveObjective, useUnsavedChanges } from "../hooks";
import type { Objective } from "../types";

const inputClass =
  "w-full rounded-sm border border-input bg-surface px-3 py-2 text-sm text-text focus-visible:outline-2 focus-visible:outline-ring";
export function ObjectiveForm({
  objective,
  onClose,
  onReload,
}: {
  objective?: Objective;
  onClose: () => void;
  onReload?: () => Promise<void>;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [code, setCode] = useState(objective?.code ?? "");
  const [description, setDescription] = useState(objective?.description ?? "");
  const [program, setProgram] = useState<CanonicalProgram | "">(
    objective?.program ?? "",
  );
  const [validation, setValidation] = useState("");
  const save = useSaveObjective(objective?.objective_id);
  const dirty =
    code !== (objective?.code ?? "") ||
    description !== (objective?.description ?? "") ||
    program !== (objective?.program ?? "");
  useUnsavedChanges(dirty);
  useEffect(() => {
    dialog.current?.showModal();
  }, []);
  const close = () => {
    if (
      !save.isPending &&
      (!dirty || window.confirm("Discard your unsaved objective changes?"))
    )
      onClose();
  };
  return (
    <dialog
      ref={dialog}
      aria-labelledby="objective-form-title"
      onCancel={(event) => {
        event.preventDefault();
        close();
      }}
      className="m-auto w-[calc(100%-2rem)] max-w-xl rounded-md border border-border bg-surface p-0 text-text backdrop:bg-overlay/50"
    >
      <form
        className="space-y-4 p-5"
        onSubmit={async (event) => {
          event.preventDefault();
          if (!program || !code.trim() || !description.trim()) {
            setValidation("Code, description, and program are required.");
            return;
          }
          setValidation("");
          try {
            await save.mutateAsync({
              code: code.trim().toUpperCase(),
              description: description.trim(),
              program,
              ...(objective ? { version: objective.version } : {}),
            });
            onClose();
          } catch {
            /* Keep the entered values and show the mutation error. */
          }
        }}
      >
        <div className="border-b border-border pb-3">
          <h2 id="objective-form-title" className="text-lg font-semibold">
            {objective ? "Edit objective" : "Add objective"}
          </h2>
          <p className="mt-1 text-sm text-text-muted">
            Changes apply to future checks. Saved results retain their original
            objectives.
          </p>
        </div>
        {objective ? (
          <p className="text-sm text-text-muted">
            Used by {objective.mapping_count} courses. Remove incompatible
            mappings before changing program.
          </p>
        ) : null}
        <label className="block text-sm font-semibold">
          Code <span aria-hidden="true">*</span>
          <input
            autoFocus
            required
            maxLength={50}
            value={code}
            onChange={(event) => setCode(event.target.value)}
            disabled={save.isPending}
            className={`${inputClass} mt-1 uppercase`}
          />
        </label>
        <label className="block text-sm font-semibold">
          Description <span aria-hidden="true">*</span>
          <textarea
            required
            maxLength={4000}
            rows={5}
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            disabled={save.isPending}
            className={`${inputClass} mt-1 resize-y`}
          />
        </label>
        <Dropdown
          label="Program"
          required
          placeholder="Select a program"
          value={program}
          onChange={setProgram}
          options={CANONICAL_PROGRAMS.map((value) => ({ value, label: value }))}
          disabled={save.isPending}
        />
        <p className="text-sm text-text-muted">
          Map this objective to a course in the same program before using it in
          curriculum alignment.
        </p>
        {validation || save.error ? (
          <p role="alert" className="text-sm text-destructive">
            {validation || getErrorMessage(save.error)}
          </p>
        ) : null}
        {save.error && onReload ? (
          <button
            type="button"
            className="text-sm font-semibold text-primary underline"
            onClick={() => {
              if (
                !dirty ||
                window.confirm(
                  "Discard your changes and load the latest saved objective?",
                )
              )
                void onReload();
            }}
          >
            Reload latest objective
          </button>
        ) : null}
        <div className="flex justify-end gap-2 border-t border-border pt-4">
          <button
            type="button"
            onClick={close}
            disabled={save.isPending}
            className={cn(
              BUTTON_STYLES.base,
              BUTTON_STYLES.variants.secondary,
              BUTTON_STYLES.sizes.md,
            )}
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={save.isPending}
            className={cn(
              BUTTON_STYLES.base,
              BUTTON_STYLES.variants.primary,
              BUTTON_STYLES.sizes.md,
            )}
          >
            {save.isPending ? "Saving…" : "Save objective"}
          </button>
        </div>
      </form>
    </dialog>
  );
}
