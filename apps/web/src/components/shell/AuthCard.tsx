import type { ReactNode } from "react";

/** The paper card used by setup, sign-in and invitation pages. */
export function AuthCard({
  eyebrow,
  title,
  kicker,
  children,
}: {
  eyebrow: string;
  title: ReactNode;
  kicker?: ReactNode;
  children: ReactNode;
}) {
  return (
    <main className="mx-auto flex w-full max-w-md flex-col px-4 py-16 sm:py-24">
      <div className="sheet p-6 sm:p-8">
        <p className="eyebrow">{eyebrow}</p>
        <h1 className="mt-2 font-display text-4xl leading-tight">{title}</h1>
        {kicker && <p className="mt-2 text-sm text-muted-foreground">{kicker}</p>}
        <div className="mt-6">{children}</div>
      </div>
    </main>
  );
}

export function FormError({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <p role="alert" className="rounded-md border border-status-critical/40 bg-status-critical/5 px-3 py-2 text-sm">
      {message}
    </p>
  );
}
