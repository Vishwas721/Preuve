"""Write the research pack JSON schema to docs/ (run after changing app/modules/research/pack.py).

Run: uv run python -m app.scripts.export_pack_schema
"""

import json
from pathlib import Path

from app.modules.research.pack import ResearchPack

SCHEMA_PATH = Path(__file__).resolve().parents[4] / "docs" / "research-pack.schema.json"


def render() -> str:
    schema = ResearchPack.model_json_schema()
    schema["$id"] = "https://github.com/Vishwas721/Preuve/docs/research-pack.schema.json"
    schema["title"] = "Preuve research pack"
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":
    SCHEMA_PATH.write_text(render(), encoding="utf-8", newline="\n")
    print(f"wrote {SCHEMA_PATH}")
