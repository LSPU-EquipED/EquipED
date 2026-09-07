import { Input } from '@/shared/components/Input';
import { ProgramSelector } from '@/shared/components/ProgramSelector';
import { LSPU_SCC_COLLEGE_PROGRAMS } from '@/shared/constants/programs';

interface UploadIntakeFieldsProps {
  title: string;
  setTitle: (val: string) => void;
  program?: string;
  setProgram?: (val: string) => void;
}

export function UploadIntakeFields({
  title,
  setTitle,
  program = '',
  setProgram,
}: UploadIntakeFieldsProps) {
  return (
    <div className="max-w-2xl space-y-4">
      <Input
        id="document-title"
        label="Document title"
        type="text"
        value={title}
        onChange={(event) => setTitle(event.target.value)}
        placeholder="Enter the official Self-Learning Module title"
        required
      />
      {setProgram && (
        <ProgramSelector
          value={program}
          onChange={setProgram}
          groups={LSPU_SCC_COLLEGE_PROGRAMS}
          label="College Academic Program"
          placeholder="Select degree program (BSCS or BSInfoTech)"
          hint="Selecting the academic program associates the SLM with its curriculum."
        />
      )}
    </div>
  );
}
