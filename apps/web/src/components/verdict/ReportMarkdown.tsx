// Renders the Markdown subset the API's report renderer emits (reports/service.py): `#`/`##`
// headings, `- ` lists, pipe tables, paragraphs, **bold** and _italic_. Text is rendered as React
// text nodes (never as HTML), so nothing in a quote can inject markup.

import { Fragment, type ReactNode } from "react";

function inline(text: string): ReactNode[] {
  // Split on **bold** and _italic_ (whole-word underscores only).
  const parts = text.split(/(\*\*[^*]+\*\*|(?:^|(?<=\s))_[^_]+_(?=\s|$|[.,;:]))/g);
  return parts.map((p, i) => {
    if (p.startsWith("**") && p.endsWith("**") && p.length > 4) return <strong key={i}>{p.slice(2, -2)}</strong>;
    if (p.startsWith("_") && p.endsWith("_") && p.length > 2) return <em key={i}>{p.slice(1, -1)}</em>;
    return <Fragment key={i}>{p}</Fragment>;
  });
}

function cells(row: string): string[] {
  return row
    .trim()
    .replace(/^\||\|$/g, "")
    .split(/(?<!\\)\|/)
    .map((c) => c.trim().replace(/\\\|/g, "|"));
}

type Block =
  | { t: "h1" | "h2" | "p"; text: string }
  | { t: "ul"; items: string[] }
  | { t: "table"; head: string[]; rows: string[][] };

export function parse(md: string): Block[] {
  const lines = md.split("\n");
  const out: Block[] = [];
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (!line.trim()) continue;
    if (line.startsWith("## ")) out.push({ t: "h2", text: line.slice(3) });
    else if (line.startsWith("# ")) out.push({ t: "h1", text: line.slice(2) });
    else if (line.startsWith("- ")) {
      const items: string[] = [];
      while (i < lines.length && lines[i].startsWith("- ")) items.push(lines[i++].slice(2));
      i--;
      out.push({ t: "ul", items });
    } else if (line.startsWith("|")) {
      const rows: string[][] = [];
      while (i < lines.length && lines[i].startsWith("|")) {
        if (!/^\|[\s|:-]+\|$/.test(lines[i].trim())) rows.push(cells(lines[i]));
        i++;
      }
      i--;
      out.push({ t: "table", head: rows[0] ?? [], rows: rows.slice(1) });
    } else out.push({ t: "p", text: line });
  }
  return out;
}

export function ReportMarkdown({ content }: { content: string }) {
  return (
    // overflow-wrap:anywhere lets long source URLs break instead of widening the page on phones.
    <article className="report min-w-0 space-y-4 text-[15px] leading-relaxed [overflow-wrap:anywhere]">
      {parse(content).map((b, i) => {
        switch (b.t) {
          case "h1":
            return (
              <h1 key={i} className="font-display text-4xl leading-tight sm:text-5xl">
                {inline(b.text)}
              </h1>
            );
          case "h2":
            return (
              <h2 key={i} className="break-after-avoid border-b rule pb-1.5 pt-6 font-display text-2xl">
                {inline(b.text)}
              </h2>
            );
          case "ul":
            return (
              <ul key={i} className="list-disc space-y-1.5 pl-5 marker:text-muted-foreground">
                {b.items.map((it, j) => (
                  <li key={j} className="break-inside-avoid">
                    {inline(it)}
                  </li>
                ))}
              </ul>
            );
          case "table":
            return (
              <div key={i} className="overflow-x-auto">
                <table className="w-full min-w-[28rem] text-sm">
                  <thead>
                    <tr className="border-b rule text-left">
                      {b.head.map((h, j) => (
                        <th key={j} className="py-1.5 pr-3 align-bottom font-medium">
                          {inline(h)}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {b.rows.map((r, j) => (
                      <tr key={j} className="break-inside-avoid border-b border-border/50 align-top">
                        {r.map((c, k) => (
                          <td key={k} className="py-1.5 pr-3">
                            {inline(c)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            );
          default:
            return <p key={i}>{inline(b.text)}</p>;
        }
      })}
    </article>
  );
}
