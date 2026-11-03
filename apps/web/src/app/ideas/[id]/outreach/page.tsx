"use client";

import { Ban, Mail, Pause, Play, Plus, Send, UserPlus } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { useDossier } from "@/components/dossier/DossierProvider";
import { EmptyState, ErrorState, SectionHeading, SheetSkeleton } from "@/components/dossier/layout";
import { CampaignSheet } from "@/components/outreach/CampaignSheet";
import { MessageDesk } from "@/components/outreach/MessageDesk";
import { RecipientsSheet } from "@/components/outreach/RecipientsSheet";
import { StatusStamp } from "@/components/outreach/StatusStamp";
import { SuppressionSheet } from "@/components/outreach/SuppressionSheet";
import { Button } from "@/components/ui/button";
import { api, type Campaign, type MessageSummary, type OutreachSettings } from "@/lib/api";
import { cn } from "@/lib/utils";

const POLL_MS = 2500;

export default function OutreachPage() {
  const { id } = useDossier();
  const [settings, setSettings] = useState<OutreachSettings | null>(null);
  const [campaigns, setCampaigns] = useState<Campaign[] | null>(null);
  const [campaignId, setCampaignId] = useState<string | null>(null);
  const [messages, setMessages] = useState<MessageSummary[] | null>(null);
  const [messageId, setMessageId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sheet, setSheet] = useState<"campaign" | "recipients" | "suppressions" | null>(null);
  // Poll for a while after a send is queued, so the result shows without a reload.
  const [watchUntil, setWatchUntil] = useState(0);

  const campaign = campaigns?.find((c) => c.id === campaignId) ?? null;

  const loadCampaigns = useCallback(
    () =>
      Promise.all([api.listCampaigns(id), api.outreachSettings()]).then(
        ([cs, s]) => {
          setCampaigns(cs);
          setSettings(s);
          setCampaignId((cur) => (cur && cs.some((c) => c.id === cur) ? cur : (cs[0]?.id ?? null)));
          setError(null);
        },
        (e: Error) => setError(e.message),
      ),
    [id],
  );

  const loadMessages = useCallback(
    () =>
      campaignId
        ? api.listMessages(id, campaignId).then((ms) => {
            setMessages(ms);
            setMessageId((cur) => (cur && ms.some((m) => m.id === cur) ? cur : (ms[0]?.id ?? null)));
          }, (e: Error) => setError(e.message))
        : Promise.resolve(),
    [id, campaignId],
  );

  const reload = useCallback(() => Promise.all([loadCampaigns(), loadMessages()]), [loadCampaigns, loadMessages]);

  useEffect(() => {
    loadCampaigns();
  }, [loadCampaigns]);
  useEffect(() => {
    loadMessages();
  }, [loadMessages]);

  const pickCampaign = (cid: string) => {
    if (cid === campaignId) return;
    setMessages(null);
    setMessageId(null);
    setCampaignId(cid);
  };

  const drafting = !!messages?.some((m) => m.status === "drafting");
  const [now, setNow] = useState(0);
  const watching = now < watchUntil;
  useEffect(() => {
    if (!drafting && !watching) return;
    const t = setInterval(() => {
      setNow(Date.now());
      reload();
    }, POLL_MS);
    return () => clearInterval(t);
  }, [drafting, watching, reload]);

  const onChanged = useCallback(() => {
    setWatchUntil(Date.now() + 15_000);
    setNow(Date.now());
    reload();
  }, [reload]);

  const current = useMemo(() => messages?.find((m) => m.id === messageId) ?? null, [messages, messageId]);

  if (error && !campaigns) return <ErrorState message={error} onRetry={loadCampaigns} />;
  if (!campaigns) return <SheetSkeleton lines={6} />;

  return (
    <div className="space-y-6">
      <SectionHeading
        title="Outreach"
        kicker="Honest research notes to a few well-chosen people. Nothing leaves without your approval."
      >
        <Button variant="ghost" size="sm" onClick={() => setSheet("suppressions")}>
          <Ban /> Do not contact
        </Button>
        <Button size="sm" onClick={() => setSheet("campaign")}>
          <Plus /> New campaign
        </Button>
      </SectionHeading>

      <SenderStrip settings={settings} />

      {campaigns.length === 0 ? (
        <EmptyState
          title="No campaigns yet."
          action={
            <Button onClick={() => setSheet("campaign")}>
              <Plus /> Open a campaign
            </Button>
          }
        >
          A campaign holds a research purpose and a daily limit. Then pick people at your prospects and review each
          draft before anything is sent.
        </EmptyState>
      ) : (
        <>
          <nav aria-label="Campaigns" className="flex gap-2 overflow-x-auto pb-1">
            {campaigns.map((c) => (
              <button
                key={c.id}
                onClick={() => pickCampaign(c.id)}
                aria-current={c.id === campaignId}
                className={cn(
                  "sheet shrink-0 px-4 py-2.5 text-left transition-colors hover:bg-accent/40",
                  c.id === campaignId && "ring-2 ring-foreground/70",
                )}
              >
                <span className="block font-display text-lg leading-tight">{c.name}</span>
                <span className="block font-mono text-[11px] text-muted-foreground">
                  {c.stats.sent} sent · {c.stats.draft + c.stats.drafting} drafts · {c.stats.approved} approved
                  {c.status === "paused" && " · paused"}
                </span>
              </button>
            ))}
          </nav>

          {campaign && (
            <CampaignBar
              campaign={campaign}
              onAdd={() => setSheet("recipients")}
              onChanged={onChanged}
              canSend={!!settings?.sending_enabled && !!settings.sender_ready}
            />
          )}

          {!messages ? (
            <SheetSkeleton lines={6} />
          ) : messages.length === 0 ? (
            <EmptyState
              title="No messages in this campaign."
              action={
                <Button variant="outline" onClick={() => setSheet("recipients")}>
                  <UserPlus /> Add recipients
                </Button>
              }
            >
              Each recipient gets one draft written from their company’s verified evidence.
            </EmptyState>
          ) : (
            <div className="grid gap-5 xl:grid-cols-[17rem_minmax(0,1fr)]">
              <ol className="sheet divide-y divide-border self-start overflow-hidden" aria-label="Messages">
                {messages.map((m) => (
                  <li key={m.id}>
                    <button
                      onClick={() => setMessageId(m.id)}
                      aria-current={m.id === messageId}
                      className={cn(
                        "flex w-full flex-col gap-1.5 px-4 py-3 text-left transition-colors hover:bg-accent/50 focus-visible:bg-accent focus-visible:outline-none",
                        m.id === messageId && "bg-accent/60",
                      )}
                    >
                      <span className="flex items-center justify-between gap-2">
                        <span className="truncate font-medium">{m.to_name}</span>
                        <StatusStamp status={m.status} />
                      </span>
                      <span className="truncate text-xs text-muted-foreground">
                        {m.subject || (m.status === "drafting" ? "drafting…" : "no subject yet")}
                      </span>
                      {m.checks.length > 0 && m.status === "draft" && (
                        <span className="font-mono text-[10px] text-status-warning-ink">
                          {m.checks.length} check{m.checks.length === 1 ? "" : "s"} to review
                        </span>
                      )}
                    </button>
                  </li>
                ))}
              </ol>
              {current && (
                <MessageDesk
                  messageId={current.id}
                  version={`${current.updated_at}:${current.status}`}
                  settings={settings}
                  onChanged={onChanged}
                />
              )}
            </div>
          )}
        </>
      )}

      <CampaignSheet
        open={sheet === "campaign"}
        onOpenChange={(o) => setSheet(o ? "campaign" : null)}
        onCreated={(c) => {
          setSheet(null);
          pickCampaign(c.id);
          loadCampaigns();
        }}
      />
      {campaign && (
        <RecipientsSheet
          campaign={campaign}
          open={sheet === "recipients"}
          onOpenChange={(o) => setSheet(o ? "recipients" : null)}
          onDrafted={reload}
        />
      )}
      <SuppressionSheet open={sheet === "suppressions"} onOpenChange={(o) => setSheet(o ? "suppressions" : null)} />
    </div>
  );
}

function SenderStrip({ settings }: { settings: OutreachSettings | null }) {
  if (!settings) return null;
  const ready = settings.sending_enabled && settings.sender_ready;
  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-x-6 gap-y-2 rounded-lg border px-4 py-3 text-sm",
        !ready && "border-status-warning/50 bg-status-warning/5",
      )}
    >
      <span className="inline-flex items-center gap-2">
        <Mail className="size-4 text-muted-foreground" aria-hidden />
        {settings.sender_ready ? (
          <span>
            From <span className="font-medium">{settings.sender_name}</span>{" "}
            <span className="font-mono text-xs text-muted-foreground">&lt;{settings.sender_address}&gt;</span>
          </span>
        ) : (
          <span>Set EMAIL_FROM_NAME and EMAIL_FROM_ADDRESS in .env — a real sender identity is required.</span>
        )}
      </span>
      <span className="font-mono text-xs text-muted-foreground">
        {settings.sending_enabled ? settings.provider : "sending disabled (SMTP_HOST is empty)"}
      </span>
      <span className="ml-auto font-mono text-xs text-muted-foreground">
        today {settings.sent_today}/{settings.daily_limit} · one email per address per {settings.cooldown_days} days
      </span>
    </div>
  );
}

function CampaignBar({
  campaign,
  onAdd,
  onChanged,
  canSend,
}: {
  campaign: Campaign;
  onAdd: () => void;
  onChanged: () => void;
  canSend: boolean;
}) {
  const { id } = useDossier();
  const s = campaign.stats;
  const paused = campaign.status === "paused";
  return (
    <div className="sheet flex flex-wrap items-center gap-x-5 gap-y-3 p-4">
      <div className="min-w-0 flex-1 basis-72">
        <p className="eyebrow">Research purpose</p>
        <p className="mt-0.5 text-sm text-ink-soft">{campaign.purpose}</p>
      </div>
      <dl className="flex gap-5 font-mono text-xs" aria-label="Campaign tally">
        {(
          [
            ["drafts", s.draft + s.drafting],
            ["approved", s.approved],
            ["sent", s.sent],
            ["bounced", s.bounced],
            ["blocked", s.blocked],
          ] as const
        ).map(([k, v]) => (
          <div key={k} className="flex flex-col-reverse text-center">
            <dt className="mt-1 text-[10px] uppercase tracking-wider text-muted-foreground">{k}</dt>
            <dd className="font-display text-2xl leading-none tabular-nums">{v}</dd>
          </div>
        ))}
        <div className="flex flex-col-reverse text-center">
          <dt className="mt-1 text-[10px] uppercase tracking-wider text-muted-foreground">today</dt>
          <dd className="font-display text-2xl leading-none tabular-nums">
            {s.sent_today}
            <span className="text-base text-muted-foreground">/{campaign.daily_limit}</span>
          </dd>
        </div>
      </dl>
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" size="sm" onClick={onAdd}>
          <UserPlus /> Add recipients
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={() =>
            api
              .updateCampaign(id, campaign.id, { status: paused ? "active" : "paused" })
              .then(onChanged, (e: Error) => toast.error(e.message))
          }
        >
          {paused ? <Play /> : <Pause />} {paused ? "Resume" : "Pause"}
        </Button>
        <Button
          size="sm"
          disabled={s.approved === 0 || paused || !canSend}
          onClick={() =>
            api.sendCampaign(id, campaign.id).then(
              (r) => {
                toast(`Queued ${r.queued} approved message${r.queued === 1 ? "" : "s"}`, {
                  description: "Limits, suppression and duplicates are re-checked before each send.",
                });
                onChanged();
              },
              (e: Error) => toast.error(e.message),
            )
          }
        >
          <Send /> Send {s.approved} approved
        </Button>
      </div>
    </div>
  );
}
