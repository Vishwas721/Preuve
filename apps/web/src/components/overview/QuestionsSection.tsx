"use client";

import { CheckCircle2, MoreHorizontal, Plus } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";

import { ClaimList } from "@/components/dossier/Cite";
import { useDossier } from "@/components/dossier/DossierProvider";
import { EmptyState, SectionHeading } from "@/components/dossier/layout";
import { Provenance, Stamp } from "@/components/dossier/marks";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api, type Finding, type Priority, type Unknown, type UnknownCategory } from "@/lib/api";
import { cn } from "@/lib/utils";

const CATEGORIES: Record<UnknownCategory, string> = {
  frequency: "Frequency",
  cost: "Cost",
  current_solution: "Current solution",
  buyer: "Buyer",
  budget: "Budget",
  alternatives: "Alternatives",
  urgency: "Urgency",
  other: "Other",
};
const PRIORITY_RANK: Record<Priority, number> = { high: 0, medium: 1, low: 2 };

function PriorityMark({ priority }: { priority: Priority }) {
  return (
    <span className="inline-flex items-center gap-1 font-mono text-[10px] uppercase tracking-[0.12em]">
      <span aria-hidden className="flex gap-[2px]">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className={cn(
              "h-2.5 w-[3px] rounded-[1px]",
              i <= 2 - PRIORITY_RANK[priority] ? "bg-foreground" : "bg-viz-track",
            )}
          />
        ))}
      </span>
      {priority}
    </span>
  );
}

function FindingBlock({ finding }: { finding: Finding }) {
  const stamp =
    finding.status === "answered" ? (
      <Stamp tone="good">Answered by research</Stamp>
    ) : finding.status === "partially_answered" ? (
      <Stamp tone="warning">Partly answered</Stamp>
    ) : (
      <Stamp tone="ink">No evidence found</Stamp>
    );
  return (
    <div className="mt-3 rounded-md border border-dashed bg-background/50 p-3">
      <div className="mb-2">{stamp}</div>
      {finding.summary.length > 0 && <ClaimList claims={finding.summary} />}
    </div>
  );
}

function QuestionRow({ unknown, n, finding }: { unknown: Unknown; n: number; finding?: Finding }) {
  const { id, refresh } = useDossier();
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(unknown.question);
  const answered = unknown.status === "answered";

  async function patch(data: Parameters<typeof api.updateUnknown>[2], message?: string) {
    try {
      await api.updateUnknown(id, unknown.id, data);
      if (message) toast(message);
      setEditing(false);
      await refresh();
    } catch (err) {
      toast.error((err as Error).message);
    }
  }

  return (
    <motion.li
      layout
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0, height: 0 }}
      className="grid grid-cols-[3rem_1fr_auto] gap-x-3 border-b rule py-5 last:border-b-0"
    >
      <span className={cn("pt-0.5 font-mono text-xs text-muted-foreground", answered && "line-through")}>
        Q-{String(n).padStart(2, "0")}
      </span>
      <div className="min-w-0">
        <div className="mb-1.5 flex flex-wrap items-center gap-x-3 gap-y-1">
          <PriorityMark priority={unknown.priority} />
          <span className="eyebrow">{CATEGORIES[unknown.category]}</span>
          <Provenance source={unknown.source} className="py-0" />
          {answered && (
            <span className="inline-flex items-center gap-1 text-xs text-status-good-ink">
              <CheckCircle2 className="size-3.5" aria-hidden /> Marked answered
            </span>
          )}
        </div>
        {editing ? (
          <form
            className="flex gap-2"
            onSubmit={(e: FormEvent) => {
              e.preventDefault();
              patch({ question: text }, "Question updated");
            }}
          >
            <Input autoFocus required value={text} onChange={(e) => setText(e.target.value)} aria-label="Question" />
            <Button type="submit" size="sm">
              Save
            </Button>
            <Button type="button" size="sm" variant="ghost" onClick={() => setEditing(false)}>
              Cancel
            </Button>
          </form>
        ) : (
          <p className={cn("text-[1.02rem] leading-relaxed", answered && "text-muted-foreground")}>{unknown.question}</p>
        )}
        {finding && <FindingBlock finding={finding} />}
      </div>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon-sm" aria-label={`Actions for Q-${n}`}>
            <MoreHorizontal />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onSelect={() => setEditing(true)}>Edit wording</DropdownMenuItem>
          <DropdownMenuSub>
            <DropdownMenuSubTrigger>Priority</DropdownMenuSubTrigger>
            <DropdownMenuSubContent>
              <DropdownMenuRadioGroup
                value={unknown.priority}
                onValueChange={(v) => patch({ priority: v as Priority }, "Priority changed")}
              >
                <DropdownMenuRadioItem value="high">High</DropdownMenuRadioItem>
                <DropdownMenuRadioItem value="medium">Medium</DropdownMenuRadioItem>
                <DropdownMenuRadioItem value="low">Low</DropdownMenuRadioItem>
              </DropdownMenuRadioGroup>
            </DropdownMenuSubContent>
          </DropdownMenuSub>
          <DropdownMenuItem
            onSelect={() => patch({ status: answered ? "open" : "answered" }, answered ? "Reopened" : "Marked answered")}
          >
            {answered ? "Reopen" : "Mark answered"}
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem variant="destructive" onSelect={() => patch({ status: "dropped" }, "Question removed")}>
            Remove
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </motion.li>
  );
}

function AddQuestion() {
  const { id, refresh } = useDossier();
  const [question, setQuestion] = useState("");
  const [category, setCategory] = useState<UnknownCategory>("other");
  const [priority, setPriority] = useState<Priority>("medium");

  async function add(e: FormEvent) {
    e.preventDefault();
    try {
      await api.createUnknown(id, { question, category, priority });
      setQuestion("");
      toast.success("Question added to the docket");
      await refresh();
    } catch (err) {
      toast.error((err as Error).message);
    }
  }

  return (
    <form onSubmit={add} className="flex flex-col gap-2 border-t rule pt-4 sm:flex-row">
      <Input
        required
        aria-label="New question"
        placeholder="Add a question the evidence must answer…"
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        className="flex-1"
      />
      <Select value={category} onValueChange={(v) => setCategory(v as UnknownCategory)}>
        <SelectTrigger aria-label="Category" className="sm:w-40">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {Object.entries(CATEGORIES).map(([v, l]) => (
            <SelectItem key={v} value={v}>
              {l}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Select value={priority} onValueChange={(v) => setPriority(v as Priority)}>
        <SelectTrigger aria-label="Priority" className="sm:w-28">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="high">High</SelectItem>
          <SelectItem value="medium">Medium</SelectItem>
          <SelectItem value="low">Low</SelectItem>
        </SelectContent>
      </Select>
      <Button type="submit">
        <Plus /> Add
      </Button>
    </form>
  );
}

export function QuestionsSection() {
  const { analysis, research } = useDossier();
  const unknowns = [...(analysis?.unknowns ?? [])].sort(
    (a, b) =>
      Number(a.status === "answered") - Number(b.status === "answered") ||
      PRIORITY_RANK[a.priority] - PRIORITY_RANK[b.priority],
  );
  const findings = Object.fromEntries((research?.findings ?? []).map((f) => [f.unknown_id, f]));

  return (
    <section aria-labelledby="questions-title" className="space-y-4">
      <SectionHeading
        index="02"
        title={<span id="questions-title">Open questions</span>}
        kicker="The research plan. Each question needs evidence — or a customer — before you build."
      />
      <div className="sheet px-5 py-1">
        {unknowns.length === 0 ? (
          <div className="py-5">
            <EmptyState title="No questions yet.">They appear after analysis, or add your own below.</EmptyState>
          </div>
        ) : (
          <ul>
            <AnimatePresence initial={false}>
              {unknowns.map((u, i) => (
                <QuestionRow key={u.id} unknown={u} n={i + 1} finding={findings[u.id]} />
              ))}
            </AnimatePresence>
          </ul>
        )}
        <div className="pb-5">
          <AddQuestion />
        </div>
      </div>
    </section>
  );
}
