import { CaretDown } from '@phosphor-icons/react';
import { ProgramSelector } from '@/shared/components/ProgramSelector';
import { LSPU_SCC_COLLEGE_PROGRAMS } from '@/shared/constants/programs';
import {
  POLICY_AREA_LABELS,
  POLICY_AREAS,
  type PolicyArea,
} from '@/shared/types/documents';
import type { AdminUploadSourceType } from '../types';

export const sourceTypeLabels: Record<AdminUploadSourceType, string> = {
  syllabus: 'Syllabus',
  curriculum: 'Curriculum',
  policy: 'Policy',
};

export const referenceTypes: AdminUploadSourceType[] = ['syllabus', 'curriculum', 'policy'];

interface ReferenceClassificationStepProps {
  sourceType: AdminUploadSourceType;
  onSourceTypeChange: (type: AdminUploadSourceType) => void;
  program: string;
  onProgramChange: (program: string) => void;
  isProgramInvalid: boolean;
  policyArea: PolicyArea;
  onPolicyAreaChange: (area: PolicyArea) => void;
}

export function ReferenceClassificationStep({
  sourceType,
  onSourceTypeChange,
  program,
  onProgramChange,
  isProgramInvalid,
  policyArea,
  onPolicyAreaChange,
}: ReferenceClassificationStepProps) {
  const isCurriculum = sourceType === 'curriculum';
  const isPolicyAreaRequired = sourceType === 'policy';

  return (
    <div className="rounded-md border border-border bg-surface p-6 sm:p-7 space-y-5 shadow-none">
      <div className="space-y-1">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
          Step 1 of 2
        </span>
        <h2 className="text-base font-bold text-text tracking-tight">
          Reference Classification
        </h2>
      </div>
      <div className="space-y-2">
        <label
          htmlFor="ref-source-type"
          className="block text-xs font-semibold text-text"
        >
          Document Type <span className="text-destructive">*</span>
        </label>
        <div className="relative">
          <select
            id="ref-source-type"
            value={sourceType}
            onChange={(e) => onSourceTypeChange(e.target.value as AdminUploadSourceType)}
            className="w-full h-10 appearance-none border border-input bg-surface pl-3 pr-9 rounded-sm text-sm font-semibold text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring cursor-pointer"
          >
            {referenceTypes.map((type) => (
              <option key={type} value={type}>
                {sourceTypeLabels[type]}
              </option>
            ))}
          </select>
          <CaretDown
            className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 size-4 text-text-muted"
            aria-hidden="true"
          />
        </div>
        <p className="text-[11px] text-text-muted">
          {sourceType === 'syllabus' && 'Official course syllabus containing learning outcomes and topic outlines.'}
          {sourceType === 'curriculum' && 'Degree curriculum map binding course outcomes to institutional competencies.'}
          {sourceType === 'policy' && 'University policy manual defining intellectual property and compliance criteria.'}
        </p>
      </div>

      {isCurriculum ? (
        <div className="space-y-2 pt-2">
          <ProgramSelector
            id="ref-program"
            label="Program"
            value={program}
            onChange={onProgramChange}
            groups={LSPU_SCC_COLLEGE_PROGRAMS}
            placeholder="Select a program (BSCS or BSInfoTech)"
            required
            hint="Required for curriculum references. Associated with canonical BSCS or BSInfoTech."
          />
          {isProgramInvalid ? (
            <p
              id="ref-program-error"
              role="alert"
              className="text-xs font-semibold text-destructive mt-1"
            >
              Please select a program for this curriculum document.
            </p>
          ) : null}
        </div>
      ) : null}

      {isPolicyAreaRequired ? (
        <div className="space-y-2 pt-2">
          <label
            htmlFor="ref-policy-area"
            className="block text-xs font-semibold text-text"
          >
            Policy Area <span className="text-destructive">*</span>
          </label>
          <div className="relative">
            <select
              id="ref-policy-area"
              value={policyArea}
              onChange={(e) => onPolicyAreaChange(e.target.value as PolicyArea)}
              className="w-full h-10 appearance-none border border-input bg-surface pl-3 pr-9 rounded-sm text-sm font-semibold text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring cursor-pointer"
              required={isPolicyAreaRequired}
            >
              {POLICY_AREAS.map((area) => (
                <option key={area} value={area}>
                  {POLICY_AREA_LABELS[area]}
                </option>
              ))}
            </select>
            <CaretDown
              className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 size-4 text-text-muted"
              aria-hidden="true"
            />
          </div>
          <p className="text-[11px] text-text-muted">
            Required for policy references. The area is used to route retrieval during ITSO evaluation.
          </p>
        </div>
      ) : null}
    </div>
  );
}
