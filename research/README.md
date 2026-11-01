# Research packs

Output of the `/research-idea` skill (see `.claude/skills/research-idea/SKILL.md` and
[ADR 0004](../docs/adr/0004-claude-code-research-analyst.md)). One folder per idea:

- `pack-<date>.json`: the research pack imported into Preuve
  (schema: `docs/research-pack.schema.json`);
- `report-<date>.md`: the readable report.

Packs are the input. What Preuve stores is what survived verification, so check the import
report in the app for verified, unverifiable and rejected counts.
