import { MessageSquareText } from 'lucide-react';

type FeedbackPanelProps = {
  readonly comments?: readonly string[];
};

const fallbackComments = ['Agent feedback will appear here after persisted Layer 3 outputs are available for this job.'];

export function FeedbackPanel({ comments = fallbackComments }: FeedbackPanelProps) {
  return (
    <div className="grid gap-2">
      {comments.map((comment) => (
        <div key={comment} className="flex gap-3 rounded-lg border bg-card p-3 text-sm transition duration-200 hover:bg-muted/30">
          <span className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
            <MessageSquareText className="size-4" aria-hidden="true" />
          </span>
          <p className="m-0 leading-6 text-muted-foreground">{comment}</p>
        </div>
      ))}
    </div>
  );
}
