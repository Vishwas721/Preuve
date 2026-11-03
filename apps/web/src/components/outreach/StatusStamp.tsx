// Message status as a rubber stamp: icon + label, never colour alone.

import { Ban, Check, CircleSlash, Loader2, MailCheck, MailX, PenLine } from "lucide-react";

import { Stamp } from "@/components/dossier/marks";
import type { MessageStatus } from "@/lib/api";
import { cn } from "@/lib/utils";

const STATUS: Record<
  MessageStatus,
  { label: string; tone: "good" | "warning" | "ink"; icon: typeof Check; critical?: boolean }
> = {
  drafting: { label: "Drafting", tone: "ink", icon: Loader2 },
  draft: { label: "Draft", tone: "ink", icon: PenLine },
  approved: { label: "Approved", tone: "good", icon: Check },
  rejected: { label: "Rejected", tone: "ink", icon: CircleSlash },
  sent: { label: "Sent", tone: "good", icon: MailCheck },
  bounced: { label: "Bounced", tone: "warning", icon: MailX, critical: true },
  blocked: { label: "Blocked", tone: "warning", icon: Ban, critical: true },
};

export const STATUS_LABEL = Object.fromEntries(
  Object.entries(STATUS).map(([k, v]) => [k, v.label]),
) as Record<MessageStatus, string>;

export function StatusStamp({ status, className }: { status: MessageStatus; className?: string }) {
  const s = STATUS[status];
  const Icon = s.icon;
  return (
    <Stamp tone={s.tone} className={cn(s.critical && "text-status-critical", className)}>
      <Icon className={cn("size-3", status === "drafting" && "animate-spin")} aria-hidden />
      {s.label}
    </Stamp>
  );
}
