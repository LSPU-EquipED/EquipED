interface UploadIntakeFieldsProps {
  title: string;
  setTitle: (val: string) => void;
}

export function UploadIntakeFields({ title, setTitle }: UploadIntakeFieldsProps) {
  return (
    <div className="space-y-1.5 max-w-2xl">
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
        className="w-full h-10 px-3 border border-slate-200 bg-white rounded-sm text-sm focus:outline-none focus:ring-2 focus:ring-[#1b3b87] placeholder:text-slate-600 font-semibold text-slate-800"
        required
      />
    </div>
  );
}
