"use client";

import { Check, Copy, KeyRound, Trash2, UserPlus } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { toast } from "sonner";

import { SectionHeading } from "@/components/dossier/layout";
import { useSession } from "@/components/shell/SessionProvider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api, type ApiTokenRow, type Invitation, type Member, type Role } from "@/lib/api";
import { relativeTime, shortDate } from "@/lib/format";

function Section({ id, title, kicker, children }: { id: string; title: string; kicker?: string; children: ReactNode }) {
  return (
    <section aria-labelledby={id} className="space-y-4">
      <SectionHeading title={<span id={id}>{title}</span>} kicker={kicker} />
      {children}
    </section>
  );
}

/** A secret shown once, with a copy button. */
function OneTimeSecret({ label, value, note }: { label: string; value: string; note: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="space-y-2 rounded-md border border-status-warning/40 bg-status-warning/5 p-3">
      <p className="text-sm font-medium">{label}</p>
      <div className="flex gap-2">
        <Input readOnly value={value} className="font-mono text-xs" onFocus={(e) => e.currentTarget.select()} aria-label={label} />
        <Button
          type="button"
          variant="outline"
          size="icon"
          aria-label="Copy"
          onClick={async () => {
            await navigator.clipboard.writeText(value);
            setCopied(true);
          }}
        >
          {copied ? <Check /> : <Copy />}
        </Button>
      </div>
      <p className="text-xs text-muted-foreground">{note}</p>
    </div>
  );
}

function errorToast(e: unknown) {
  toast.error((e as Error).message);
}

// ---------- account ----------

function Account() {
  const { me } = useSession();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [busy, setBusy] = useState(false);
  if (!me) return null;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await api.changePassword(current, next);
      setCurrent("");
      setNext("");
      toast("Password changed", { description: "Your other sessions were signed out." });
    } catch (err) {
      errorToast(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Section id="account" title="Account">
      <div className="sheet grid gap-6 p-5 md:grid-cols-2">
        <dl className="space-y-3 text-sm">
          <div>
            <dt className="eyebrow !text-[9px]">Name</dt>
            <dd className="mt-0.5">{me.user.name}</dd>
          </div>
          <div>
            <dt className="eyebrow !text-[9px]">Email</dt>
            <dd className="mt-0.5 font-mono text-xs">{me.user.email}</dd>
          </div>
        </dl>
        <form onSubmit={submit} className="space-y-3">
          <p className="eyebrow">Change password</p>
          <Input
            type="password"
            autoComplete="current-password"
            placeholder="Current password"
            aria-label="Current password"
            required
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
          />
          <Input
            type="password"
            autoComplete="new-password"
            placeholder="New password (10+ characters)"
            aria-label="New password"
            required
            minLength={10}
            value={next}
            onChange={(e) => setNext(e.target.value)}
          />
          <Button type="submit" size="sm" variant="outline" disabled={busy}>
            Change password
          </Button>
        </form>
      </div>
    </Section>
  );
}

// ---------- workspace, members, invitations ----------

function WorkspaceSection() {
  const { me, activeWorkspace, refresh, switchWorkspace } = useSession();
  const params = useSearchParams();
  const newRef = useRef<HTMLInputElement>(null);
  const [name, setName] = useState(activeWorkspace?.name ?? "");
  const [newName, setNewName] = useState("");
  const [members, setMembers] = useState<Member[] | null>(null);
  const [invites, setInvites] = useState<Invitation[]>([]);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<Role>("member");
  const [link, setLink] = useState<string | null>(null);
  const ws = activeWorkspace;
  const owner = ws?.role === "owner";

  const load = useCallback(() => {
    if (!ws) return Promise.resolve();
    return Promise.all([api.listMembers(ws.id), owner ? api.listInvitations(ws.id) : Promise.resolve([])]).then(
      ([m, i]) => {
        setMembers(m);
        setInvites(i);
      },
      errorToast,
    );
  }, [ws, owner]);
  useEffect(() => {
    void load();
  }, [load]);
  useEffect(() => {
    if (params.get("new") === "workspace") newRef.current?.focus();
  }, [params]);

  if (!me || !ws) return null;

  async function act(fn: () => Promise<unknown>, done?: string) {
    try {
      await fn();
      if (done) toast(done);
      await load();
    } catch (e) {
      errorToast(e);
    }
  }

  return (
    <Section id="workspace" title="Workspace" kicker="Everyone in a workspace sees all of its cases. Owners manage members.">
      <div className="sheet space-y-6 p-5">
        <form
          className="flex flex-wrap items-end gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            void act(async () => {
              await api.renameWorkspace(ws.id, name);
              await refresh();
            }, "Workspace renamed");
          }}
        >
          <div className="min-w-0 flex-1 space-y-1.5">
            <Label htmlFor="ws-name">Name</Label>
            <Input id="ws-name" value={name} maxLength={200} disabled={!owner} onChange={(e) => setName(e.target.value)} />
          </div>
          {owner && (
            <Button type="submit" variant="outline" size="sm" disabled={!name.trim() || name === ws.name}>
              Rename
            </Button>
          )}
        </form>

        <div>
          <p className="eyebrow mb-2">Members</p>
          <ul className="divide-y divide-border rounded-md border">
            {(members ?? []).map((m) => {
              const self = m.user_id === me.user.id;
              return (
                <li key={m.user_id} className="flex flex-wrap items-center gap-3 px-3 py-2.5">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm">
                      {m.name}
                      {self && <span className="text-muted-foreground"> (you)</span>}
                    </p>
                    <p className="truncate font-mono text-[11px] text-muted-foreground">
                      {m.email} · joined {shortDate(m.joined_at)}
                    </p>
                  </div>
                  {owner ? (
                    <Select value={m.role} onValueChange={(r) => void act(() => api.setMemberRole(ws.id, m.user_id, r as Role))}>
                      <SelectTrigger className="h-8 w-28" aria-label={`Role of ${m.name}`}>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="owner">Owner</SelectItem>
                        <SelectItem value="member">Member</SelectItem>
                      </SelectContent>
                    </Select>
                  ) : (
                    <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">{m.role}</span>
                  )}
                  {(owner || self) && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() =>
                        void act(async () => {
                          await api.removeMember(ws.id, m.user_id);
                          if (self) {
                            await refresh();
                            // eslint-disable-next-line @next/next/no-location-assign-relative-destination
                            window.location.assign("/"); // full reload: drop the left workspace's data
                          }
                        }, self ? "You left the workspace" : "Member removed")
                      }
                    >
                      {self ? "Leave" : "Remove"}
                    </Button>
                  )}
                </li>
              );
            })}
          </ul>
        </div>

        {owner && (
          <div className="space-y-3">
            <p className="eyebrow">Invite someone</p>
            <form
              className="flex flex-wrap gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                void act(async () => {
                  const inv = await api.invite(ws.id, inviteEmail, inviteRole);
                  setLink(`${window.location.origin}/invite/${inv.token}`);
                  setInviteEmail("");
                });
              }}
            >
              <Input
                type="email"
                required
                placeholder="their@email.com"
                aria-label="Email to invite"
                className="min-w-0 flex-1"
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
              />
              <Select value={inviteRole} onValueChange={(r) => setInviteRole(r as Role)}>
                <SelectTrigger className="w-28" aria-label="Role">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="member">Member</SelectItem>
                  <SelectItem value="owner">Owner</SelectItem>
                </SelectContent>
              </Select>
              <Button type="submit" size="sm" className="h-9">
                <UserPlus /> Create link
              </Button>
            </form>
            {link && (
              <OneTimeSecret
                label="Invitation link"
                value={link}
                note="Send it to them yourself. It works once, for that email, for 7 days. It won't be shown again."
              />
            )}
            {invites.length > 0 && (
              <ul className="space-y-1.5 text-sm">
                {invites.map((i) => (
                  <li key={i.id} className="flex flex-wrap items-center gap-2">
                    <span className="min-w-0 flex-1 truncate">
                      {i.email} <span className="font-mono text-[10px] uppercase text-muted-foreground">{i.role}</span>
                    </span>
                    <span className="font-mono text-[11px] text-muted-foreground">expires {shortDate(i.expires_at)}</span>
                    <Button variant="ghost" size="sm" onClick={() => void act(() => api.revokeInvitation(ws.id, i.id), "Invitation revoked")}>
                      Revoke
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        <form
          className="flex flex-wrap items-end gap-2 border-t rule pt-5"
          onSubmit={(e) => {
            e.preventDefault();
            void act(async () => {
              const created = await api.createWorkspace(newName);
              setNewName("");
              await switchWorkspace(created.id);
            });
          }}
        >
          <div className="min-w-0 flex-1 space-y-1.5">
            <Label htmlFor="ws-new">New workspace</Label>
            <Input
              id="ws-new"
              ref={newRef}
              required
              maxLength={200}
              placeholder="e.g. Side projects"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
            />
          </div>
          <Button type="submit" size="sm" variant="outline">
            Create and switch
          </Button>
        </form>
      </div>
    </Section>
  );
}

// ---------- API tokens ----------

function Tokens() {
  const { activeWorkspace } = useSession();
  const [rows, setRows] = useState<ApiTokenRow[]>([]);
  const [name, setName] = useState("research CLI");
  const [secret, setSecret] = useState<string | null>(null);
  const { me } = useSession();
  const wsName = (id: string) => me?.workspaces.find((w) => w.id === id)?.name ?? "another workspace";

  const load = useCallback(() => api.listTokens().then(setRows, errorToast), []);
  useEffect(() => {
    void load();
  }, [load]);

  return (
    <Section
      id="tokens"
      title="API tokens"
      kicker="For the /research-idea skill and other scripts. A token sees only the workspace it was created in."
    >
      <div className="sheet space-y-4 p-5">
        <form
          className="flex flex-wrap gap-2"
          onSubmit={async (e) => {
            e.preventDefault();
            try {
              const t = await api.createToken(name);
              setSecret(t.token);
              await load();
            } catch (err) {
              errorToast(err);
            }
          }}
        >
          <Input aria-label="Token name" required maxLength={100} className="min-w-0 flex-1" value={name} onChange={(e) => setName(e.target.value)} />
          <Button type="submit" size="sm" className="h-9">
            <KeyRound /> Create token for “{activeWorkspace?.name}”
          </Button>
        </form>
        {secret && (
          <OneTimeSecret
            label="New API token"
            value={secret}
            note="Copy it now: it won't be shown again. In your shell: export PREUVE_API_TOKEN=… (never commit it)."
          />
        )}
        {rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">No tokens.</p>
        ) : (
          <ul className="divide-y divide-border rounded-md border">
            {rows.map((t) => (
              <li key={t.id} className="flex flex-wrap items-center gap-3 px-3 py-2.5">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm">{t.name}</p>
                  <p className="truncate font-mono text-[11px] text-muted-foreground">
                    {t.token_prefix}… · {wsName(t.workspace_id)} ·{" "}
                    {t.last_used_at ? `used ${relativeTime(t.last_used_at)}` : "never used"}
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={`Revoke ${t.name}`}
                  onClick={async () => {
                    try {
                      await api.revokeToken(t.id);
                      await load();
                    } catch (err) {
                      errorToast(err);
                    }
                  }}
                >
                  <Trash2 />
                </Button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Section>
  );
}

export default function SettingsPage() {
  return (
    <main className="mx-auto w-full max-w-3xl space-y-12 px-4 pb-24 pt-10 sm:px-6">
      <div>
        <p className="eyebrow">Settings</p>
        <h1 className="mt-2 font-display text-5xl leading-tight">Your account and workspace</h1>
      </div>
      <Account />
      <Suspense>
        <WorkspaceSection />
      </Suspense>
      <Tokens />
    </main>
  );
}
