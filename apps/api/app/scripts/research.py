"""CLI used by the `/research-idea` skill (ADR 0004).

  uv run python -m app.scripts.research context <idea_id>
  uv run python -m app.scripts.research create --title T --description D --market US [--analyze]
  uv run python -m app.scripts.research fetch <url> [--full]
  uv run python -m app.scripts.research validate <pack.json>
  uv run python -m app.scripts.research import <pack.json>

`context`, `create` and `import` talk to the running API (PREUVE_API_URL, default
http://localhost:3100/api, the app started with preuve.cmd) with a personal API token
(PREUVE_API_TOKEN, created under Settings > API tokens; it's bound to one workspace).
`import` also needs the worker. `fetch` and `validate` work offline.
"""

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx
from pydantic import ValidationError

from app.modules.research.pack import ResearchPack
from app.search.fetch import FetchError, PageFetcher

# The local app started with `preuve.cmd` (production stack, API behind the web app at /api).
# For the development setup use PREUVE_API_URL=http://127.0.0.1:8000.
API = os.environ.get("PREUVE_API_URL", "http://localhost:3100/api")
POLL_S = 2.0
NO_TOKEN = (
    "Set PREUVE_API_TOKEN to a Preuve API token (Settings > API tokens in the web app, "
    "in the workspace that holds the idea)."
)


def _headers() -> dict[str, str]:
    token = os.environ.get("PREUVE_API_TOKEN", "").strip()
    if not token:
        sys.exit(NO_TOKEN)
    return {"Authorization": f"Bearer {token}"}


def _api(method: str, path: str, **kwargs: Any) -> Any:
    try:
        resp = httpx.request(method, f"{API}{path}", timeout=30, headers=_headers(), **kwargs)
    except httpx.HTTPError as exc:
        sys.exit(f"Cannot reach the Preuve API at {API} ({exc}). Is uvicorn running?")
    if resp.status_code == 401:
        sys.exit(f"The API refused the token (revoked or wrong). {NO_TOKEN}")
    if resp.status_code == 404 and path.startswith("/ideas/"):
        sys.exit(
            f"{method} {path} -> 404: no such idea in this token's workspace. "
            "Use a token created in the idea's workspace."
        )
    if resp.status_code >= 400:
        sys.exit(f"{method} {path} -> {resp.status_code}: {resp.text}")
    return resp.json() if resp.content else None


def _wait(path: str, done: callable, timeout_s: float = 900) -> Any:
    deadline = time.monotonic() + timeout_s
    while True:
        body = _api("GET", path)
        if done(body):
            return body
        if time.monotonic() > deadline:
            sys.exit(f"Timed out waiting on {path}. Is the arq worker running?")
        time.sleep(POLL_S)


# ---------- commands ----------


def cmd_context(args: argparse.Namespace) -> None:
    idea = _api("GET", f"/ideas/{args.idea_id}")
    analysis = _api("GET", f"/ideas/{args.idea_id}/analysis")
    research = _api("GET", f"/ideas/{args.idea_id}/research")
    findings = {f["unknown_id"]: f["status"] for f in research["findings"]}
    stances: dict[str, int] = {}
    for e in research["evidence"]:
        stances[e["stance"]] = stances.get(e["stance"], 0) + 1
    out = {
        "idea": {
            k: idea[k]
            for k in (
                "id",
                "title",
                "description",
                "target_market",
                "why_it_matters",
                "industry",
                "customer_type",
                "known_competitors",
                "assumptions",
            )
        },
        "hypothesis": analysis["hypothesis"]
        and {
            k: analysis["hypothesis"][k]
            for k in (
                "version",
                "problem",
                "users",
                "buyer",
                "decision_maker",
                "economic_value",
                "geography",
                "industry",
            )
        },
        "unknowns": [
            {k: u[k] for k in ("id", "question", "category", "priority", "status")}
            | {"latest_finding": findings.get(u["id"])}
            for u in analysis["unknowns"]
        ],
        "icps": [
            {
                "name": i["name"],
                "primary": i["is_primary"],
                "score": i["hypothesis_score"],
                "company_type": i["company_type"],
                "size": [i["size_min"], i["size_max"]],
                "geography": i["geography"],
                "signals": i["signals"],
                "roles": i["roles"],
            }
            for i in analysis["icps"]
        ],
        "existing_research": {
            "imports": len(research["imports"]),
            "evidence_by_stance": stances,
            "evidence_urls": sorted({e["url"] for e in research["evidence"]}),
        },
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))


def cmd_create(args: argparse.Namespace) -> None:
    body = {
        "title": args.title,
        "description": args.description,
        "target_market": args.market,
        "why_it_matters": args.why,
    }
    idea = _api("POST", "/ideas", json=body)
    print(f"Created idea {idea['id']}")
    if args.analyze:
        run = _api("POST", f"/ideas/{idea['id']}/analyze")
        print("Analyzing (hypothesis, unknowns, ICPs)…", flush=True)
        run = _wait(
            f"/ideas/{idea['id']}/analysis-runs/{run['id']}",
            lambda r: r["status"] in ("succeeded", "failed"),
        )
        print(f"Analysis {run['status']}" + (f": {run['error']}" if run["error"] else ""))
    print(idea["id"])


def cmd_fetch(args: argparse.Namespace) -> None:
    async def go() -> None:
        try:
            page = await PageFetcher().fetch(args.url)
        except FetchError as exc:
            sys.exit(
                f"UNVERIFIABLE: {exc}\n"
                "Preuve can't fetch this page; items citing it will import as 'unverifiable'."
            )
        print(f"# {page.title or '(no title)'}\n# final url: {page.final_url}\n")
        print(page.full_text if args.full or not page.text else page.text)
        if not args.full:
            print("\n# (main content shown; use --full for every visible text node)")

    asyncio.run(go())


def _load_pack(path: str) -> ResearchPack:
    raw = Path(path).read_text(encoding="utf-8")
    try:
        return ResearchPack.model_validate_json(raw)
    except ValidationError as exc:
        print(f"Invalid pack ({exc.error_count()} errors):")
        for err in exc.errors():
            loc = ".".join(str(p) for p in err["loc"])
            print(f"  - {loc}: {err['msg']}")
        sys.exit(1)


def cmd_validate(args: argparse.Namespace) -> None:
    pack = _load_pack(args.pack)
    print(
        f"OK: {len(pack.evidence)} evidence items, {len(pack.unknown_findings)} findings, "
        f"hypothesis update: {'yes' if pack.hypothesis_update else 'no'}, "
        f"new unknowns: {len(pack.new_unknowns)}"
    )


def cmd_import(args: argparse.Namespace) -> None:
    pack = _load_pack(args.pack)
    idea_id = pack.meta.idea_id
    imp = _api("POST", f"/ideas/{idea_id}/research-imports", json=pack.model_dump(mode="json"))
    print(f"Import {imp['id']} queued; verifying {len(pack.evidence)} quotes…", flush=True)
    imp = _wait(
        f"/ideas/{idea_id}/research-imports/{imp['id']}",
        lambda i: i["status"] in ("done", "failed"),
    )
    if imp["status"] == "failed":
        sys.exit(f"Import failed: {imp['error']}")

    r = imp["report"]
    c = r["counts"]
    print(
        f"\nVerified: {c['verified']}   Unverifiable: {c['unverifiable']}"
        f"   Rejected: {c['rejected']}"
    )
    for item in r["rejected"]:
        print(f"  REJECTED {item['ref']}: {item['reason']} ({item['url']})")
    for d in r["dropped_claims"]:
        print(f"  DROPPED CLAIM: {d['statement']!r} (cites {d['missing_refs']})")
    for u in r["downgraded_findings"]:
        print(f"  FINDING DOWNGRADED to no_evidence_found: unknown {u}")
    if r["duplicates"]:
        print(f"  Already known (deduplicated): {', '.join(r['duplicates'])}")
    if r["hypothesis_version"]:
        print(f"  Hypothesis updated -> v{r['hypothesis_version']} (source: research)")
    elif r["hypothesis_skipped"]:
        print(f"  Hypothesis update skipped: {r['hypothesis_skipped']}")
    if r["new_unknowns"]:
        print(f"  New unknowns added: {r['new_unknowns']}")
    comps = r.get("competitors") or {}
    if comps.get("created") or comps.get("updated"):
        print(
            f"  Competitors: {len(comps['created'])} new, {len(comps['updated'])} updated"
            f" ({', '.join(comps['created'] + comps['updated'])})"
        )
    for c in comps.get("rejected", []):
        print(f"  COMPETITOR REJECTED {c['ref']} ({c['name']}): {c['reason']}")
    cos = r.get("companies") or {}
    if cos.get("created") or cos.get("updated"):
        print(
            f"  Companies: {len(cos['created'])} new, {len(cos['updated'])} updated;"
            f" contacts added: {cos.get('contacts_added', 0)}"
        )
    for c in cos.get("rejected", []):
        print(f"  COMPANY REJECTED {c['ref']} ({c['name']}): {c['reason']}")
    for c in cos.get("contacts_rejected", []):
        print(f"  CONTACT REJECTED {c['name']} at {c['company']}: {c['reason']}")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # quotes contain typographic characters
    parser = argparse.ArgumentParser(prog="research", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser(
        "context", help="Idea, hypothesis, unknowns (with ids), ICPs, research so far"
    )
    p.add_argument("idea_id")
    p.set_defaults(func=cmd_context)

    p = sub.add_parser("create", help="Create an idea (optionally run the 1A analysis)")
    p.add_argument("--title", required=True)
    p.add_argument("--description", required=True)
    p.add_argument("--market", default="United States")
    p.add_argument("--why", default=None)
    p.add_argument("--analyze", action="store_true")
    p.set_defaults(func=cmd_create)

    p = sub.add_parser("fetch", help="Print the exact page text Preuve verifies quotes against")
    p.add_argument("url")
    p.add_argument("--full", action="store_true")
    p.set_defaults(func=cmd_fetch)

    p = sub.add_parser("validate", help="Validate a pack against the schema (offline)")
    p.add_argument("pack")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("import", help="Import a pack and print the verification report")
    p.add_argument("pack")
    p.set_defaults(func=cmd_import)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
