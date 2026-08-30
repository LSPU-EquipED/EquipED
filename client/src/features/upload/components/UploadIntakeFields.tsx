import { Input } from '@/shared/components/Input';

interface UploadIntakeFieldsProps {
  title: string;
  setTitle: (val: string) => void;
}

export function UploadIntakeFields({ title, setTitle }: UploadIntakeFieldsProps) {
  return (
    <div className="max-w-2xl">
      <Input
        id="document-title"
        label="Document title"
        type="text"
        value={title}
        onChange={(event) => setTitle(event.target.value)}
        placeholder="Enter the official Self-Learning Module title"
        required
      />
    </div>
  );
}
