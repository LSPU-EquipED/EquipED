import { Button, Dropdown, Skeleton } from "@equiped/ui";
import { CANONICAL_PROGRAMS } from "@equiped/types";
import type { EvaluationSetupState } from "../hooks/useEvaluationSetup";

type SetupFieldsState = Pick<
  EvaluationSetupState,
  | "meta"
  | "program"
  | "setProgram"
  | "isPending"
  | "isLoadingCurricula"
  | "isCurriculaError"
  | "retryCurricula"
  | "readyCurricula"
  | "curriculumId"
  | "setCurriculumId"
>;

export function EvaluationSetupFields({ setup }: { setup: SetupFieldsState }) {
  return (
    <div className="swp-setup-controls">
      <Dropdown
        label="Confirmed program"
        value={setup.program}
        onChange={setup.setProgram}
        disabled={setup.isPending}
        className="w-full"
        options={CANONICAL_PROGRAMS.map((value) => ({
          value,
          label:
            value === "BSCS"
              ? "BSCS · Computer Science"
              : "BSInfoTech · Information Technology",
        }))}
      />
      {setup.meta.id === "itso" && (
        <p className="text-xs text-text-muted">
          ITSO searches public references and checks available source pages for
          criteria 1 and 2 on every evaluation. Only public bibliography details
          or lesson/topic names are sent to the search provider; body passages
          and personal data stay local.
        </p>
      )}
      {setup.meta.requiresCurriculum &&
        (setup.isLoadingCurricula ? (
          <div role="status" aria-label="Loading verified curricula">
            <Skeleton className="h-4 w-32" />
            <Skeleton className="mt-2 h-10 w-full" />
          </div>
        ) : setup.isCurriculaError ? (
          <div role="alert" className="swp-setup-message">
            <p>Verified curricula could not be loaded.</p>
            <Button
              variant="secondary"
              size="sm"
              onClick={setup.retryCurricula}
            >
              Retry curricula
            </Button>
          </div>
        ) : setup.readyCurricula.length === 0 ? (
          <p role="alert" className="swp-setup-message">
            No verified curriculum found for {setup.program}. Coordinator
            evaluation requires one.
          </p>
        ) : (
          <Dropdown
            label="Verified curriculum"
            required
            placeholder="Select a curriculum"
            value={setup.curriculumId || ""}
            onChange={setup.setCurriculumId}
            disabled={setup.isPending}
            className="w-full"
            options={setup.readyCurricula.map((item) => ({
              value: item.documentId,
              label: item.title,
            }))}
          />
        ))}
    </div>
  );
}
