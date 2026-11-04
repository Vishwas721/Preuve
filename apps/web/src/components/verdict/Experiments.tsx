"use client";

import { FlaskConical, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { useDossier } from "@/components/dossier/DossierProvider";
import { EmptyState, ErrorState, SectionHeading, SheetSkeleton } from "@/components/dossier/layout";
import { Stamp } from "@/components/dossier/marks";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ExperimentSheet } from "@/components/verdict/ExperimentSheet";
import { api, type CohortResult, type Experiment } from "@/lib/api";
import { shortDate } from "@/lib/format";

const ROWS: [keyof CohortResult, string][] = [
  ["sent", "Sent"],
  ["replies", "Replies"],
  ["positive", "Positive"],
  ["problem_confirmed", "Problem confirmed"],
  ["interview_recommended", "Interview recommended"],
  ["interviews_done", "Interviews done"],
];

const rate = (r: CohortResult) => (r.reply_rate === null ? "—" : `${Math.round(r.reply_rate * 100)}%`);

function ResultTable({ e }: { e: Experiment }) {
  const cols = [e.result.a, ...(e.result.b ? [e.result.b] : [])];
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[18rem] text-sm">
        <thead>
          <tr className="border-b rule text-left">
            <th className="py-1.5 pr-3 font-normal text-muted-foreground">Cohort</th>
            {cols.map((c, i) => (
              <th key={i} className="py-1.5 pr-3 text-right font-medium">
                {c.label}
                {c.small_sample && (
                  <span className="ml-1 font-mono text-[9px] uppercase text-status-warning-ink" title="Fewer than 10 sent">
                    small
                  </span>
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="font-mono tabular-nums">
          {ROWS.map(([key, label]) => (
            <tr key={key} className="border-b border-border/50">
              <td className="py-1.5 pr-3 font-sans text-muted-foreground">{label}</td>
              {cols.map((c, i) => (
                <td key={i} className="py-1.5 pr-3 text-right">
                  {String(c[key])}
                </td>
              ))}
            </tr>
          ))}
          <tr>
            <td className="py-1.5 pr-3 font-sans text-muted-foreground">Reply rate</td>
            {cols.map((c, i) => (
              <td key={i} className="py-1.5 pr-3 text-right">
                {rate(c)}
              </td>
            ))}
          </tr>
        </tbody>
      </table>
    </div>
  );
}

function ExperimentCard({ e, onChanged }: { e: Experiment; onChanged: () => void }) {
  const { id } = useDossier();
  const [conclusion, setConclusion] = useState(e.conclusion);
  const [busy, setBusy] = useState(false);
  const concluded = e.status === "concluded";

  async function act(patch: Parameters<typeof api.updateExperiment>[2]) {
    setBusy(true);
    try {
      await api.updateExperiment(id, e.id, patch);
      onChanged();
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    setBusy(true);
    try {
      await api.deleteExperiment(id, e.id);
      onChanged();
    } catch (err) {
      toast.error((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <li className="sheet space-y-4 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
            Started {shortDate(e.created_at)}
            {e.concluded_at ? ` · concluded ${shortDate(e.concluded_at)}` : ""}
          </p>
          <p className="mt-1 font-display text-xl leading-snug">{e.hypothesis}</p>
        </div>
        <div className="flex items-center gap-2">
          <Stamp tone={concluded ? "good" : "ink"}>{concluded ? "Concluded" : "Running"}</Stamp>
          <Button variant="ghost" size="icon" aria-label="Delete experiment" disabled={busy} onClick={remove}>
            <Trash2 />
          </Button>
        </div>
      </div>

      <ResultTable e={e} />
      {e.result.comparison.length > 0 && (
        <ul className="space-y-1 text-xs text-muted-foreground">
          {e.result.comparison.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      )}

      <div className="space-y-2 border-t rule pt-4">
        <p className="eyebrow">Conclusion (yours)</p>
        {concluded ? (
          <>
            <p className="text-sm">{e.conclusion}</p>
            <p className="font-mono text-[10px] text-muted-foreground">
              Results frozen when concluded.{" "}
              <button className="underline underline-offset-4" disabled={busy} onClick={() => act({ status: "running" })}>
                Reopen
              </button>
            </p>
          </>
        ) : (
          <div className="flex flex-col gap-2 sm:flex-row sm:items-start">
            <Textarea
              aria-label="Conclusion"
              placeholder="What do these counts tell you? e.g. Promising, update the ICP."
              value={conclusion}
              onChange={(ev) => setConclusion(ev.target.value)}
              className="min-h-16 flex-1"
            />
            <Button
              size="sm"
              variant="outline"
              disabled={busy || !conclusion.trim()}
              onClick={() => act({ conclusion, status: "concluded" })}
            >
              Conclude
            </Button>
          </div>
        )}
      </div>
    </li>
  );
}

export function Experiments() {
  const { id } = useDossier();
  const [rows, setRows] = useState<Experiment[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  const load = useCallback(
    () =>
      api.listExperiments(id).then(
        (r) => {
          setRows(r);
          setError(null);
        },
        (e: Error) => setError(e.message),
      ),
    [id],
  );
  useEffect(() => {
    load();
  }, [load]);

  return (
    <section className="space-y-5" aria-labelledby="experiments-title">
      <SectionHeading
        title={<span id="experiments-title">Experiments</span>}
        kicker="Test one hypothesis at a time on cohorts of the outreach you've sent (PRD §28)."
      >
        <Button size="sm" variant="outline" onClick={() => setCreating(true)}>
          <FlaskConical /> New experiment
        </Button>
      </SectionHeading>
      {error && !rows ? (
        <ErrorState message={error} onRetry={load} />
      ) : !rows ? (
        <SheetSkeleton lines={3} />
      ) : rows.length === 0 ? (
        <EmptyState title="No experiments yet.">
          Compare cohorts, e.g. operations directors vs project managers, using replies you already have.
        </EmptyState>
      ) : (
        <ul className="space-y-4">
          {rows.map((e) => (
            <ExperimentCard key={`${e.id}-${e.status}`} e={e} onChanged={load} />
          ))}
        </ul>
      )}
      <ExperimentSheet
        open={creating}
        onOpenChange={setCreating}
        onCreated={() => {
          setCreating(false);
          load();
        }}
      />
    </section>
  );
}
