// Small display helpers shared across the dossier.

const rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto" });

export function relativeTime(iso: string): string {
  const diff = (new Date(iso).getTime() - Date.now()) / 1000;
  const units: [Intl.RelativeTimeFormatUnit, number][] = [
    ["year", 31_536_000],
    ["month", 2_592_000],
    ["week", 604_800],
    ["day", 86_400],
    ["hour", 3_600],
    ["minute", 60],
  ];
  for (const [unit, secs] of units) {
    if (Math.abs(diff) >= secs) return rtf.format(Math.round(diff / secs), unit);
  }
  return "just now";
}

export function shortDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export function domain(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

/** Evidence items are exhibits: EX-01, EX-02… numbered by their position in the case. */
export function exhibitNo(index: number): string {
  return `EX-${String(index + 1).padStart(2, "0")}`;
}

export function plural(n: number, one: string, many = `${one}s`): string {
  return `${n} ${n === 1 ? one : many}`;
}

type Sourced = { url: string; origin?: string; response_id?: string | null; interview_id?: string | null };

/** Where an exhibit comes from: a web domain, or the prospect's own words (Phase 3). */
export function sourceName(ev: Sourced): string {
  if (ev.origin === "reply") return "Prospect reply";
  if (ev.origin === "interview") return "Interview notes";
  return domain(ev.url);
}

/** Link to an exhibit's source: the public page, or the reply / interview inside Preuve. */
export function sourceHref(ideaId: string, ev: Sourced): { href: string; internal: boolean } {
  if (ev.origin === "reply" && ev.response_id)
    return { href: `/ideas/${ideaId}/replies?r=${ev.response_id}`, internal: true };
  if (ev.origin === "interview" && ev.interview_id)
    return { href: `/ideas/${ideaId}/interviews?i=${ev.interview_id}`, internal: true };
  return { href: ev.url, internal: false };
}
