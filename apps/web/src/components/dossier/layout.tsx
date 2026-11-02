// Section headings and the empty / error / loading states every view uses.

import { FolderSearch, TriangleAlert } from "lucide-react";
import type { ReactNode } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export function SectionHeading({
  index,
  title,
  kicker,
  children,
  className,
}: {
  index?: string;
  title: ReactNode;
  kicker?: ReactNode;
  children?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-wrap items-end justify-between gap-3 border-b rule pb-3", className)}>
      <div className="min-w-0">
        {index && <p className="eyebrow mb-1">§ {index}</p>}
        <h2 className="font-display text-3xl leading-tight sm:text-[2.1rem]">{title}</h2>
        {kicker && <p className="mt-1 max-w-2xl text-sm text-muted-foreground">{kicker}</p>}
      </div>
      {children && <div className="flex flex-wrap items-center gap-2">{children}</div>}
    </div>
  );
}

export function EmptyState({
  title = "No evidence found.",
  children,
  action,
  className,
}: {
  title?: string;
  children?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center gap-3 rounded-lg border border-dashed px-6 py-10 text-center",
        className,
      )}
    >
      <FolderSearch className="size-7 text-muted-foreground/70" aria-hidden />
      <p className="font-display text-xl">{title}</p>
      {children && <div className="max-w-md text-sm text-muted-foreground">{children}</div>}
      {action}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div
      role="alert"
      className="flex flex-wrap items-center gap-3 rounded-lg border border-status-critical/40 bg-status-critical/5 px-4 py-3 text-sm"
    >
      <TriangleAlert className="size-4 text-status-critical" aria-hidden />
      <span className="flex-1">{message}</span>
      {onRetry && (
        <button onClick={onRetry} className="underline underline-offset-4">
          Try again
        </button>
      )}
    </div>
  );
}

export function SheetSkeleton({ lines = 3, className }: { lines?: number; className?: string }) {
  return (
    <div className={cn("sheet space-y-3 p-5", className)} aria-busy="true" aria-label="Loading">
      <Skeleton className="h-3 w-24" />
      <Skeleton className="h-7 w-2/3" />
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton key={i} className="h-3.5" style={{ width: `${92 - i * 11}%` }} />
      ))}
    </div>
  );
}
