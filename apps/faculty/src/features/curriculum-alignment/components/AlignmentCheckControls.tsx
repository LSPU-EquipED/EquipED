import { Button, Dropdown, type DropdownOption, Select } from '@equiped/ui';
import type { ClientDocument } from '@equiped/types';

interface AlignmentCheckControlsProps {
  documentId: string;
  courseId: string;
  pickerDocuments: ClientDocument[];
  selectedDocument: ClientDocument | null;
  selectedEligibility: { eligible: boolean; message: string | null };
  courseOptions: DropdownOption[];
  coursesLoading: boolean;
  canRunCheck: boolean;
  isPending: boolean;
  isChecking?: boolean;
  onDocumentChange: (documentId: string) => void;
  onCourseChange: (courseId: string) => void;
  onRun: () => void;
}

export function AlignmentCheckControls({
  documentId,
  courseId,
  pickerDocuments,
  selectedDocument,
  selectedEligibility,
  courseOptions,
  coursesLoading,
  canRunCheck,
  isPending,
  isChecking = isPending,
  onDocumentChange,
  onCourseChange,
  onRun,
}: AlignmentCheckControlsProps) {
  return (
    <div className="rounded-md border border-border bg-surface p-4 sm:p-5 shadow-none">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] items-end">
        <div className="min-w-0">
          <Select
            id="curriculum-doc-select"
            label="Course Module (SLM)"
            value={documentId}
            onChange={(e) => onDocumentChange(e.target.value)}
            size="sm"
            disabled={isChecking}
            className="h-8.5 w-full text-xs font-semibold cursor-pointer"
          >
            <option value="">Select a document...</option>
            {pickerDocuments.map((doc) => (
              <option key={doc.documentId} value={doc.documentId}>
                {doc.title}
              </option>
            ))}

            {documentId && !selectedEligibility.eligible && selectedDocument ? (
              <option value={selectedDocument.documentId} disabled>
                {selectedDocument.title} (not eligible)
              </option>
            ) : null}
          </Select>
        </div>

        <div className="min-w-0">
          <Dropdown
            id="curriculum-course-dropdown"
            label="Target Course"
            value={courseId}
            onChange={onCourseChange}
            options={courseOptions}
            placeholder="Select a course..."
            size="sm"
            disabled={coursesLoading || isChecking}
            className="h-8.5 w-full text-xs font-semibold"
          />
        </div>

        <Button
          type="button"
          variant="primary"
          size="sm"
          onClick={onRun}
          disabled={!canRunCheck || isPending || isChecking}
          isLoading={isPending}
          className="h-8.5 px-4 font-semibold text-xs whitespace-nowrap"
        >
          Run Alignment Check
        </Button>
      </div>
    </div>
  );
}
