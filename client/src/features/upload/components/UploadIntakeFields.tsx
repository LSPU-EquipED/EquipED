type ProgramId = 'bsit' | 'bscs' | 'bsis';

interface UploadIntakeFieldsProps {
  title: string;
  setTitle: (val: string) => void;
  program: ProgramId;
  handleProgramChange: (val: string) => void;
  subject: string;
  setSubject: (val: string) => void;
  programLabels: Record<ProgramId, string>;
  subjectsByProgram: Record<ProgramId, string[]>;
}

export function UploadIntakeFields({
  title,
  setTitle,
  program,
  handleProgramChange,
  subject,
  setSubject,
  programLabels,
  subjectsByProgram,
}: UploadIntakeFieldsProps) {
  return (
    <div className="space-y-4 max-w-2xl">
      {/* Title Field */}
      <div className="space-y-1.5">
        <label
          htmlFor="document-title"
          className="text-xs font-medium uppercase tracking-wide text-slate-500 block"
        >
          Document Title
        </label>
        <input
          id="document-title"
          type="text"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="Enter the official Self-Learning Module title"
          className="w-full h-10 px-3 border border-slate-200 bg-white rounded-sm text-sm focus:outline-none focus:ring-2 focus:ring-[#1b3b87] placeholder:text-slate-600 font-semibold text-slate-800 transition-shadow"
          required
        />
      </div>

      {/* Grid for Program and Subject */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Program Field */}
        <div className="space-y-1.5">
          <label
            htmlFor="document-program"
            className="text-xs font-medium uppercase tracking-wide text-slate-500 block"
          >
            Academic Program
          </label>
          <select
            id="document-program"
            value={program}
            onChange={(e) => handleProgramChange(e.target.value)}
            className="w-full h-10 border border-slate-200 bg-white px-3 focus:outline-none focus:ring-2 focus:ring-[#1b3b87] rounded-sm text-sm font-semibold text-slate-800 cursor-pointer transition-shadow"
          >
            {(Object.keys(programLabels) as ProgramId[]).map((programId) => (
              <option key={programId} value={programId}>
                {programLabels[programId]}
              </option>
            ))}
          </select>
        </div>

        {/* Subject Field */}
        <div className="space-y-1.5">
          <label
            htmlFor="document-subject"
            className="text-xs font-medium uppercase tracking-wide text-slate-500 block"
          >
            Subject/Course
          </label>
          <select
            id="document-subject"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            className="w-full h-10 border border-slate-200 bg-white px-3 focus:outline-none focus:ring-2 focus:ring-[#1b3b87] rounded-sm text-sm font-semibold text-slate-800 cursor-pointer transition-shadow"
          >
            {subjectsByProgram[program].map((subjectName) => (
              <option key={subjectName} value={subjectName}>
                {subjectName}
              </option>
            ))}
          </select>
        </div>
      </div>
    </div>
  );
}
