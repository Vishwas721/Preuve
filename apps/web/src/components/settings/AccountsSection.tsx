"use client";

// Settings → Accounts (Phase 5C): only for the instance owner (the account that set Preuve up).
// Lists every account and creates one-time password-reset links.

import { KeyRound } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { SectionHeading } from "@/components/dossier/layout";
import { useSession } from "@/components/shell/SessionProvider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, type AdminUser } from "@/lib/api";
import { relativeTime } from "@/lib/format";

export function AccountsSection() {
  const { me } = useSession();
  const owner = !!me?.user.is_instance_owner;
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [link, setLink] = useState<{ email: string; url: string } | null>(null);

  useEffect(() => {
    if (!owner) return;
    api.adminUsers().then(setUsers, (e: Error) => toast.error(e.message));
  }, [owner]);

  if (!owner) return null;

  async function reset(u: AdminUser) {
    try {
      const r = await api.createResetLink(u.id);
      setLink({ email: u.email, url: `${window.location.origin}/reset/${r.token}` });
    } catch (err) {
      toast.error((err as Error).message);
    }
  }

  return (
    <section aria-labelledby="accounts" className="space-y-4">
      <SectionHeading
        title={<span id="accounts">Accounts</span>}
        kicker="You set Preuve up, so you can help anyone who forgot their password with a one-time reset link."
      />
      <div className="sheet space-y-4 p-5">
        <ul className="divide-y divide-border rounded-md border">
          {users.map((u) => (
            <li key={u.id} className="flex flex-wrap items-center gap-3 px-3 py-2.5">
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm">
                  {u.name}
                  {u.is_instance_owner && <span className="text-muted-foreground"> (instance owner)</span>}
                </p>
                <p className="truncate font-mono text-[11px] text-muted-foreground">
                  {u.email} · {u.workspaces.join(", ") || "no workspace"} ·{" "}
                  {u.last_login_at ? `signed in ${relativeTime(u.last_login_at)}` : "never signed in"}
                </p>
              </div>
              <Button size="sm" variant="ghost" onClick={() => void reset(u)}>
                <KeyRound /> Reset link
              </Button>
            </li>
          ))}
        </ul>
        {link && (
          <div className="space-y-2 rounded-md border border-status-warning/40 bg-status-warning/5 p-3">
            <p className="text-sm font-medium">Reset link for {link.email}</p>
            <Input
              readOnly
              value={link.url}
              aria-label="Password reset link"
              className="font-mono text-xs"
              onFocus={(e) => e.currentTarget.select()}
            />
            <p className="text-xs text-muted-foreground">
              Works once, for 1 hour. Send it to them yourself. Whoever opens it can set the password, so share it
              privately. It won&apos;t be shown again.
            </p>
          </div>
        )}
      </div>
    </section>
  );
}
