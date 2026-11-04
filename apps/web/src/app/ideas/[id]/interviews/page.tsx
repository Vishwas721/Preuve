"use client";

import { CalendarPlus } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { useDossier } from "@/components/dossier/DossierProvider";
import { EmptyState, ErrorState, SectionHeading, SheetSkeleton } from "@/components/dossier/layout";
import { InterviewDesk } from "@/components/interviews/InterviewDesk";
import { NewInterviewSheet } from "@/components/interviews/NewInterviewSheet";
import { WtpLedger } from "@/components/interviews/WtpLedger";
import { Button } from "@/components/ui/button";
import { api, type InterviewSummary } from "@/lib/api";
import { shortDate } from "@/lib/format";
import { cn } from "@/lib/utils";

const STATUS = { planned: "Planned", done: "Done", cancelled: "Cancelled" } as const;

export default function InterviewsPage() {
  const { id, analysis } = useDossier();
  const params = useSearchParams();
  const [rows, setRows] = useState<InterviewSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [openId, setOpenId] = useState<string | null>(params.get("i"));
  const [creating, setCreating] = useState(false);
  const [ledgerVersion, setLedgerVersion] = useState(0);

  const load = useCallback(
    () =>
      api.listInterviews(id).then(
        (r) => {
          setRows(r);
          setOpenId((cur) => (cur && r.some((x) => x.id === cur) ? cur : (r[0]?.id ?? null)));
          setError(null);
        },
        (e: Error) => setError(e.message),
      ),
    [id],
  );
  useEffect(() => {
    load();
  }, [load]);

  const onChanged = useCallback(() => {
    load();
    setLedgerVersion((v) => v + 1); // extraction may have proposed a WTP record
  }, [load]);

  if (error && !rows) return <ErrorState message={error} onRetry={load} />;
  if (!rows) return <SheetSkeleton lines={6} />;

  const open = analysis?.unknowns.filter((u) => u.status === "open").length ?? 0;

  return (
    <div className="space-y-10">
      <div className="space-y-6">
        <SectionHeading
          title="Interviews"
          kicker={`Learn how they work today. ${open} open ${open === 1 ? "question" : "questions"} to cover.`}
        >
          <Button size="sm" onClick={() => setCreating(true)}>
            <CalendarPlus /> Plan an interview
          </Button>
        </SectionHeading>

        {rows.length === 0 ? (
          <EmptyState
            title="No interviews yet."
            action={
              <Button onClick={() => setCreating(true)}>
                <CalendarPlus /> Plan an interview
              </Button>
            }
          >
            A reply recommending an interview is a good start. The guide is written from the open unknowns.
          </EmptyState>
        ) : (
          <div className="grid grid-cols-[minmax(0,1fr)] gap-5 xl:grid-cols-[16rem_minmax(0,1fr)]">
            <ol className="sheet divide-y divide-border self-start overflow-hidden" aria-label="Interviews">
              {rows.map((r) => (
                <li key={r.id}>
                  <button
                    onClick={() => setOpenId(r.id)}
                    aria-current={r.id === openId}
                    className={cn(
                      "flex w-full flex-col gap-0.5 px-4 py-3 text-left transition-colors hover:bg-accent/50 focus-visible:bg-accent focus-visible:outline-none",
                      r.id === openId && "bg-accent/60",
                    )}
                  >
                    <span className="truncate font-medium">{r.interviewee_name}</span>
                    <span className="truncate text-xs text-muted-foreground">
                      {r.company_name || r.interviewee_role || "—"}
                    </span>
                    <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                      {STATUS[r.status]}
                      {r.scheduled_at ? ` · ${shortDate(r.scheduled_at)}` : ""}
                      {r.extraction_state === "done" ? " · extracted" : ""}
                    </span>
                  </button>
                </li>
              ))}
            </ol>
            {openId && <InterviewDesk key={openId} interviewId={openId} onChanged={onChanged} />}
          </div>
        )}
      </div>

      <WtpLedger version={ledgerVersion} />

      <NewInterviewSheet
        open={creating}
        onOpenChange={setCreating}
        onCreated={(iv) => {
          setCreating(false);
          setOpenId(iv.id);
          load();
        }}
      />
    </div>
  );
}
