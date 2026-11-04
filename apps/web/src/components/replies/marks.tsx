// Reply vocabulary: recommended-action stamps, sentiment marks and verbatim highlights.
// Icon + label everywhere, so colour is never the only signal.

import { CalendarCheck, CircleSlash, Frown, Meh, MessageCircleQuestion, Smile, Undo2 } from "lucide-react";
import type { ReactNode } from "react";

import { Stamp } from "@/components/dossier/marks";
import type { ResponseClassification } from "@/lib/api";
import { cn } from "@/lib/utils";

type Action = ResponseClassification["recommended_action"]["value"];

const ACTION: Record<Action, { label: string; tone: "good" | "warning" | "ink"; icon: typeof Smile }> = {
  interview: { label: "Interview", tone: "good", icon: CalendarCheck },
  follow_up: { label: "Follow up", tone: "ink", icon: MessageCircleQuestion },
  close: { label: "Close", tone: "ink", icon: CircleSlash },
  none: { label: "No action", tone: "ink", icon: CircleSlash },
};

export function ActionStamp({ action, optOut }: { action?: Action; optOut?: boolean }) {
  if (optOut)
    return (
      <Stamp tone="warning" className="text-status-critical">
        <Undo2 className="size-3" aria-hidden /> Opted out
      </Stamp>
    );
  if (!action) return null;
  const a = ACTION[action];
  const Icon = a.icon;
  return (
    <Stamp tone={a.tone}>
      <Icon className="size-3" aria-hidden /> {a.label}
    </Stamp>
  );
}

const SENTIMENT = {
  positive: { label: "Positive", icon: Smile, cls: "text-viz-supports" },
  neutral: { label: "Neutral", icon: Meh, cls: "text-muted-foreground" },
  negative: { label: "Negative", icon: Frown, cls: "text-viz-contradicts" },
} as const;

export function SentimentMark({ sentiment }: { sentiment: keyof typeof SENTIMENT }) {
  const s = SENTIMENT[sentiment];
  const Icon = s.icon;
  return (
    <span className={cn("inline-flex items-center gap-1 text-xs", s.cls)}>
      <Icon className="size-3.5" aria-hidden />
      <span className="text-foreground">{s.label}</span>
    </span>
  );
}

/** The customer's text with the quoted spans highlighted (exact matches only). */
export function Highlighted({ text, quotes }: { text: string; quotes: string[] }) {
  const spans: [number, number][] = [];
  for (const q of quotes) {
    const needle = q.trim();
    if (needle.length < 4) continue;
    const at = text.toLowerCase().indexOf(needle.toLowerCase());
    if (at >= 0) spans.push([at, at + needle.length]);
  }
  spans.sort((a, b) => a[0] - b[0]);
  const parts: ReactNode[] = [];
  let pos = 0;
  for (const [start, end] of spans) {
    if (start < pos) continue; // overlapping: keep the first
    if (start > pos) parts.push(text.slice(pos, start));
    parts.push(
      <mark key={start} className="mark bg-transparent text-inherit">
        {text.slice(start, end)}
      </mark>,
    );
    pos = end;
  }
  parts.push(text.slice(pos));
  return <>{parts}</>;
}

export const SIGNAL_LABELS: [keyof Omit<ResponseClassification, "sentiment" | "recommended_action">, string][] = [
  ["problem_confirmed", "Problem confirmed"],
  ["pain", "Pain"],
  ["frequency", "Frequency"],
  ["current_solution", "Current solution"],
  ["time_or_cost", "Time or cost"],
  ["severity", "Severity"],
  ["solution_satisfaction", "Happy with current solution"],
  ["interest", "Interest"],
  ["willingness_to_pay", "Willingness to pay"],
];
