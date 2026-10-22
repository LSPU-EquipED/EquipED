import { Link } from "@tanstack/react-router";
import { Button, Dropdown, type DropdownOption } from "@equiped/ui";
import type { ClientDocument } from "@equiped/types";
import curriculumIllustration from "../../../../assets/illustrations/curriculum-check.svg";

interface AlignmentCheckControlsProps {
  documentId: string;
  courseId: string;
  pickerDocuments: ClientDocument[];
  selectedDocument: ClientDocument | null;
  selectedEligibility: { eligible: boolean; message: string | null };
  courseOptions: DropdownOption[];
  documentsLoading: boolean;
  coursesLoading: boolean;
  documentsError: string | null;
  coursesError: string | null;
  canRunCheck: boolean;
  isPending: boolean;
  onDocumentChange: (documentId: string) => void;
  onCourseChange: (courseId: string) => void;
  onRetryDocuments: () => void;
  onRetryCourses: () => void;
  onRun: () => void;
}

export function AlignmentCheckControls({
  documentId,
  courseId,
  pickerDocuments,
  selectedDocument,
  selectedEligibility,
  courseOptions,
  documentsLoading,
  coursesLoading,
  documentsError,
  coursesError,
  canRunCheck,
  isPending,
  onDocumentChange,
  onCourseChange,
  onRetryDocuments,
  onRetryCourses,
  onRun,
}: AlignmentCheckControlsProps) {
  const documentOptions: DropdownOption[] = [
    {
      value: "",
      label: documentsLoading
        ? "Loading modules…"
        : documentsError
          ? "Modules unavailable"
          : pickerDocuments.length === 0
            ? "No eligible modules"
            : "Select a module…",
    },
    ...pickerDocuments.map((doc) => ({
      value: doc.documentId,
      label: doc.title,
    })),
  ];
  if (documentId && !selectedEligibility.eligible && selectedDocument) {
    documentOptions.push({
      value: selectedDocument.documentId,
      label: selectedDocument.title,
      disabled: true,
    });
  }
  const noModules =
    !documentsLoading && !documentsError && pickerDocuments.length === 0;
  const noCourses =
    !coursesLoading && !coursesError && courseOptions.length === 0;

  return (
    <section
      aria-labelledby="curriculum-setup-heading"
      className="rounded-md border border-border bg-surface"
    >
      <div className="flex items-center justify-between gap-6 px-5 py-5 sm:px-6 sm:py-6">
        <div className="min-w-0">
          <h2
            id="curriculum-setup-heading"
            className="text-lg font-semibold text-text"
          >
            Set up a curriculum check
          </h2>
          <p className="mt-1.5 max-w-prose text-sm leading-relaxed text-text-muted">
            Compare a module with the objectives mapped to its course.
          </p>
        </div>
        <img
          src={curriculumIllustration}
          alt=""
          className="hidden size-16 shrink-0 sm:block"
        />
      </div>
      <div className="border-t border-border bg-surface-subtle/40 px-5 py-5 sm:px-6">
        <div className="grid items-start gap-4 sm:grid-cols-2 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]">
          <div className="min-w-0">
            <Dropdown
              id="curriculum-doc-select"
              error={documentsError ?? undefined}
              label="Module"
              value={documentId}
              onChange={onDocumentChange}
              options={documentOptions}
              size="md"
              disabled={
                isPending ||
                documentsLoading ||
                Boolean(documentsError) ||
                noModules
              }
              className="w-full"
              menuClassName="w-full"
              hint={
                noModules
                  ? "No processed BSCS or BSInfoTech SLMs available."
                  : "Processed BSCS and BSInfoTech SLMs only."
              }
            />
            {documentsError && (
              <div className="mt-1 text-xs text-destructive">
                <button
                  type="button"
                  onClick={onRetryDocuments}
                  className="mt-1 min-h-8 font-medium underline focus-visible:outline-2 focus-visible:outline-ring"
                >
                  Retry modules
                </button>
              </div>
            )}
            {noModules && (
              <Link
                to="/documents"
                className="mt-1 inline-flex min-h-8 items-center text-xs font-medium text-primary hover:underline focus-visible:outline-2 focus-visible:outline-ring"
              >
                Open Module library
              </Link>
            )}
          </div>
          <div className="min-w-0">
            <Dropdown
              id="curriculum-course-dropdown"
              error={coursesError ?? undefined}
              label="Target course"
              value={courseId}
              onChange={onCourseChange}
              options={courseOptions}
              placeholder={
                coursesLoading ? "Loading courses…" : "Select a course…"
              }
              size="md"
              disabled={
                coursesLoading ||
                isPending ||
                Boolean(coursesError) ||
                noCourses
              }
              className="w-full"
              menuClassName="w-full"
              hint={
                noCourses
                  ? "No courses available for this program. Contact your administrator."
                  : undefined
              }
            />
            {coursesError && (
              <div className="mt-1 text-xs text-destructive">
                <button
                  type="button"
                  onClick={onRetryCourses}
                  className="mt-1 min-h-8 font-medium underline focus-visible:outline-2 focus-visible:outline-ring"
                >
                  Retry courses
                </button>
              </div>
            )}
          </div>
          <Button
            type="button"
            onClick={onRun}
            disabled={
              !canRunCheck ||
              isPending ||
              documentsLoading ||
              coursesLoading ||
              Boolean(documentsError || coursesError)
            }
            isLoading={isPending}
            className="w-full whitespace-nowrap sm:col-span-2 sm:w-auto sm:justify-self-end lg:col-span-1 lg:mt-5.5"
          >
            {isPending ? "Checking…" : "Run check"}
          </Button>
        </div>
        {documentId && selectedDocument && !selectedEligibility.eligible && (
          <p role="status" className="mt-3 text-sm text-warning">
            {selectedEligibility.message}
          </p>
        )}
      </div>
    </section>
  );
}
