type FlagListProps = {
  readonly flags?: readonly string[];
};

const fallbackFlags = ['Contextual highlights will appear here once evaluation data exists.'];

export function FlagList({ flags = fallbackFlags }: FlagListProps) {
  return (
    <section className="rounded-lg border bg-card p-4 shadow-sm">
      <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Flags</div>
      <div className="mt-3 grid gap-2">
        {flags.map((flag, index) => (
          <p key={`${flag}-${index}`} className="m-0 rounded-md border bg-background px-3 py-2 text-sm leading-6 text-muted-foreground">
            {flag}
          </p>
        ))}
      </div>
    </section>
  );
}
