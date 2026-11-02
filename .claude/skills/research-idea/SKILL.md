---
name: research-idea
description: Research a startup idea for Preuve. Finds public evidence for and against the problem, writes a verified research pack plus a report, and imports it into Preuve. Use when the user pastes an idea to validate, gives a Preuve idea id to research, or asks to research or re-research an idea.
---

# /research-idea — method v2

You are Preuve's research analyst (ADR 0004). Find **real, public evidence** about whether the
idea's problem exists, how painful it is and how it is solved today. Then hand Preuve a research
pack that it verifies independently.

**The prime rule:** Preuve fetches every URL you cite and checks that your quote is on the page.
A paraphrased quote gets rejected, and an invented one gets you caught. Finding "no evidence" is
a valid, valuable result. Never fill gaps with plausible-sounding claims.

## 0. Preconditions

Run everything from `apps/api`. Run pnpm and long commands with `< /dev/null`.

```bash
docker compose --env-file ../../.env -f ../../infra/docker-compose.yml up -d   # if not running
curl -s http://127.0.0.1:8000/health    # API must be up:  uv run uvicorn app.main:app
                                        # worker must be up: uv run arq app.workers.settings.WorkerSettings
```

If the API or worker isn't running, start it in the background before continuing.

## 1. Get the idea into Preuve

- **The user gave an idea id:** go to step 2.
- **The user pasted an idea:** create it, with the 1A analysis, so research can target its
  unknowns:

  ```bash
  uv run python -m app.scripts.research create --title "<short name>" \
    --description "<the idea in the user's words>" --market "<market, default United States>" \
    --why "<why they think it matters, if given>" --analyze
  ```

## 2. Read the context

```bash
uv run python -m app.scripts.research context <idea_id>
```

You get the hypothesis, the **unknowns with their ids**, the ICPs and any research done so far.
The unknowns are your research plan. Skip URLs listed in `existing_research` unless you're
re-checking them.

## 3. Plan

For each open unknown (high priority first), write 2–4 search queries across these source types:

| Source type | What it shows | Example query shapes |
|---|---|---|
| `job_posting` | The manual work exists and is paid for | `"<role>" "<task>" job`, `"prepare weekly reports" coordinator` |
| `forum` | People describing the pain in their own words | `<problem> site:reddit.com`, industry forums, Q&A sites |
| `review` | Complaints about current tools (G2, Capterra, app stores) | `<tool> reviews cons`, `<tool> "wish it"` |
| `industry_publication` | Workflows, costs, adoption | trade magazines, associations |
| `news` / `report` | Market moves, survey data | `<industry> survey <problem>` |
| `company_site` | How vendors frame the problem; customer stories | competitor pages, case studies |

Also plan **at least 2 contradiction searches**: evidence that the problem is solved, rare, cheap
or unimportant (e.g. `<problem> solved`, `<tool> works great`, `"not a problem"`).

Record every query you run in `meta.queries`.

## 4. Search, read and quote

1. Find candidates with **WebSearch**.
2. Read the page with **Preuve's fetcher**, not a summarizer, so the text you quote is exactly
   what Preuve will check:

   ```bash
   uv run python -m app.scripts.research fetch "<url>"          # main content
   uv run python -m app.scripts.research fetch "<url>" --full   # every visible text node
   ```

3. Copy the quote **character for character** from that output: 20–600 characters, the
   shortest span that proves the point.
   - You may join two passages from the same page with ` … `. Each piece must be at least 8
     characters and appear in that order.
   - Never fix typos, change tense or merge sentences.
4. If `fetch` prints `UNVERIFIABLE` (robots.txt, paywall, error), the item will import as
   *unverifiable*. Prefer another source. Keep it only if it adds something unique, and quote it
   only from text you actually read, for example via WebFetch while asking for verbatim text.
5. Never cite a page you didn't open.

For each item, decide:

- **kind:** `fact` if the source states it directly (a posting lists the task, a person says
  they spend 4h). `inference` if you're drawing a reasonable conclusion from what it states.
- **stance:** relative to the hypothesis' problem: `supports`, `contradicts` or `neutral`.
- **relevance:** `high` if it speaks directly to an unknown or the core problem, `medium` if it
  only gives useful context, `low` if it's tangential (usually leave those out).
- **unknown_ids:** the unknowns it informs (ids from step 2).
- **company_name:** only if the evidence is about a specific company. **Never record people's
  names or usernames.**

**Budget:** about 15–25 evidence items for the unknowns, plus what step 5b needs (typically 5–12 more), with a mix of source types. Stop when more searching
isn't changing the picture. Quality beats count.

## 5. Conclude per unknown

For every open unknown, add a `unknown_findings` entry with one of these statuses:

- `answered`: the evidence clearly answers it;
- `partially_answered`: some signal, but gaps remain;
- `no_evidence_found`: you looked and found nothing. Use an empty summary, or an
  `assumption`-kind claim noting what's missing.

Each summary is a short list of claims, `{statement, kind, evidence_ids: [refs]}`:

- `fact` claims must cite refs;
- cite only refs in this pack;
- write claims that state what the evidence says, not more.

Optional, and only when the evidence warrants it:

- `hypothesis_update`: refined hypothesis fields, with `rationale` claims citing refs. Preuve
  saves it as a new version; it never overwrites the user's.
- `new_unknowns`: important questions the research raised.

## 5b. Competitors and alternatives: how is it solved today?

Answer "how is this problem solved today?" with sourced entries only (PRD §13).

1. **Founder-listed competitors** (`idea.known_competitors` in the context): research each one.
   Include it if you find public evidence about it. If you don't, say so in the report.
2. **Search for the four kinds:**
   - `direct`: products solving the same problem (`<problem> software`, `<problem> app`,
     `<problem> AI`);
   - `indirect`: broader tools that cover part of it, such as the incumbent platform's features;
   - `manual`: spreadsheets, email, chat apps, paper, internal tools
     (`<problem> template`, `<problem> excel`);
   - `service`: consultants, agencies, outsourced or third-party providers
     (`<problem> consultant`, `<problem> services`).
3. **At least one complaint search** about the leading tool, e.g. `<tool> problems`,
   `<tool> reviews cons`, `<tool> alternative`. Review sites often block Preuve's crawler; prefer
   fetchable sources such as vendor docs, forums, news and publications.
4. **Every competitor needs evidence.** Add an `evidence[]` item for the page that shows it
   exists or what it does, then cite those refs in the competitor's `evidence_refs`.
   - Re-citing a page and quote already imported is fine; Preuve deduplicates.
   - A competitor whose evidence is all rejected is not stored.
   - `pricing_note` only when the price is publicly stated on a cited page.
   - `sentiment`: claims about what customers praise or complain about, citing refs. Only use
     what the sources actually say.
5. **`current_solutions`:** 2–5 claims summarizing how the problem is solved today, citing refs.
   Include the boring answer (spreadsheets, email) when the evidence shows it.

## 6. Write the pack and the report

Write two files to `research/<idea-slug>/` at the repo root. Use a short kebab-case slug,
e.g. `construction-progress-reports`.

**`pack-<YYYY-MM-DD>.json`**, matching `docs/research-pack.schema.json`:

```json
{
  "meta": {
    "schema_version": "1.1",
    "method_version": "2",
    "idea_id": "<uuid>",
    "researcher": "claude-code",
    "started_at": "<iso>",
    "finished_at": "<iso>",
    "queries": ["..."],
    "notes": "scope, limits, anything a reviewer should know"
  },
  "evidence": [
    {
      "ref": "ev-01",
      "url": "https://...",
      "title": "...",
      "source_type": "job_posting",
      "published_at": "2026-05-01",
      "quote": "exact text",
      "statement": "what it shows",
      "kind": "fact",
      "stance": "supports",
      "relevance": "high",
      "unknown_ids": ["<uuid>"],
      "company_name": null
    }
  ],
  "unknown_findings": [
    {
      "unknown_id": "<uuid>",
      "status": "partially_answered",
      "summary": [{"statement": "...", "kind": "fact", "evidence_ids": ["ev-01"]}]
    }
  ],
  "hypothesis_update": null,
  "new_unknowns": [],
  "competitors": [
    {
      "ref": "comp-01",
      "name": "Procore",
      "url": "https://www.procore.com",
      "kind": "indirect",
      "description": "what part of the problem it covers",
      "pricing_note": null,
      "evidence_refs": ["ev-07"],
      "sentiment": [{"statement": "...", "kind": "fact", "evidence_ids": ["ev-09"]}]
    }
  ],
  "current_solutions": [
    {"statement": "...", "kind": "fact", "evidence_ids": ["ev-02", "ev-07"]}
  ]
}
```

**`report-<YYYY-MM-DD>.md`**, a readable summary for the founder. Cite refs like `[ev-03]`.

- **Bottom line**: 2–3 sentences, honest about strength. Weak evidence means saying so plainly.
- **What supports the problem**: the strongest items first.
- **What argues against it**: the contradicting evidence, never omitted.
- **Unknowns**: the status of each, and what's still missing.
- **How it's solved today**: the competitors and alternatives by kind, plus the founder-listed
  competitors with no public evidence. Only what the evidence shows.
- **Method notes**: queries, source mix, limits, what couldn't be verified.

## 7. Validate and import

```bash
uv run python -m app.scripts.research validate ../../research/<slug>/pack-<date>.json
uv run python -m app.scripts.research import   ../../research/<slug>/pack-<date>.json
```

- **Rejected items:** re-fetch the page, fix the quote so it's verbatim, and import again.
  Re-imports are deduplicated. If you can't find the passage again, leave the item out.
- **Dropped claims or downgraded findings:** treat them as a signal that the conclusion was
  stronger than the verified evidence. Update the report so it matches.

## 8. Finish

- Commit the pack and report:
  `git add research/<slug> && git commit -m "research: <slug> (method v2)"` and push.
- Tell the user:
  - verified / unverifiable / rejected counts;
  - the bottom line;
  - the 2–3 strongest supporting and contradicting items;
  - which unknowns are still open;
  - where to see it: `http://localhost:3000/ideas/<idea_id>`.

## Method changelog

- **v1 (2026-11-01):** initial method.
- **v2 (2026-11-02):** adds step 5b (competitors and alternatives, `current_solutions`), pack
  schema 1.1.
