export function AuthFormHeader({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <header className="auth-form-header">
      <h1>{title}</h1>
      <p>{description}</p>
    </header>
  );
}
