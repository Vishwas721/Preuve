"use client";

import { ArrowRight, FilePlus2 } from "lucide-react";
import { motion } from "motion/react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { CaseFolder } from "@/components/board/CaseFolder";
import { EmptyState, ErrorState } from "@/components/dossier/layout";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type PortfolioItem } from "@/lib/api";
import { cn } from "@/lib/utils";

function Stat({ value, label }: { value: number | string; label: string }) {
  return (
    <div className="border-l rule pl-4">
      <div className="font-display text-4xl leading-none tabular-nums sm:text-5xl">{value}</div>
      <div className="eyebrow mt-2">{label}</div>
    </div>
  );
}

export default function CaseBoard() {
  const [items, setItems] = useState<PortfolioItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [order, setOrder] = useState<"recent" | "score">("recent");

  const load = useCallback(
    () =>
      api.portfolio().then(
        (data) => {
          setError(null);
          setItems(data);
        },
        (e: Error) => setError(e.message),
      ),
    [],
  );
  useEffect(() => {
    load();
  }, [load]);

  const totals = (items ?? []).reduce(
    (acc, i) => ({
      verified: acc.verified + i.evidence.verified,
      prospects: acc.prospects + i.prospects,
      open: acc.open + i.unknowns_open,
    }),
    { verified: 0, prospects: 0, open: 0 },
  );

  return (
    <main className="mx-auto w-full max-w-7xl px-4 pb-24 sm:px-6">
      {/* masthead */}
      <section className="grid gap-10 border-b rule py-12 lg:grid-cols-[1.4fr_1fr] lg:items-end lg:py-16">
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
          <p className="eyebrow mb-4">The case board</p>
          <h1 className="font-display text-5xl leading-[0.95] tracking-tight sm:text-7xl">
            Every idea is a case.
            <br />
            <span className="italic text-ink-soft">
              Build only what the <span className="mark not-italic text-foreground">evidence</span> proves.
            </span>
          </h1>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Button asChild size="lg" className="h-10 px-4">
              <Link href="/ideas/new">
                <FilePlus2 /> Open a new case
              </Link>
            </Button>
            <span className="text-sm text-muted-foreground">
              or press <kbd className="rounded border bg-paper px-1.5 font-mono text-xs">⌘K</kbd> to find one
            </span>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.2, duration: 0.5 }}
          className="grid grid-cols-2 gap-y-8 sm:grid-cols-4 lg:grid-cols-2"
          aria-label="Totals"
        >
          <Stat value={items?.length ?? "—"} label="Open cases" />
          <Stat value={items ? totals.verified : "—"} label="Verified exhibits" />
          <Stat value={items ? totals.prospects : "—"} label="Prospects" />
          <Stat value={items ? totals.open : "—"} label="Open questions" />
        </motion.div>
      </section>

      {/* folders */}
      <section className="pt-10" aria-labelledby="cases-heading">
        <div className="mb-6 flex flex-wrap items-baseline justify-between gap-3">
          <h2 id="cases-heading" className="eyebrow">
            Cases · {order === "score" ? "highest validation score first" : "most recent activity first"}
          </h2>
          <div className="flex gap-1 text-xs" role="group" aria-label="Sort cases">
            {(["recent", "score"] as const).map((o) => (
              <button
                key={o}
                aria-pressed={order === o}
                onClick={() => setOrder(o)}
                className={cn(
                  "rounded-md px-2.5 py-1 transition-colors hover:bg-accent",
                  order === o ? "bg-accent font-medium" : "text-muted-foreground",
                )}
              >
                {o === "recent" ? "Recent" : "Score"}
              </button>
            ))}
          </div>
        </div>

        {error && <ErrorState message={`Couldn't load your cases: ${error}`} onRetry={load} />}

        {!error && items === null && (
          <ul className="grid gap-x-6 gap-y-10 md:grid-cols-2 xl:grid-cols-3" aria-busy="true">
            {[0, 1, 2].map((i) => (
              <li key={i} className="list-none">
                <Skeleton className="h-6 w-40 rounded-b-none" />
                <Skeleton className="h-72 rounded-tl-none" />
              </li>
            ))}
          </ul>
        )}

        {items && items.length === 0 && (
          <EmptyState
            title="No open cases."
            action={
              <Button asChild>
                <Link href="/ideas/new">
                  Open your first case <ArrowRight />
                </Link>
              </Button>
            }
          >
            Describe an idea in your own words. Preuve turns it into testable assumptions, then
            evidence decides.
          </EmptyState>
        )}

        {items && items.length > 0 && (
          <ul className="grid gap-x-6 gap-y-10 md:grid-cols-2 xl:grid-cols-3">
            {(order === "score"
              ? [...items].sort((a, b) => (b.validation?.score ?? -1) - (a.validation?.score ?? -1))
              : items
            ).map((item, i) => (
              <CaseFolder key={item.id} item={item} index={i} caseNo={items.indexOf(item) + 1} />
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
