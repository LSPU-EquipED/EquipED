import { Dropdown, ProgramSelector } from '@equiped/ui';
import { LSPU_SCC_COLLEGE_PROGRAMS } from '@equiped/types';
import {
  POLICY_AREA_LABELS,
  POLICY_AREAS,
  type PolicyArea,
} from '@equiped/types';
import type { AdminUploadSourceType } from '../types';

export const sourceTypeLabels: Record<AdminUploadSourceType, string> = {
  syllabus: 'Syllabus',
  curriculum: 'Curriculum',
  policy: 'Policy',
};

export const referenceTypes: AdminUploadSourceType[] = ['syllabus', 'curriculum', 'policy'];

const referenceTypeOptions = referenceTypes.map((type) => ({
  value: type,
  label: sourceTypeLabels[type],
}));

const policyAreaOptions = POLICY_AREAS.map((area) => ({
  value: area,
  label: POLICY_AREA_LABELS[area],
}));

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
    <div className="space-y-5 border-b border-border p-5 sm:p-6">
      <div className="space-y-1">
        <h1 className="text-xl font-semibold leading-tight text-text">
          Add a reference
        </h1>
        <p className="max-w-2xl text-sm leading-relaxed text-text-muted">
          Set the source type and scope before attaching the official document.
        </p>
      </div>
      <div className="space-y-2">
        <Dropdown
          id="ref-source-type"
          label="Reference type"
          value={sourceType}
          onChange={(value) => onSourceTypeChange(value as AdminUploadSourceType)}
          options={referenceTypeOptions}
          size="md"
          required
          className="w-full border-input text-sm"
          containerClassName="w-full"
          menuClassName="w-full"
        />
        <p className="text-xs leading-relaxed text-text-muted">
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
          <Dropdown
            id="ref-policy-area"
            label="Policy area"
            value={policyArea}
            onChange={(value) => onPolicyAreaChange(value as PolicyArea)}
            options={policyAreaOptions}
            size="md"
            required={isPolicyAreaRequired}
            className="w-full border-input text-sm"
            containerClassName="w-full"
            menuClassName="w-full"
          />
          <p className="text-xs leading-relaxed text-text-muted">
            Required for policy references. The area is used to route retrieval during ITSO evaluation.
          </p>
        </div>
      ) : null}
    </div>
  );
}
