"use client";

// Who is signed in, and in which workspace (Phase 5A). Private pages render only once the
// session is known; a missing or expired session sends the browser to /login (or /setup on a
// fresh install), then back to where it was.

import { usePathname, useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError, setUnauthorizedHandler, type Me } from "@/lib/api";

const PUBLIC = [/^\/login$/, /^\/setup$/, /^\/invite\/[^/]+$/, /^\/reset\/[^/]+$/];
export const isPublicPath = (path: string) => PUBLIC.some((re) => re.test(path));

interface SessionValue {
  me: Me | null;
  activeWorkspace: Me["workspaces"][number] | null;
  refresh: () => Promise<Me | null>;
  switchWorkspace: (id: string) => Promise<void>;
  signOut: () => Promise<void>;
}

const Ctx = createContext<SessionValue | null>(null);

export function useSession(): SessionValue {
  const v = useContext(Ctx);
  if (!v) throw new Error("useSession outside SessionProvider");
  return v;
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [checked, setChecked] = useState(false);
  const isPublic = isPublicPath(pathname);

  const toSignIn = useCallback(async () => {
    setMe(null);
    const here = window.location.pathname + window.location.search;
    let setup = false;
    try {
      setup = (await api.authStatus()).needs_setup;
    } catch {
      // API down: the login page explains
    }
    if (setup) router.replace("/setup");
    else router.replace(`/login?next=${encodeURIComponent(here)}`);
  }, [router]);

  const refresh = useCallback(
    () =>
      api.me().then(
        (m) => {
          setMe(m);
          setChecked(true);
          return m as Me | null;
        },
        (e: unknown) => {
          setChecked(true);
          if (e instanceof ApiError && e.status === 401) {
            setMe(null);
            return null;
          }
          throw e;
        },
      ),
    [],
  );

  useEffect(() => {
    setUnauthorizedHandler(() => {
      if (!isPublicPath(window.location.pathname)) void toSignIn();
    });
    return () => setUnauthorizedHandler(null);
  }, [toSignIn]);

  useEffect(() => {
    refresh().then(
      (m) => {
        if (!m && !isPublic) void toSignIn();
      },
      () => setChecked(true),
    );
    // Re-check when moving between public and private pages (e.g. after signing in).
  }, [isPublic, refresh, toSignIn]);

  const switchWorkspace = useCallback(async (id: string) => {
    await api.switchWorkspace(id);
    // Every view's data belongs to the old workspace: a full reload starts clean on the board.
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.assign("/");
  }, []);

  const signOut = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      // A full reload drops every piece of the signed-out user's data held in memory.
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination
      window.location.assign("/login");
    }
  }, []);

  const value = useMemo<SessionValue>(
    () => ({
      me,
      activeWorkspace: me?.workspaces.find((w) => w.id === me.active_workspace_id) ?? null,
      refresh,
      switchWorkspace,
      signOut,
    }),
    [me, refresh, switchWorkspace, signOut],
  );

  if (!isPublic && !me) {
    return (
      <Ctx.Provider value={value}>
        <main className="mx-auto w-full max-w-7xl px-4 py-12 sm:px-6" aria-busy="true" aria-label="Loading">
          {checked ? null : (
            <>
              <Skeleton className="h-3 w-40" />
              <Skeleton className="mt-4 h-12 w-96 max-w-full" />
            </>
          )}
        </main>
      </Ctx.Provider>
    );
  }
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
